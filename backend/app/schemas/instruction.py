"""Data models for instruction stream generation.

Defines data structures such as the instruction format, generation requests and responses.
"""

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


# ==================== Instruction Format Definitions ====================

class InstructionBase(BaseModel):
    """Instruction base class"""
    op: str = Field(..., description="Instruction operation type")


class SetInstruction(InstructionBase):
    """Set field value instruction"""
    op: Literal["set"] = "set"
    path: str = Field(..., description="Field path in JSON Pointer format, e.g. /name or /config/theme")
    value: Any = Field(..., description="Value to set, can be any type")


class AppendInstruction(InstructionBase):
    """Append element to array instruction"""
    op: Literal["append"] = "append"
    path: str = Field(..., description="Array path in JSON Pointer format")
    value: Any = Field(..., description="Element to append")


class DoneInstruction(InstructionBase):
    """Generation completion flag instruction"""
    op: Literal["done"] = "done"


# Union type: all instruction types
Instruction = SetInstruction | AppendInstruction | DoneInstruction


# ==================== Generation Config ====================

class GenerationConfig(BaseModel):
    """Card generation config

    Defines the strategy and prompts for generating card content.
    """
    mode: Literal["instruction_stream"] = Field(
        default="instruction_stream",
        description="Generation mode, currently only instruction stream mode is supported"
    )
    prompt_template: Optional[str] = Field(
        default=None,
        description="Global prompt template (optional)"
    )
    field_hints: Optional[Dict[str, str]] = Field(
        default=None,
        description="Field-level generation hints, key is field path, value is hint text"
    )
    field_order: Optional[List[str]] = Field(
        default=None,
        description="Suggested field generation order"
    )
    custom: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Custom config (for extension)"
    )


# ==================== API Request/Response Models ====================

class ConversationMessage(BaseModel):
    """Conversation message"""
    role: Literal["system", "user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")


class InstructionGenerateRequest(BaseModel):
    """Instruction stream generation request"""

    # LLM config
    llm_config_id: int = Field(..., description="LLM config ID")

    # User input
    user_prompt: str = Field(default="", description="User-provided prompt or reply")

    # Schema definition
    response_model_schema: Dict[str, Any] = Field(..., description="JSON Schema of the target data structure")

    # Current data state
    current_data: Dict[str, Any] = Field(default_factory=dict, description="Currently generated data")

    # Conversation context
    conversation_context: List[ConversationMessage] = Field(
        default_factory=list,
        description="Conversation history (maintained by frontend)"
    )

    # Generation config (optional)
    generation_config: Optional[GenerationConfig] = Field(
        default=None,
        description="Generation config, uses default config if empty"
    )

    # Prompt template (optional, overrides default)
    prompt_template: Optional[str] = Field(
        default=None,
        description="Custom prompt template"
    )

    # Context info (optional)
    context_info: Optional[str] = Field(
        default=None,
        description="Context injection info (e.g. related entities, existing cards)"
    )

    # Sampling parameters
    temperature: Optional[float] = Field(default=0.7, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, description="Max generation token count")
    timeout: Optional[float] = Field(default=150, description="Timeout (seconds)")

    # Dependency data (e.g. entity name list)
    deps: Optional[str] = Field(default=None, description="Dependency data, used for validation")


# ==================== SSE Event Types ====================

class ThinkingEvent(BaseModel):
    """Thinking event (AI's natural language output)"""
    type: Literal["thinking"] = "thinking"
    text: str = Field(..., description="Thinking content or question")


class InstructionEvent(BaseModel):
    """Instruction event (validated instruction)"""
    type: Literal["instruction"] = "instruction"
    instruction: Instruction = Field(..., description="Instruction object")


class WarningEvent(BaseModel):
    """Warning event (non-fatal error)"""
    type: Literal["warning"] = "warning"
    text: str = Field(..., description="Warning message")


class ErrorEvent(BaseModel):
    """Error event (fatal error)"""
    type: Literal["error"] = "error"
    text: str = Field(..., description="Error message")


class DoneEvent(BaseModel):
    """Done event"""
    type: Literal["done"] = "done"
    success: bool = Field(default=True, description="Whether completed successfully")
    message: Optional[str] = Field(default=None, description="Completion message")


# Union type: all event types
StreamEvent = ThinkingEvent | InstructionEvent | WarningEvent | ErrorEvent | DoneEvent
