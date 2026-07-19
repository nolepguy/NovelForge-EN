from typing import Any, Dict, List, Optional, AsyncIterator
from loguru import logger
from pydantic import BaseModel, Field
from sqlmodel import select

from app.db.models import Card
from ...registry import register_node
from ..base import BaseNode, get_card_type_by_name


class CardQueryInput(BaseModel):
    """Query card input"""
    card_type: Optional[str] = Field(None, description="Card type name (optional)")
    parent_id: Optional[int] = Field(None, description="Parent card ID (optional)")
    project_id: Optional[int] = Field(None, description="Project ID (optional)")
    limit: int = Field(100, description="Maximum return count")


class CardQueryOutput(BaseModel):
    """Query card output"""
    cards: List[Dict[str, Any]] = Field(..., description="Card list")


@register_node
class CardQueryNode(BaseNode[CardQueryInput, CardQueryOutput]):
    node_type = "Card.Query"
    category = "card"
    label = "Query Cards"
    description = "Query the card list by conditions"
    
    input_model = CardQueryInput
    output_model = CardQueryOutput

    async def execute(self, inputs: CardQueryInput) -> AsyncIterator[CardQueryOutput]:
        """Query cards node"""
        # Build the query
        stmt = select(Card)
        
        # Add filter conditions
        if inputs.card_type:
            card_type = get_card_type_by_name(self.context.session, inputs.card_type)
            if card_type:
                stmt = stmt.where(Card.card_type_id == card_type.id)
        
        # Parent ID
        if inputs.parent_id is not None:
            stmt = stmt.where(Card.parent_id == inputs.parent_id)
        
        # Project ID (filter if provided, otherwise do not filter)
        if inputs.project_id:
            stmt = stmt.where(Card.project_id == inputs.project_id)
        
        # Limit the count
        stmt = stmt.limit(inputs.limit)
        
        # Execute the query
        cards = list(self.context.session.exec(stmt).all())
        
        logger.info(
            f"[Card.Query] Queried cards: type={inputs.card_type}, "
            f"parent_id={inputs.parent_id}, result count={len(cards)}"
        )
        
        yield CardQueryOutput(
            cards=[
                {
                    "id": card.id,
                    "title": card.title,
                    "content": card.content,
                    "card_type_id": card.card_type_id,
                    "parent_id": card.parent_id
                }
                for card in cards
            ]
        )