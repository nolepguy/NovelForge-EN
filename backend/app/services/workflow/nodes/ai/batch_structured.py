import asyncio
import os
from typing import Any, Dict, List, Optional, AsyncIterator, Union, TYPE_CHECKING
from loguru import logger
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ...engine.async_executor import ProgressEvent

from app.services.ai.core.model_builder import build_model_from_json_schema
from app.services.ai.core.llm_service import generate_structured
from ...registry import register_node
from ..base import BaseNode
from app.db.models import CardType
from app.schemas.response_registry import RESPONSE_MODEL_MAP
from sqlmodel import select


class BatchStructuredInput(BaseModel):
    """Batch structured generation input"""
    items: List[Any] = Field(..., description="Data list (includes metadata)")
    llm_config_id: int = Field(..., description="LLM config ID", json_schema_extra={"x-component": "LLMSelect"})
    prompt_template: str = Field(..., description="Prompt template, supports {{content}} and {{item.field}}", json_schema_extra={"x-component": "Textarea"})
    response_model_id: str = Field(..., description="Response model", json_schema_extra={"x-component": "ResponseModelSelect"})
    concurrency: int = Field(30, description="Maximum concurrency", ge=1)
    max_retries: int = Field(3, description="Maximum retry count")
    temperature: float = Field(0.7, description="Temperature parameter")
    max_tokens: Optional[int] = Field(None, description="Maximum token count")
    timeout: Optional[float] = Field(150, description="Timeout (seconds)")
    fail_soft: bool = Field(False, description="Whether to degrade and return partial results on single-item failure")
    use_instruction_flow: bool = Field(
        False,
        description="Whether to use instruction-flow mode (recommended for complex structures; can be turned off for simple structures to use native structured output)",
    )
    cache_key: Optional[str] = Field(None, description="Cache key (for checkpoint recovery); if empty, uses item.path or index")


class BatchStructuredOutput(BaseModel):
    """Batch structured generation output"""
    results: List[Dict[str, Any]] = Field(..., description="Extraction result list")
    errors: List[Dict[str, Any]] = Field(..., description="Error item list")


@register_node
class BatchStructuredNode(BaseNode[BatchStructuredInput, BatchStructuredOutput]):
    node_type = "AI.BatchStructured"
    category = "ai"
    label = "Batch Structured Generation"
    description = "Batch-call LLM for structured extraction, supports concurrency and checkpoint recovery"
    
    input_model = BatchStructuredInput
    output_model = BatchStructuredOutput

    async def execute(self, inputs: BatchStructuredInput) -> AsyncIterator[Union['ProgressEvent', BatchStructuredOutput]]:
        """Batch structured generation (supports concurrency and checkpoint recovery)"""
        from ...engine.async_executor import ProgressEvent
        
        items = inputs.items
        if not isinstance(items, list):
            raise ValueError("Input items must be a list")

        if not items:
            yield BatchStructuredOutput(results=[], errors=[])
            return

        prompt_template = inputs.prompt_template
        if not prompt_template:
            raise ValueError("Prompt template is empty")

        # === 1. Recover checkpoint ===
        checkpoint = getattr(self.context, 'checkpoint', None)
        processed_indices = set(checkpoint.get('processed_indices', [])) if checkpoint else set()
        saved_results = checkpoint.get('partial_results', []) if checkpoint else []
        
        if processed_indices:
            logger.info(
                f"[BatchStructured] Resumed from checkpoint: "
                f"processed {len(processed_indices)}/{len(items)}"
            )

        # Initialize the result list
        results = [None] * len(items)
        errors = []
        total = len(items)
        
        # Recover saved results
        for saved_result in saved_results:
            if isinstance(saved_result, dict) and 'meta' in saved_result:
                for i, item in enumerate(items):
                    if item == saved_result['meta']:
                        results[i] = saved_result
                        break
        
        # Indices to process
        pending_indices = [i for i in range(len(items)) if i not in processed_indices]
        
        if not pending_indices:
            logger.info(f"[BatchStructured] All tasks completed")
            yield BatchStructuredOutput(
                results=[r for r in results if r is not None],
                errors=errors
            )
            return
        
        logger.info(
            f"[BatchStructured] {len(pending_indices)} items to process "
            f"({len(processed_indices)} completed, concurrency limit: {inputs.concurrency})"
        )

        schema = self._get_schema(self.context.session, inputs)
        if not schema:
            raise ValueError(f"Unable to load model Schema: {inputs.response_model_id}")
        dynamic_output = build_model_from_json_schema(
            f"BatchStructured_{inputs.response_model_id}",
            schema,
        )
        
        # === 2. Progress queue ===
        progress_queue = asyncio.Queue()
        
        # === 3. Single-item processing function ===
        async def process_item(index):
            """Process a single item"""
            item = items[index]
            
            try:
                # Prepare content
                content = ""
                path = item.get("path")
                
                if path and os.path.exists(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                    except Exception as e:
                        logger.error(f"Failed to read file: {path}, {e}")
                        content = f"[Read failed: {e}]"
                
                if not content and "content" in item:
                    content = item["content"]

                # Render the prompt
                current_prompt = prompt_template.replace("{{content}}", str(content))
                for k, v in item.items():
                    if k != "content":
                        current_prompt = current_prompt.replace(f"{{{{item.{k}}}}}", str(v))
                
                # LLM call
                logger.info(f"[BatchStructured] Item {index}: starting LLM call")

                generated = await generate_structured(
                    session=self.context.session,
                    llm_config_id=inputs.llm_config_id,
                    user_prompt=current_prompt,
                    output_type=dynamic_output,
                    system_prompt=None,
                    deps="",
                    temperature=inputs.temperature,
                    max_tokens=inputs.max_tokens,
                    timeout=inputs.timeout or 150,
                    max_retries=inputs.max_retries,
                    use_instruction_flow=inputs.use_instruction_flow,
                    track_stats=True,
                    return_logs=True,
                )
                
                logger.info(f"[BatchStructured] Item {index}: LLM call completed")
                
                # Save the result
                results[index] = {
                    "ai_result": generated["result"].model_dump(mode="json"),
                    "logs": generated["logs"],
                    "meta": item
                }
                
            except asyncio.CancelledError:
                logger.warning(f"[BatchStructured] Item {index}: task cancelled")
                raise
            except Exception as e:
                logger.error(f"[BatchStructured] Item {index} processing failed: {e}")
                errors.append({"index": index, "item": item, "error": str(e)})
                results[index] = {"error": str(e), "meta": item}
            
            finally:
                # Notify progress
                processed_indices.add(index)
                await progress_queue.put(index)
        
        # === 4. Batch processing function (single task) ===
        async def process_all_batches():
            """Process all pending items in batches"""
            batch_size = inputs.concurrency
            
            for batch_start in range(0, len(pending_indices), batch_size):
                batch_indices = pending_indices[batch_start:batch_start + batch_size]
                
                logger.info(
                    f"[BatchStructured] Processing batch {batch_start//batch_size + 1}: "
                    f"indices {batch_indices}"
                )
                
                # Process the current batch concurrently
                await asyncio.gather(
                    *[process_item(i) for i in batch_indices],
                    return_exceptions=True
                )
                
                logger.info(
                    f"[BatchStructured] Batch {batch_start//batch_size + 1} completed"
                )
        
        # === 5. Start processing and listen for progress ===
        main_task = asyncio.create_task(process_all_batches())
        self.register_task(main_task)  # Only need to register one task
        
        # Report progress in real time
        while not main_task.done():
            try:
                await asyncio.wait_for(progress_queue.get(), timeout=0.5)
                
                # Report progress
                percent = (len(processed_indices) / total) * 100
                current_results = [r for r in results if r is not None]
                
                yield ProgressEvent(
                    percent=percent,
                    message=f"Processed {len(processed_indices)}/{total} items",
                    data={
                        'processed_indices': list(processed_indices),
                        'partial_results': current_results
                    }
                )
            except asyncio.TimeoutError:
                continue
        
        # Wait for the main task to complete
        await main_task
        
        logger.info(
            f"[BatchStructured] Batch processing completed: "
            f"{len([r for r in results if r is not None])} succeeded, {len(errors)} failed"
        )
        
        # === 6. Return the final result ===
        yield BatchStructuredOutput(
            results=[r for r in results if r is not None],
            errors=errors
        )

    def _get_schema(self, session, inputs: BatchStructuredInput) -> Optional[Dict[str, Any]]:
        """Get the JSON Schema based on config
        """
        
        stmt = select(CardType).where(CardType.name == inputs.response_model_id)
        ct = session.exec(stmt).first()
        if ct and ct.json_schema:
            return ct.json_schema

        builtin_model = RESPONSE_MODEL_MAP.get(inputs.response_model_id)
        if builtin_model is not None:
            return builtin_model.model_json_schema(ref_template="#/$defs/{model}")
                
        return None