"""Project creation trigger node"""
from typing import Optional
from pydantic import BaseModel, Field

from ..base import BaseNode
from ...registry import register_node


class TriggerProjectCreatedInput(BaseModel):
    """Project creation trigger input"""
    template: Optional[str] = Field(
        None,
        description="Template name (optional). Only trigger project creation for the specified template, e.g. 'snowflake'. Leave empty to match all templates"
    )


class TriggerProjectCreatedOutput(BaseModel):
    """Project creation trigger output"""
    project_id: int = Field(..., description="Project ID")
    template: Optional[str] = Field(None, description="Template name (e.g. 'snowflake')")


@register_node
class TriggerProjectCreatedNode(BaseNode):
    """Project creation trigger
    
    Triggers the workflow when a new project is created.
    
    Output fields:
        - project_id: Project ID
        - template: Template name (if a template was specified)
    
    Filter conditions:
        - template: Only trigger project creation for the specified template (optional)
    
    Example:
        # Listen to all project creations
        trigger = Trigger.ProjectCreated()
        
        # Only listen to the snowflake method template
        trigger = Trigger.ProjectCreated(template="snowflake")
        
        # Use the trigger output
        card = Card.Create(
            project_id=trigger.project_id,
            card_type="Core Blueprint",
            title="Core Blueprint"
        )
    """
    
    node_type = "Trigger.ProjectCreated"
    category = "trigger"
    label = "Project Creation Trigger"
    description = "Triggered when a new project is created"
    
    input_model = TriggerProjectCreatedInput
    output_model = TriggerProjectCreatedOutput
    
    async def execute(self, inputs: TriggerProjectCreatedInput):
        """Read trigger data from the context and output it
        
        Trigger data is injected at workflow startup via initial_context["__trigger_data__"],
        and can be accessed via self.context.variables.
        """
        # Get trigger data from the context's variables
        trigger_data = self.context.variables.get("__trigger_data__", {})
        
        yield TriggerProjectCreatedOutput(
            project_id=trigger_data.get("project_id"),
            template=trigger_data.get("template")
        )