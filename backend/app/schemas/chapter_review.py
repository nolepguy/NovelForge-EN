from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


QualityGate = Literal["pass", "revise", "block"]
ReviewType = Literal["chapter", "stage", "card", "custom"]
TargetType = Literal["card"]


class ReviewResultCardContent(BaseModel):
    review_target_card_id: int = Field(description="Reviewed card ID")
    review_target_title: str = Field(description="Reviewed card title")
    review_target_type: TargetType = Field(default="card", description="Reviewed target type")
    review_type: ReviewType = Field(default="card", description="Review type")
    review_profile: str = Field(description="Review profile code")
    review_target_field: Optional[str] = Field(default=None, description="Reviewed field path")
    quality_gate: QualityGate = Field(description="Review conclusion")
    review_markdown: str = Field(description="Review result body (Markdown)")
    prompt_name: str = Field(description="Name of the prompt used")
    llm_config_id: Optional[int] = Field(default=None, description="Model config used for review")
    reviewed_at: str = Field(description="Review time (ISO format string)")
    target_snapshot: Optional[str] = Field(default=None, description="Snapshot of the reviewed content")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Extended metadata")


class ReviewResultCardRead(BaseModel):
    card_id: int
    project_id: int
    title: str
    review_target_card_id: int
    review_target_title: str
    review_target_type: TargetType = "card"
    review_type: ReviewType
    review_profile: str
    review_target_field: Optional[str] = None
    quality_gate: QualityGate
    review_markdown: str
    prompt_name: str
    llm_config_id: Optional[int] = None
    reviewed_at: str
    target_snapshot: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ReviewDraftResult(BaseModel):
    review_text: str
    quality_gate: QualityGate
    review_type: ReviewType
    review_profile: str
    review_target_field: Optional[str] = None
    prompt_name: str
    llm_config_id: Optional[int] = None
    target_snapshot: Optional[str] = None
    existing_review_card_id: Optional[int] = None
    review_card_title: str
    meta: Dict[str, Any] = Field(default_factory=dict)


class ReviewRunRequest(BaseModel):
    card_id: int
    project_id: Optional[int] = None
    title: str
    target_type: TargetType = Field(default="card")
    review_type: ReviewType = Field(default="card")
    review_profile: str = Field(default="generic_card_review")
    target_field: str = Field(default="content")
    target_text: Optional[str] = None
    context_info: Optional[str] = None
    facts_info: Optional[str] = None
    content_snapshot: Optional[str] = Field(default=None, description="Optional stored snapshot of the review target")
    llm_config_id: int
    prompt_name: str = Field(default="general_review")
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[float] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class ReviewCardUpsertRequest(BaseModel):
    project_id: int
    target_card_id: int
    target_title: str
    review_type: ReviewType
    review_profile: str
    target_field: Optional[str] = None
    review_text: str
    quality_gate: QualityGate
    prompt_name: str
    llm_config_id: Optional[int] = None
    content_snapshot: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class ReviewRunResponse(BaseModel):
    review_text: str
    draft: ReviewDraftResult
