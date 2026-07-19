from typing import Any, Dict, Optional, AsyncIterator
from loguru import logger
from pydantic import BaseModel, Field

from app.db.models import Card
from ...registry import register_node
from ..base import BaseNode, get_card_type_by_name


class CardCreateInput(BaseModel):
    """Create card input"""
    project_id: int = Field(..., description="Project ID (must be passed explicitly)")
    card_type: str = Field(..., description="Card type name")
    title: str = Field(..., description="Card title")
    content: Dict[str, Any] = Field(default_factory=dict, description="Card content")
    parent: Optional[Dict[str, Any]] = Field(None, description="Parent card")


class CardCreateOutput(BaseModel):
    """Create card output
    
    Returns card fields directly (flat structure) for easy access by later nodes.
    """
    id: int = Field(..., description="Card ID")
    title: str = Field(..., description="Card title")
    content: Dict[str, Any] = Field(..., description="Card content")
    card_type_id: int = Field(..., description="Card type ID")
    parent_id: Optional[int] = Field(None, description="Parent card ID")


@register_node
class CardCreateNode(BaseNode[CardCreateInput, CardCreateOutput]):
    """Create card node.

    Strict constraints (for the workflow authoring Agent):
    1) `content` must be a literal dict (statically validatable); do not write the
       whole content as a string, `${...}`, or `Logic.Expression.result`.
    2) Before writing, confirm the target card type schema (field names, required
       fields, field types); fabricating fields is forbidden.
    3) If dynamic content is needed, reference known output fields at the field-value
       level, avoiding dynamic assembly of the whole object.

    Recommended flow:
    - Query the card type schema first
    - Then construct `content={...}` according to the schema
    """
    node_type = "Card.Create"
    category = "card"
    label = "Create Card"
    description = "Create a new card"
    
    input_model = CardCreateInput
    output_model = CardCreateOutput

    async def execute(self, inputs: CardCreateInput) -> AsyncIterator[CardCreateOutput]:
        """Create card node"""
        # 1. Prepare data
        title = inputs.title
        if not title:
            raise ValueError("Card title not provided")

        content = inputs.content or {}
        
        # Check the card type
        card_type = get_card_type_by_name(self.context.session, inputs.card_type)
        if not card_type:
            raise ValueError(f"Card type does not exist: {inputs.card_type}")
        
        # Use the explicitly passed project_id
        project_id = inputs.project_id
        
        parent_data = inputs.parent or {}
        parent_id = parent_data.get("id")
        
        # Use CardService to create the card
        from app.services.card_service import CardService
        from app.schemas.card import CardCreate
        
        card_service = CardService(self.context.session)
        
        try:
            card_in = CardCreate(
                title=title,
                content=content,
                card_type_id=card_type.id,
                parent_id=parent_id,
                project_id=project_id
            )
            card = card_service.create(card_in, project_id)
            
        except Exception as e:
            logger.error(f"[Card.Create] Creation failed: {e}")
            raise
        
        # Record affected cards
        touched = self.context.variables.setdefault("touched_card_ids", [])
        if card.id not in touched:
            touched.append(card.id)
        
        logger.info(
            f"[Card.Create] Created card: id={card.id}, title={card.title}, "
            f"type={inputs.card_type}"
        )
        
        yield CardCreateOutput(
            id=card.id,
            title=card.title,
            content=card.content,
            card_type_id=card.card_type_id,
            parent_id=card.parent_id
        )