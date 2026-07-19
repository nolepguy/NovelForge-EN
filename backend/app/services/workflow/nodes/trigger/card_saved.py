"""Card save trigger node"""
from typing import Optional
from pydantic import BaseModel, Field

from ..base import BaseNode
from ...registry import register_node


class TriggerCardSavedInput(BaseModel):
    """Card save trigger input"""
    card_type: Optional[str] = Field(
        None,
        description="Card type name (optional). Only trigger card saves for the specified type, e.g. 'Core Blueprint'. Leave empty to match all types"
    )
    on_create: bool = Field(
        False,
        description="Whether to trigger on card creation"
    )
    on_update: bool = Field(
        True,
        description="Whether to trigger on card update"
    )


class TriggerCardSavedOutput(BaseModel):
    """Card save trigger output"""
    card_id: int = Field(..., description="Card ID")
    project_id: int = Field(..., description="Project ID")
    card_type: Optional[str] = Field(None, description="Card type name")
    is_created: bool = Field(..., description="Whether it is a newly created card (true=create, false=update)")


@register_node
class TriggerCardSavedNode(BaseNode):
    """Card save trigger
    
    Triggers the workflow when a card is saved (including creation and update).
    
    Output fields:
        - card_id: Card ID
        - project_id: Project ID
        - card_type: Card type name
        - is_created: Whether it is a newly created card
    
    Filter conditions:
        - card_type: Only trigger for cards of the specified type (optional)
        - on_create: Whether to trigger on creation (default false)
        - on_update: Whether to trigger on update (default true)
    
    Example:
        # Listen to all card saves
        trigger = Trigger.CardSaved()
        
        # Only listen to updates of Core Blueprint cards
        trigger = Trigger.CardSaved(
            card_type="Core Blueprint",
            on_create=false,
            on_update=true
        )
        
        # Use the trigger output
        card = Card.Get(card_id=trigger.card_id)
        
        # Extract relations
        relations = AI.ExtractRelations(
            card_id=trigger.card_id,
            project_id=trigger.project_id
        )
    """
    
    node_type = "Trigger.CardSaved"
    category = "trigger"
    label = "Card Save Trigger"
    description = "Triggered when a card is saved"
    
    input_model = TriggerCardSavedInput
    output_model = TriggerCardSavedOutput
    
    async def execute(self, inputs: TriggerCardSavedInput):
        """Read trigger data from the context and output it
        
        Trigger data is injected at workflow startup via initial_context["__trigger_data__"],
        and can be accessed via self.context.variables.
        """
        # Get trigger data from the context's variables
        trigger_data = self.context.variables.get("__trigger_data__", {})

        card_type = trigger_data.get("card_type")
        if card_type is None:
            card_type = inputs.card_type
        
        yield TriggerCardSavedOutput(
            card_id=trigger_data.get("card_id"),
            project_id=trigger_data.get("project_id"),
            card_type=card_type,
            is_created=trigger_data.get("is_created", False)
        )