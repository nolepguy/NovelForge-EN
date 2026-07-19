"""Context assembly node

Reuses ContextService to provide context assembly capability for workflows.
"""

from typing import Any, Dict, List, Optional, AsyncIterator
from pydantic import BaseModel, Field
from loguru import logger

from ...registry import register_node
from ..base import BaseNode
from app.services.context_service import assemble_context, ContextAssembleParams


class ContextAssembleInput(BaseModel):
    """Context assembly input"""
    
    project_id: int = Field(..., description="Project ID (must be passed explicitly)")
    participants: List[str] = Field(
        default_factory=list,
        description="Participant list (character/location names)"
    )


class ContextAssembleOutput(BaseModel):
    """Context assembly output"""
    
    context_text: str = Field(..., description="Formatted context text")
    context_data: Dict[str, Any] = Field(default_factory=dict, description="Structured context data")


# Unverified, hidden for now
# @register_node
class ContextAssembleNode(BaseNode):
    """Context assembly node"""
    
    node_type = "Context.Assemble"
    category = "context"
    label = "Assemble Context"
    description = "Extract the facts subgraph from the knowledge graph to provide structured context for the LLM"
    input_model = ContextAssembleInput
    output_model = ContextAssembleOutput

    async def execute(self, input_data: ContextAssembleInput) -> AsyncIterator[ContextAssembleOutput]:
        """Execute context assembly"""
        
        # Use the explicitly passed project ID
        project_id = input_data.project_id
        
        # Build parameters
        params = ContextAssembleParams(
            project_id=project_id,
            participants=input_data.participants,
            volume_number=None,
            chapter_number=None,
            current_draft_tail=None,
        )
        
        # Call the context service
        result = assemble_context(self.context.session, params)
        
        logger.info(
            f"[Context.Assemble] context assembled successfully: project_id={project_id}, "
            f"participants={input_data.participants}"
        )
        
        yield ContextAssembleOutput(
            context_text=result.facts_subgraph,
            context_data=result.facts_structured or {},
        )
