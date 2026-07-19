from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal


ContinuationWordControlMode = Literal["prompt_only", "balanced"]

class ContinuationRequest(BaseModel):
    previous_content: str = Field(default="", description="Already written chapter content")
    llm_config_id: int
    stream: bool = False
    # Optional context fields (backward compatible)
    project_id: Optional[int] = None
    volume_number: Optional[int] = None
    chapter_number: Optional[int] = None
    participants: Optional[List[str]] = None
    # Sampling and timeout (optional)
    temperature: Optional[float] = Field(default=None, description="Sampling temperature 0-2, leave empty to use model default")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens to generate, leave empty to use default")
    timeout: Optional[float] = Field(default=None, description="Generation timeout (seconds), leave empty to use default")
    # Context info (referenced context + fact subgraph)
    context_info: Optional[str] = Field(default=None, description="Context info, including referenced content and fact subgraph")
    # Word count of existing content (used to guide continuation length)
    existing_word_count: Optional[int] = Field(default=None, description="Word count of the existing chapter body")
    target_word_count: Optional[int] = Field(default=None, description="Target total word count")
    word_control_mode: Optional[ContinuationWordControlMode] = Field(
        default=None,
        description="Word count control mode: prompt_only / balanced",
    )
    continuation_guidance: Optional[str] = Field(default=None, description="Continuation guidance requirements")
    budget_round_hint: Optional[int] = Field(default=None, description="Current round hint fed back by the budget runtime")
    remaining_word_count_hint: Optional[int] = Field(default=None, description="Remaining word count hint fed back by the budget runtime")
    is_final_round_hint: Optional[bool] = Field(default=None, description="Final round flag fed back by the budget runtime")
    # Prompt name selected by the parameter card (this prompt is used as system prompt with priority)
    prompt_name: Optional[str] = Field(default=None, description="Prompt name selected by the parameter card")
    # Whether to append the "directly output continuous novel body" suffix (default True for backward compatibility with existing continuation)
    append_continuous_novel_directive: bool = Field(default=True, description="Whether to append the continuous novel body directive")

class ContinuationResponse(BaseModel):
    content: str


class AssistantChatRequest(BaseModel):
    """Inspiration assistant chat request (new format)"""
    # New format: frontend sends unified context info and user input
    context_info: str = Field(description="Complete project context info (including project structure, operation history, referenced cards, etc.)")
    user_prompt: str = Field(default="", description="Current user input (can be empty)")

    # Required fields
    project_id: int = Field(description="Project ID (for tool call scope)")
    llm_config_id: int = Field(description="LLM config ID")
    prompt_name: str = Field(default="inspiration_chat", description="System prompt name")

    # Optional parameters
    temperature: Optional[float] = Field(default=None, description="Sampling temperature 0-2")
    max_tokens: Optional[int] = Field(default=None, description="Max token count")
    timeout: Optional[float] = Field(default=None, description="Timeout in seconds")
    stream: bool = Field(default=True, description="Whether to stream output")
    thinking_enabled: Optional[bool] = Field(default=None, description="Whether to enable reasoning/Thinking output (only supported by some models)")
    # Context summarization config (used only by inspiration assistant, frontend may pass it in)
    context_summarization_enabled: Optional[bool] = Field(default=None, description="Whether to enable the context summarization middleware (summarizes and compresses overly long conversations)")
    context_summarization_threshold: Optional[int] = Field(default=None, description="Token threshold that triggers context summarization")
    react_mode_enabled: Optional[bool] = Field(default=None, description="Whether to enable React text protocol tool-call mode")


class GeneralAIRequest(BaseModel):
    input: Dict[str, Any]
    llm_config_id: Optional[int] = None
    prompt_name: Optional[str] = None
    response_model_name: Optional[Dict[str, Any]] | Optional[str] = None
    response_model_schema: Optional[Dict[str, Any]] = None  # Used to dynamically create the model
    # Sampling and timeout (optional)
    temperature: Optional[float] = Field(default=None, description="Sampling temperature 0-2, leave empty to use model default")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens to generate, leave empty to use default")
    timeout: Optional[float] = Field(default=None, description="Generation timeout (seconds), leave empty to use default")
    # Dependencies passed directly from the frontend (JSON string, e.g. {"all_entity_names":[...]})
    deps: Optional[str] = Field(default=None, description="Dependency injection data (JSON string), e.g. entity name list")
    # Whether to filter AI fields (based on x-ai-exclude marker)
    exclude_ai_fields: Optional[bool] = Field(default=True, description="Whether to filter fields marked as x-ai-exclude")

    class Config:
        extra = 'ignore'
