from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator
from datetime import datetime


# --- CardType Schemas ---

class CardTypeBase(BaseModel):
    name: str
    model_name: Optional[str] = None
    description: Optional[str] = None
    # Built-in structure of the type (JSON Schema)
    json_schema: Optional[Dict[str, Any]] = None
    # Default AI parameters for the type
    ai_params: Optional[Dict[str, Any]] = None
    editor_component: Optional[str] = None
    is_ai_enabled: bool = Field(default=False)
    is_singleton: bool = Field(default=False)
    # Default AI context injection template (type level)
    default_ai_context_template: Optional[str] = None
    default_ai_context_template_review: Optional[str] = None
    # UI layout (optional)
    ui_layout: Optional[Dict[str, Any]] = None


class CardTypeCreate(CardTypeBase):
    pass


class CardTypeUpdate(BaseModel):
    name: Optional[str] = None
    model_name: Optional[str] = None
    description: Optional[str] = None
    json_schema: Optional[Dict[str, Any]] = None
    ai_params: Optional[Dict[str, Any]] = None
    editor_component: Optional[str] = None
    is_ai_enabled: Optional[bool] = None
    is_singleton: Optional[bool] = None
    default_ai_context_template: Optional[str] = None
    default_ai_context_template_review: Optional[str] = None
    ui_layout: Optional[Dict[str, Any]] = None


class CardTypeRead(CardTypeBase):
    id: int
    built_in: bool = False


# --- Card Schemas ---

class CardBase(BaseModel):
    title: str
    model_name: Optional[str] = None
    content: Optional[Dict[str, Any]] = Field(default_factory=dict)
    parent_id: Optional[int] = None
    card_type_id: int
    # Instance optional custom structure; empty means follow the type
    json_schema: Optional[Dict[str, Any]] = None
    # Instance AI parameters; empty means follow the type
    ai_params: Optional[Dict[str, Any]] = None
    ai_context_template: Optional[str] = None
    ai_context_template_review: Optional[str] = None


class CardCreate(CardBase):
    pass


class CardUpdate(BaseModel):
    title: Optional[str] = None
    model_name: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    parent_id: Optional[int] = None
    display_order: Optional[int] = None
    ai_context_template: Optional[str] = None
    ai_context_template_review: Optional[str] = None
    json_schema: Optional[Dict[str, Any]] = None
    ai_params: Optional[Dict[str, Any]] = None
    # AI modification tracking fields (frontend needs to clear needs_confirmation)
    needs_confirmation: Optional[bool] = None


class CardRead(CardBase):
    id: int
    project_id: int
    created_at: datetime
    display_order: int
    card_type: CardTypeRead
    # Specific card can override the type default template
    ai_context_template: Optional[str] = None
    ai_context_template_review: Optional[str] = None
    # AI modification tracking fields
    ai_modified: bool = False
    needs_confirmation: bool = False
    last_modified_by: Optional[str] = None


# --- Operations ---

class CardCopyOrMoveRequest(BaseModel):
    target_project_id: int
    parent_id: Optional[int] = None


class CardOrderItem(BaseModel):
    """Sort order info for a single card"""
    card_id: int
    display_order: int
    parent_id: Optional[int] = None


class CardBatchReorderRequest(BaseModel):
    """Batch update card sort order request"""
    updates: List[CardOrderItem] = Field(description="List of card sort orders to update")


# --- Export ---

CardExportScope = Literal["all", "single", "type"]
CardExportFormat = Literal["txt", "md", "json"]


class CardExportRequest(BaseModel):
    """Project card export request"""

    scope: CardExportScope = Field(default="all", description="Export scope")
    card_id: Optional[int] = Field(default=None, description="Card ID when exporting a single card")
    card_type_id: Optional[int] = Field(default=None, description="Card type ID when exporting by type")
    format: CardExportFormat = Field(default="txt", description="Export format")

    @model_validator(mode="after")
    def validate_scope_fields(self):
        if self.scope == "single" and self.card_id is None:
            raise ValueError("card_id must be provided when scope=single")
        if self.scope == "type" and self.card_type_id is None:
            raise ValueError("card_type_id must be provided when scope=type")
        return self
