"""Structured generation node

Uses the instruction-flow generation service (Instruction Generator) to generate
structured data. Supports auto-validation, auto-repair, and Pydantic model output.
"""

from typing import Any, Dict, Optional, List, AsyncIterator, TYPE_CHECKING
from pydantic import BaseModel, Field
from loguru import logger

if TYPE_CHECKING:
    from ...engine.async_executor import ProgressEvent

from ...registry import register_node
from ..base import BaseNode
from app.services import prompt_service
from app.services.ai.core.model_builder import build_model_from_json_schema
from app.services.ai.core.llm_service import generate_structured
from app.services.schema_service import compose_full_schema
from app.db.models import CardType
from app.schemas.response_registry import RESPONSE_MODEL_MAP
from sqlmodel import select


class StructuredGenerateInput(BaseModel):
    """Structured generation input"""
    user_prompt: str = Field(..., description="User prompt")
    llm_config_id: int = Field(..., description="LLM config ID", json_schema_extra={"x-component": "LLMSelect"})
    response_model_id: str = Field(..., description="Response model", json_schema_extra={"x-component": "ResponseModelSelect"})
    context: Optional[Dict[str, Any]] = Field(None, description="Context data / initial data")
    schema_extra: Optional[Dict[str, Any]] = Field(None, description="Additional Schema definitions (optional)")
    max_retry: int = Field(3, description="Maximum retry/repair count")
    prompt_template: Optional[str] = Field(None, description="Prompt template name (optional)", json_schema_extra={"x-component": "PromptSelect"})
    temperature: float = Field(0.7, description="Temperature parameter")
    max_tokens: Optional[int] = Field(None, description="Maximum token count")
    timeout: int = Field(60, description="Timeout (seconds)")
    fail_soft: bool = Field(False, description="Whether to degrade and return an empty result on failure instead of raising")
    use_instruction_flow: bool = Field(
        False,
        description="Whether to use instruction-flow mode (recommended for complex structures; can be turned off for simple structures to use native structured output)",
    )


class StructuredGenerateOutput(BaseModel):
    """Structured generation output"""
    data: Dict[str, Any] = Field(..., description="Generated structured data")
    logs: List[Dict[str, Any]] = Field(..., description="Generation process logs")

@register_node
class StructuredGenerateNode(BaseNode[StructuredGenerateInput, StructuredGenerateOutput]):
    """Structured generation node"""
    
    node_type = "AI.StructuredGenerate"
    category = "ai"
    label = "Structured Generation"
    description = "Generate structured data conforming to a specified Schema (supports auto-repair)"
    
    input_model = StructuredGenerateInput
    output_model = StructuredGenerateOutput

    @classmethod
    def get_output_schema_contract(
        cls,
        config: Dict[str, Any],
        session=None,
    ) -> Optional[Dict[str, Any]]:
        """Declare the schema contract of the output `data` field.

        Contract format:
        {
            "kind": "structured_output",
            "schema_id": "Character Card",
            "data_path": "data"
        }
        """
        model_id = config.get("response_model_id")
        if not isinstance(model_id, str) or not model_id.strip():
            return None

        return {
            "kind": "structured_output",
            "schema_id": model_id.strip(),
            "data_path": "data",
        }

    async def execute(
        self,
        inputs: StructuredGenerateInput
    ) -> AsyncIterator[StructuredGenerateOutput]:
        """Execute generation"""
        session = self.context.session
        user_prompt = inputs.user_prompt
        current_data = inputs.context or {}
        
        # 1. Get the target Schema
        target_schema = self._get_schema(session, inputs)
        if not target_schema:
            raise ValueError(f"Unable to load model Schema: {inputs.response_model_id}")
            
        # 2. Prepare parameters
        # Assemble the full Schema (handle $ref)
        full_schema = compose_full_schema(session, target_schema)

        # Load the prompt template (if configured)
        card_prompt_content = None
        if inputs.prompt_template:
            prompt = prompt_service.get_prompt_by_name(session, inputs.prompt_template)
            if prompt and prompt.template:
                card_prompt_content = prompt.template
        
        logger.info(f"[AI.Structured] Starting generation: model={inputs.response_model_id}")

        # 3. Call the instruction-flow aggregated generation (the node layer stays non-streaming)
        try:
            dynamic_output = build_model_from_json_schema(
                f"WorkflowStructured_{inputs.response_model_id}",
                full_schema,
            )
            generated = await generate_structured(
                session=session,
                llm_config_id=inputs.llm_config_id,
                user_prompt=user_prompt,
                output_type=dynamic_output,
                system_prompt=card_prompt_content,
                deps="",
                temperature=inputs.temperature,
                max_tokens=inputs.max_tokens,
                timeout=inputs.timeout,
                max_retries=inputs.max_retry,
                use_instruction_flow=inputs.use_instruction_flow,
                track_stats=True,
                return_logs=True,
            )
        except Exception as e:
            if inputs.fail_soft:
                logger.warning(
                    f"[AI.Structured] Generation failed but fail_soft enabled, returning degraded result: model={inputs.response_model_id}, err={e}"
                )
                yield StructuredGenerateOutput(data=current_data or {}, logs=[{"type": "error", "text": str(e)}])
                return
            logger.exception(f"[AI.Structured] Execution exception")
            raise

        result_data = generated["result"].model_dump(mode="json")

        yield StructuredGenerateOutput(
            data=result_data,
            logs=generated["logs"],
        )

    def _get_schema(self, session, inputs: StructuredGenerateInput) -> Optional[Dict[str, Any]]:
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