
import copy
import json
import os
from typing import Any, AsyncIterator, Dict, List, Optional, TYPE_CHECKING, Union

from loguru import logger
from pydantic import BaseModel, Field
from sqlmodel import select

if TYPE_CHECKING:
    from ...engine.async_executor import ProgressEvent

from app.db.models import CardType
from app.schemas.response_registry import RESPONSE_MODEL_MAP
from app.services.ai.core.model_builder import build_model_from_json_schema
from app.services.ai.core.llm_service import generate_structured
from ...expressions.evaluator import evaluate_expression
from ...registry import register_node
from ..base import BaseNode


class SequentialStructuredInput(BaseModel):
    """Sequential structured generation input"""

    items: List[Any] = Field(..., description="Data list (processed in order)")
    llm_config_id: int = Field(..., description="LLM config ID", json_schema_extra={"x-component": "LLMSelect"})
    prompt_template: str = Field(
        ...,
        description="Prompt template, supports {{content}} / {{item.xxx}} / {{carry.xxx}}",
        json_schema_extra={"x-component": "Textarea"},
    )
    response_model_id: str = Field(..., description="Response model", json_schema_extra={"x-component": "ResponseModelSelect"})
    temperature: Optional[float] = Field(
        None,
        description="Sampling temperature (optional, defaults to model config)",
        ge=0.0,
        le=2.0,
    )
    max_tokens: Optional[int] = Field(
        None,
        description="Max output tokens (optional, defaults to model config)",
        ge=1,
    )
    timeout: Optional[float] = Field(
        None,
        description="Per-call timeout in seconds (optional, defaults to model config)",
        gt=0,
    )
    max_retries: int = Field(3, description="Max retry count", ge=1)
    use_instruction_flow: bool = Field(
        False,
        description="Whether to use instruction-flow mode (recommended for complex structures; can be disabled for simple structures to use native structured output)",
    )
    overlap_size: int = Field(0, description="Overlap window size (optional, default 0)", ge=0)
    initial_carry: Optional[Dict[str, Any]] = Field(None, description="Initial carry state")
    carry_extract_expr: Optional[str] = Field(
        None,
        description="Expression to extract the next round's carry from the current round's result (optional)",
        json_schema_extra={"x-component": "Textarea"},
    )
    fail_soft: bool = Field(False, description="Whether to degrade and continue on single-item failure")


class SequentialStructuredOutput(BaseModel):
    """Sequential structured generation output"""

    results: List[Dict[str, Any]] = Field(..., description="Per-round results (ai_result/meta/carry_in/carry_out)")
    final_carry: Dict[str, Any] = Field(..., description="Final carry state")
    errors: List[Dict[str, Any]] = Field(..., description="Error list")


@register_node
class SequentialStructuredNode(BaseNode[SequentialStructuredInput, SequentialStructuredOutput]):
    """
    AI node that executes structured generation in sequence and carries over carry state.
    Usage notes:
    - `items` are processed one by one in order, naturally supporting cross-item context carry-over.
    - `prompt_template` supports `{{content}}`, `{{item.xxx}}`, `{{carry.xxx}}`, `{{overlap_size}}` placeholders.
    - Use `carry_extract_expr` to extract the next round's carry from the current `ai_result` (must return a dict or None).
    - Optionally pass through `temperature/max_tokens/timeout` to fine-tune structured generation quality and stability.
    - Emits `ProgressEvent` continuously during execution and writes `partial_results/carry_state` into the checkpoint, supporting checkpoint resume.
    """

    node_type = "AI.SequentialStructured"
    category = "ai"
    label = "Sequential Structured Generation"
    description = "Invoke structured generation in sequence, supporting cross-round carry hand-off and checkpoint resume"

    input_model = SequentialStructuredInput
    output_model = SequentialStructuredOutput

    async def execute(
        self,
        inputs: SequentialStructuredInput,
    ) -> AsyncIterator[Union["ProgressEvent", SequentialStructuredOutput]]:
        from ...engine.async_executor import ProgressEvent

        items = inputs.items
        if not isinstance(items, list):
            raise ValueError("Input items must be a list")

        if not inputs.prompt_template:
            raise ValueError("Prompt template is empty")

        if not items:
            yield SequentialStructuredOutput(
                results=[],
                final_carry=copy.deepcopy(inputs.initial_carry or {}),
                errors=[],
            )
            return

        total = len(items)
        schema = self._get_schema(self.context.session, inputs)
        if not schema:
            raise ValueError(f"Failed to load model Schema: {inputs.response_model_id}")
        dynamic_output = build_model_from_json_schema(
            f"SequentialStructured_{inputs.response_model_id}",
            schema,
        )

        checkpoint = getattr(self.context, "checkpoint", None) or {}
        results = self._normalize_result_list(checkpoint.get("partial_results", []))
        errors = self._normalize_result_list(checkpoint.get("errors", []))
        processed_indices = self._normalize_index_set(checkpoint.get("processed_indices", []), total)

        carry_state = checkpoint.get("carry_state")
        if not isinstance(carry_state, dict):
            carry_state = copy.deepcopy(inputs.initial_carry or {})

        current_index = checkpoint.get("current_index")
        if not isinstance(current_index, int):
            current_index = len(results)

        current_index = max(current_index, len(results), len(processed_indices))
        current_index = min(current_index, total)

        if current_index > 0:
            logger.info(
                f"[SequentialStructured] Resumed from checkpoint: processed {current_index}/{total}, "
                f"errors={len(errors)}"
            )

        if current_index >= total:
            yield SequentialStructuredOutput(
                results=results,
                final_carry=carry_state,
                errors=errors,
            )
            return

        for index in range(current_index, total):
            item = items[index]
            carry_in = copy.deepcopy(carry_state)

            try:
                rendered_prompt = self._render_prompt(
                    template=inputs.prompt_template,
                    item=item,
                    carry=carry_in,
                    overlap_size=inputs.overlap_size,
                )

                logger.info(f"[SequentialStructured] Item {index}: starting LLM call")
                generated = await generate_structured(
                    session=self.context.session,
                    llm_config_id=inputs.llm_config_id,
                    user_prompt=rendered_prompt,
                    output_type=dynamic_output,
                    system_prompt=None,
                    deps="",
                    temperature=inputs.temperature or 0.7,
                    max_tokens=inputs.max_tokens,
                    timeout=inputs.timeout or 150,
                    max_retries=inputs.max_retries,
                    use_instruction_flow=inputs.use_instruction_flow,
                    track_stats=True,
                    return_logs=True,
                )
                ai_result = generated["result"].model_dump(mode="json")
                logger.info(f"[SequentialStructured] Item {index}: ✅ LLM call complete")

                carry_out = self._extract_carry(
                    expr=inputs.carry_extract_expr,
                    ai_result=ai_result,
                    item=item,
                    carry=carry_in,
                    index=index,
                    results=results,
                    errors=errors,
                )

                result_item = {
                    "index": index,
                    "ai_result": ai_result,
                    "logs": generated["logs"],
                    "meta": item,
                    "carry_in": carry_in,
                    "carry_out": carry_out,
                }
                results.append(result_item)
                carry_state = carry_out
                processed_indices.add(index)

            except Exception as e:
                logger.error(f"[SequentialStructured] Item {index} processing failed: {e}")
                error_item = {"index": index, "item": item, "error": str(e)}
                errors.append(error_item)

                if not inputs.fail_soft:
                    raise

                results.append(
                    {
                        "index": index,
                        "error": str(e),
                        "meta": item,
                        "carry_in": carry_in,
                        "carry_out": carry_state,
                    }
                )
                processed_indices.add(index)

            percent = ((index + 1) / total) * 100
            yield ProgressEvent(
                percent=percent,
                message=f"Processed {index + 1}/{total} items",
                data={
                    "current_index": index + 1,
                    "processed_indices": sorted(processed_indices),
                    "carry_state": carry_state,
                    "partial_results": results,
                    "errors": errors,
                },
            )

        yield SequentialStructuredOutput(
            results=results,
            final_carry=carry_state,
            errors=errors,
        )

    def _render_prompt(
        self,
        template: str,
        item: Any,
        carry: Dict[str, Any],
        overlap_size: int,
    ) -> str:
        content = self._extract_content(item)
        rendered = template.replace("{{content}}", str(content))
        rendered = rendered.replace("{{item}}", self._to_text(item))
        rendered = rendered.replace("{{carry}}", self._to_text(carry))
        rendered = rendered.replace("{{overlap_size}}", str(overlap_size))

        rendered = self._render_prefix_fields(rendered, "item", item)
        rendered = self._render_prefix_fields(rendered, "carry", carry)
        return rendered

    def _render_prefix_fields(self, text: str, prefix: str, value: Any, path: Optional[List[str]] = None) -> str:
        current_path = path or []
        placeholder = "{{" + ".".join([prefix, *current_path]) + "}}"

        if current_path:
            text = text.replace(placeholder, self._to_text(value))

        if isinstance(value, dict):
            for key, child in value.items():
                text = self._render_prefix_fields(text, prefix, child, [*current_path, str(key)])

        return text

    def _extract_content(self, item: Any) -> str:
        if not isinstance(item, dict):
            return str(item)

        content = ""
        path = item.get("path")

        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as file:
                    content = file.read()
            except Exception as e:
                logger.error(f"[SequentialStructured] Failed to read file: {path}, {e}")
                content = f"[Read failed: {e}]"

        if not content and "content" in item:
            content = self._to_text(item.get("content"))

        return content

    def _extract_carry(
        self,
        expr: Optional[str],
        ai_result: Any,
        item: Any,
        carry: Dict[str, Any],
        index: int,
        results: List[Dict[str, Any]],
        errors: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not expr:
            return copy.deepcopy(carry)

        next_carry = evaluate_expression(
            expr,
            {
                "ai_result": ai_result,
                "item": item,
                "carry": carry,
                "index": index,
                "results": results,
                "errors": errors,
            },
        )

        if next_carry is None:
            return {}

        if not isinstance(next_carry, dict):
            raise ValueError("carry_extract_expr must return a dict or None")

        return next_carry

    def _normalize_result_list(self, value: Any) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _normalize_index_set(self, value: Any, total: int) -> set[int]:
        if not isinstance(value, list):
            return set()

        normalized: set[int] = set()
        for item in value:
            try:
                index = int(item)
            except Exception:
                continue

            if 0 <= index < total:
                normalized.add(index)

        return normalized

    def _to_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)

        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    def _get_schema(self, session, inputs: SequentialStructuredInput) -> Optional[Dict[str, Any]]:
        """Get the JSON Schema based on config"""

        stmt = select(CardType).where(CardType.name == inputs.response_model_id)
        ct = session.exec(stmt).first()
        if ct and ct.json_schema:
            return ct.json_schema

        builtin_model = RESPONSE_MODEL_MAP.get(inputs.response_model_id)
        if builtin_model is not None:
            return builtin_model.model_json_schema(ref_template="#/$defs/{model}")

        return None
