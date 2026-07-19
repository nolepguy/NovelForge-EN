"""Card update node"""

from typing import Any, Dict, Optional, AsyncIterator
from pydantic import BaseModel, Field
from sqlalchemy.orm.attributes import flag_modified

from app.services.workflow.nodes.base import BaseNode
from app.services.workflow.registry import register_node


class CardUpdateInput(BaseModel):
    """Card update input"""
    card_id: Optional[int] = Field(None, description="Card ID (optional, can be obtained from context)")
    content_merge: Dict[str, Any] = Field(
        default_factory=dict,
        description="Content to merge (deep-merged into the existing content)"
    )
    title: Optional[str] = Field(
        None,
        description="New title (optional)"
    )


class CardUpdateOutput(BaseModel):
    """Card update output"""
    card_id: int = Field(..., description="Updated card ID")
    success: bool = Field(True, description="Whether the update succeeded")


@register_node
class CardUpdateNode(BaseNode):
    """Card update node
    
    Updates an existing card's content or title.
    Supports deep-merging content and does not overwrite unspecified fields.
    
    Examples:
    1. Clear a list field: content_merge={"items": []}
    2. Update a nested field: content_merge={"world_view": {"social_system": {"major_power_camps": []}}}
    3. Update the title: title="New Title"

    Strict constraints (for the workflow authoring Agent):
    - `content_merge` must be a statically validatable literal dict.
    - Writing the whole `content_merge` as `${...}`, `$expr.result`, or a string
      concatenation result is forbidden.
    - Updated fields must conform to the target card schema; fields not in the schema
      must not be written.

    It is recommended to determine the target card type schema first, then construct `content_merge`.
    """
    
    node_type = "Card.Update"
    category = "card"
    label = "Update Card"
    description = "Update an existing card's content or title"
    
    input_model = CardUpdateInput
    output_model = CardUpdateOutput
    
    async def execute(self, input_data: CardUpdateInput) -> AsyncIterator[CardUpdateOutput]:
        """Execute card update"""
        from sqlmodel import select
        from app.db.models import Card
        
        # Determine the card ID
        card_id = input_data.card_id
        if not card_id:
            raise ValueError("card_id must be provided")
        
        # Get the card
        card = self.context.session.get(Card, card_id)
        if not card:
            raise ValueError(f"Card does not exist: card_id={card_id}")
        
        # Update the title
        if input_data.title:
            card.title = input_data.title
        
        # Deep-merge content
        if input_data.content_merge:
            card.content = self._deep_merge(card.content or {}, input_data.content_merge)
            flag_modified(card, "content")
        
        # Save
        self.context.session.add(card)
        self.context.session.commit()
        self.context.session.refresh(card)
        
        yield CardUpdateOutput(
            card_id=card.id,
            success=True
        )
    
    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """Deep-merge dicts
        
        Args:
            base: Base dict
            update: Update dict
            
        Returns:
            The merged dict
        """
        result = base.copy()
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dicts
                result[key] = self._deep_merge(result[key], value)
            else:
                # Overwrite directly
                result[key] = value
        
        return result