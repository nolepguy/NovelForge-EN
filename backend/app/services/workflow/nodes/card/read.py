from typing import Any, Dict, Optional, AsyncIterator
from loguru import logger
from pydantic import BaseModel, Field

from app.db.models import Card
from ...registry import register_node
from ..base import BaseNode, get_card_type_by_name, resolve_card_reference


class CardReadInput(BaseModel):
    """Read card input"""
    target: Optional[Any] = Field("$self", description="Card reference: numeric ID, $self, $parent")
    card_id: Optional[int] = Field(None, description="Card ID (overrides target)")
    type_name: Optional[str] = Field(None, description="Card type name (optional)")


class CardReadOutput(BaseModel):
    """Read card output
    
    Returns card fields directly (flat structure) for easy access by later nodes.
    
    Access examples:
    - card.id: card ID
    - card.title: card title  
    - card.content: card content (dict)
    - card.content.get('field_name'): access a content field
    """
    id: int = Field(..., description="Card ID")
    title: str = Field(..., description="Card title")
    content: Dict[str, Any] = Field(..., description="Card content")
    card_type_id: int = Field(..., description="Card type ID")
    parent_id: Optional[int] = Field(None, description="Parent card ID")


@register_node
class CardReadNode(BaseNode[CardReadInput, CardReadOutput]):
    node_type = "Card.Read"
    category = "card"
    label = "Read Card"
    description = "Read the contents of a specified card"
    
    input_model = CardReadInput
    output_model = CardReadOutput

    async def execute(self, inputs: CardReadInput) -> AsyncIterator[CardReadOutput]:
        """Read card node"""
        # Prefer card_id
        target = inputs.card_id if inputs.card_id is not None else inputs.target
        
        # Resolve the reference
        card = None
        if isinstance(target, int):
            from ..base import get_card_by_id
            card = get_card_by_id(self.context.session, target)
        else:
            card = resolve_card_reference(
                self.context.session,
                target,
                self.context.variables.get("card_id")
            )
            
            if not card and isinstance(target, str) and target.isdigit():
                from ..base import get_card_by_id
                card = get_card_by_id(self.context.session, int(target))
        
        if not card:
            raise ValueError(f"Card not found: {target}")
        
        # Record affected cards
        touched = self.context.variables.setdefault("touched_card_ids", [])
        if card.id not in touched:
            touched.append(card.id)
        
        # Get type info
        card_type_info = None
        if inputs.type_name:
            card_type = get_card_type_by_name(self.context.session, inputs.type_name)
            if card_type:
                card_type_info = {
                    "id": card_type.id,
                    "name": card_type.name,
                    "schema": card_type.json_schema
                }
        
        logger.info(
            f"[Card.Read] Read card: id={card.id}, title={card.title}"
        )
        
        yield CardReadOutput(
            id=card.id,
            title=card.title,
            content=card.content,
            card_type_id=card.card_type_id,
            parent_id=card.parent_id
        )