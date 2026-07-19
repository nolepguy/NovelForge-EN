"""Card.ReplaceFieldText node

Replaces specified text fragments in a card field (supports fuzzy matching)
"""

from typing import Any, Dict, Optional, AsyncIterator
from loguru import logger
from pydantic import BaseModel, Field

from app.services.card_service import CardService
from ...registry import register_node
from ..base import BaseNode


# ============================================================
# Input/Output Models
# ============================================================

class ReplaceTextInput(BaseModel):
    """Replace text input"""
    card_id: int = Field(..., description="Target card ID", gt=0)
    field_path: str = Field(..., description="Field path (e.g. content.overview)")
    old_text: str = Field(..., description="The old text to modify")
    new_text: str = Field("", description="New text")


class ReplaceTextOutput(BaseModel):
    """Replace text output"""
    card: Dict[str, Any] = Field(..., description="The updated card")
    replaced_count: int = Field(..., description="Number of replacements")
    success: bool = Field(..., description="Whether it succeeded")


# ============================================================
# Node Implementation
# ============================================================

@register_node
class CardReplaceTextNode(BaseNode[ReplaceTextInput, ReplaceTextOutput]):
    node_type = "Card.ReplaceFieldText"
    category = "card"
    label = "Replace Text"
    description = "Replace specified text fragments in a card field (supports fuzzy matching)"
    
    input_model = ReplaceTextInput
    output_model = ReplaceTextOutput

    async def execute(self, input_data: ReplaceTextInput) -> AsyncIterator[ReplaceTextOutput]:
        """Execute text replacement"""
        
        service = CardService(self.context.session)
        result = service.replace_field_text(
            card_id=input_data.card_id,
            field_path=input_data.field_path,
            old_text=input_data.old_text,
            new_text=input_data.new_text,
            fuzzy_match=True
        )
        
        if not result["success"]:
            raise ValueError(result.get("error", "Replacement failed"))

        # Record affected cards
        touched = self.context.variables.setdefault("touched_card_ids", [])
        if input_data.card_id not in touched:
            touched.append(input_data.card_id)
        
        # Get the latest card object to return
        updated_card = self.get_card_by_id(input_data.card_id)
        
        yield ReplaceTextOutput(
            card=updated_card,
            replaced_count=result.get("replaced_count", 0),
            success=True
        )