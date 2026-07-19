"""
Standardized type definitions for tool call results.

Uses Pydantic to define the structure of tool return values, ensuring type safety and clear fields.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolResultStatus(str, Enum):
    """Tool execution status enum"""
    SUCCESS = "success"
    FAILED = "failed"
    WARNING = "warning"
    CONFIRMATION_REQUIRED = "confirmation_required"  # Requires user confirmation


class ToolResult(BaseModel):
    """
    Standard return format for tool calls

    All assistant tools should return this format or a subclass of it, to ensure consistency and predictability of return values.
    """
    success: bool = Field(description="Whether the operation succeeded")
    status: ToolResultStatus = Field(
        default=ToolResultStatus.SUCCESS,
        description="Operation status"
    )
    message: str = Field(description="Message for the LLM (concise description of the result)")

    # Optional fields
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Returned data (e.g. card content, list, etc.)"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message (detailed error provided on failure)"
    )

    class Config:
        use_enum_values = True  # Use enum values during serialization


class ConfirmationRequest(ToolResult):
    """
    Operation request requiring user confirmation

    Returned when a tool requires user confirmation to perform a dangerous operation.
    The frontend should detect this type and display a confirmation dialog.
    """
    success: bool = False
    status: ToolResultStatus = ToolResultStatus.CONFIRMATION_REQUIRED

    confirmation_id: str = Field(description="Unique ID of the confirmation request")
    action: str = Field(description="Name of the action to execute (e.g. 'delete_card')")
    action_params: Dict[str, Any] = Field(description="Action parameters")
    warning: Optional[str] = Field(
        default=None,
        description="Warning message (e.g. 'This operation is irreversible')"
    )

    class Config:
        use_enum_values = True


class CardOperationResult(ToolResult):
    """
    Return result of card operations

    Used for card operations such as create, update, delete, etc.
    """
    card_id: Optional[int] = Field(default=None, description="Card ID")
    card_title: Optional[str] = Field(default=None, description="Card title")
    card_type: Optional[str] = Field(default=None, description="Card type")

    # AI modification status
    needs_confirmation: Optional[bool] = Field(
        default=None,
        description="Whether user confirmation is required (used to trigger workflow)"
    )

    # For create/update operations
    current_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Current data of the card"
    )
    missing_fields: Optional[List[str]] = Field(
        default=None,
        description="List of missing required field paths"
    )
    applied: Optional[int] = Field(
        default=None,
        description="Number of successfully executed instructions"
    )
    failed: Optional[int] = Field(
        default=None,
        description="Number of failed instructions"
    )

    class Config:
        use_enum_values = True


class CardSearchResult(ToolResult):
    """Card search result"""
    total: int = Field(default=0, description="Total number of cards found")
    cards: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Card list"
    )

    class Config:
        use_enum_values = True


# Helper function: convert ToolResult to Dict
def to_dict(result: ToolResult) -> Dict[str, Any]:
    """
    Convert a ToolResult object to a dict (for LangChain tool returns)

    Args:
        result: ToolResult object

    Returns:
        Result in dict format
    """
    return result.model_dump(exclude_none=True, mode='json')
