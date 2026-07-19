"""Prompt loading node

Loads a preset prompt from the database and renders template variables.
"""

from typing import Any, Dict, Optional, Union, AsyncIterator
from pydantic import BaseModel, Field
from loguru import logger
from sqlmodel import select

from ...registry import register_node
from ..base import BaseNode
from app.services.prompt_service import get_prompt, render_prompt
from app.db.models import Prompt


class PromptLoadInput(BaseModel):
    """Prompt loading input"""
    prompt_id: Union[int, str] = Field(
        ...,
        description="Prompt ID or name",
        json_schema_extra={"x-component": "PromptSelect"}
    )
    variables: Optional[Dict[str, Any]] = Field(None, description="Template variables (for rendering)")


class PromptLoadOutput(BaseModel):
    """Prompt loading output"""
    text: str = Field(..., description="Rendered prompt text")


@register_node
class PromptLoadNode(BaseNode[PromptLoadInput, PromptLoadOutput]):
    """Prompt loading node"""
    
    node_type = "Prompt.Load"
    category = "data"
    label = "Load Prompt"
    description = "Load a preset prompt template from the database"
    
    input_model = PromptLoadInput
    output_model = PromptLoadOutput

    async def execute(self, inputs: PromptLoadInput) -> AsyncIterator[PromptLoadOutput]:
        """Execute prompt loading"""
        variables = inputs.variables or {}
        
        try:
            # Get the prompt
            prompt_obj = None
            
            # Support lookup by ID or Name
            if isinstance(inputs.prompt_id, int):
                prompt_obj = get_prompt(self.context.session, inputs.prompt_id)
            else:
                # Look up by name
                statement = select(Prompt).where(Prompt.name == inputs.prompt_id)
                results = self.context.session.exec(statement)
                prompt_obj = results.first()
            
            if not prompt_obj:
                raise ValueError(f"Prompt not found: {inputs.prompt_id}")
            
            # Merge global variables
            template_vars = {
                **self.context.variables,
                **variables,
            }
            
            # Render the prompt
            rendered_text = render_prompt(prompt_obj.template, template_vars)
            
            logger.info(
                f"[Prompt.Load] Prompt loaded successfully: prompt={inputs.prompt_id}, "
                f"length={len(rendered_text)}"
            )
            
            yield PromptLoadOutput(text=rendered_text)
            
        except Exception as e:
            logger.error(f"[Prompt.Load] Failed to load prompt: {e}")
            raise