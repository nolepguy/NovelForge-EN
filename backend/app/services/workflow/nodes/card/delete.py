from typing import Any, Dict, AsyncIterator
from loguru import logger
from pydantic import BaseModel, Field

from ...registry import register_node
from ..base import BaseNode


class CardDeleteInput(BaseModel):
    """Delete card input"""
    card: Dict[str, Any] = Field(..., description="The card to delete")


class CardDeleteOutput(BaseModel):
    """Delete card output"""
    success: bool = Field(..., description="Whether it succeeded")


@register_node
class CardDeleteNode(BaseNode[CardDeleteInput, CardDeleteOutput]):
    node_type = "Card.Delete"
    category = "card"
    label = "Delete Card"
    description = "Delete a specified card"
    
    input_model = CardDeleteInput
    output_model = CardDeleteOutput

    async def execute(self, inputs: CardDeleteInput) -> AsyncIterator[CardDeleteOutput]:
        """Delete card node"""
        card_id = inputs.card.get("id")
        
        if not card_id:
            raise ValueError("Card ID not provided")
        
        from ..base import get_card_by_id
        card = get_card_by_id(self.context.session, card_id)
        if not card:
            raise ValueError(f"Card does not exist: {card_id}")
        
        # Delete the card
        self.context.session.delete(card)
        self.context.session.commit()
        
        logger.info(f"[Card.Delete] Deleted card: id={card_id}")
        
        yield CardDeleteOutput(success=True)