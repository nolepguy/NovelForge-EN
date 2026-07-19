"""LLM generation node

Provides single-turn LLM call capability, supporting prompt templates and structured output.
"""

import json
from typing import Any, Dict, Optional, AsyncIterator
from pydantic import BaseModel, Field
from loguru import logger

from ...registry import register_node
from ..base import BaseNode
from app.services.ai.core.chat_model_factory import build_chat_model
from langchain_core.messages import HumanMessage, SystemMessage


# ============================================================
# Input/Output Models
# ============================================================

class LLMInput(BaseModel):
    """LLM generation input"""
    user_prompt: str = Field(..., description="User prompt")
    system_prompt: Optional[str] = Field(None, description="System prompt")
    llm_config_id: int = Field(..., description="LLM config ID", gt=0)
    temperature: float = Field(0.7, description="Temperature parameter", ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, description="Maximum generated token count", gt=0)
    timeout: int = Field(60, description="Timeout (seconds)", gt=0)
    max_retry: int = Field(3, description="Maximum retry count", ge=0, le=10)


class LLMOutput(BaseModel):
    """LLM generation output"""
    response: str = Field(..., description="Generated text")
    usage: Dict[str, Any] = Field(default_factory=dict, description="Token usage stats")


def _extract_text(value: Any) -> str:
    """Robustly convert model-returned content to plain text, avoiding list/dict triggering response:str validation failure."""
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, list):
        parts = [_extract_text(item) for item in value]
        return "".join([part for part in parts if part])

    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            return text

        content = value.get("content")
        if content is not None:
            extracted = _extract_text(content)
            if extracted:
                return extracted

        for key in ("output_text", "message", "reasoning_content", "value"):
            field_val = value.get(key)
            if field_val is None:
                continue
            extracted = _extract_text(field_val)
            if extracted:
                return extracted

        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
            return _extract_text(dumped)
        except Exception:
            pass

    if hasattr(value, "content"):
        try:
            return _extract_text(getattr(value, "content"))
        except Exception:
            pass

    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


# ============================================================
# Node Implementation
# ============================================================

@register_node
class LLMGenerateNode(BaseNode[LLMInput, LLMOutput]):
    """LLM generation node"""
    
    node_type = "AI.LLM"
    category = "ai"
    label = "LLM Call"
    description = "Call a large language model for text generation"
    
    input_model = LLMInput
    output_model = LLMOutput

    async def execute(self, input_data: LLMInput) -> AsyncIterator[LLMOutput]:
        """Execute the LLM call"""
        
        # Build the ChatModel (outside the retry loop, to avoid rebuilding)
        try:
            model = build_chat_model(
                session=self.context.session,
                llm_config_id=input_data.llm_config_id,
                temperature=input_data.temperature,
                max_tokens=input_data.max_tokens,
                timeout=input_data.timeout,
            )
        except Exception as e:
            logger.error(f"[AI.LLM] Failed to build model: {e}")
            raise ValueError(f"Failed to build model: {str(e)}")
        
        # Build messages
        messages = []
        if input_data.system_prompt:
            messages.append(SystemMessage(content=input_data.system_prompt))
        messages.append(HumanMessage(content=input_data.user_prompt))
        
        # Retry loop
        last_error = None
        for attempt in range(input_data.max_retry + 1):  # +1 because the first time is not a retry
            try:
                # Call the model
                response = await model.ainvoke(messages)
                
                # Extract text (compatible with content being list/dict for model returns)
                payload = response.content if hasattr(response, 'content') else response
                response_text = _extract_text(payload)
                
                # Extract usage info
                usage = {}
                if hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata
                elif hasattr(response, 'response_metadata'):
                    meta = response.response_metadata
                    if isinstance(meta, dict):
                        usage = meta.get('usage', {})
                
                logger.info(
                    f"[AI.LLM] LLM call succeeded (attempt {attempt + 1}/{input_data.max_retry + 1}): "
                    f"llm_config_id={input_data.llm_config_id}, response_length={len(response_text)}"
                )
                
                yield LLMOutput(
                    response=response_text,
                    usage=usage
                )
                return
                
            except Exception as e:
                last_error = e
                if attempt < input_data.max_retry:
                    logger.warning(
                        f"[AI.LLM] LLM call failed (attempt {attempt + 1}/{input_data.max_retry + 1}), "
                        f"will retry: {str(e)}"
                    )
                else:
                    logger.error(
                        f"[AI.LLM] LLM call failed, reached maximum retry count ({input_data.max_retry + 1}): {str(e)}"
                    )
        
        # All retries failed
        raise RuntimeError(f"LLM call failed (after {input_data.max_retry} retries): {str(last_error)}")