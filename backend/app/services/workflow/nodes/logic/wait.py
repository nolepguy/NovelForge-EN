"""Logic.Wait node - wait for async tasks to complete"""

from typing import Any, List, Union, AsyncIterator
from pydantic import BaseModel, Field, field_validator

from ...registry import register_node
from ..base import BaseNode


class WaitInput(BaseModel):
    """Wait node input"""
    input: Any = Field(None, description="Input data (passthrough)")
    tasks: Union[str, List[str]] = Field(
        ...,
        description="Variable names of the async tasks to wait for (single or list)",
        json_schema_extra={
            "x-component": "TaskSelect",
            "x-multiple": True
        }
    )
    
    @field_validator('tasks', mode='before')
    @classmethod
    def normalize_tasks(cls, v):
        """Convert a single task to a list"""
        if isinstance(v, str):
            return [v]
        return v


class WaitOutput(BaseModel):
    """Wait node output"""
    waited_tasks: List[str] = Field(..., description="List of waited tasks")
    count: int = Field(..., description="Number of waited tasks")


@register_node
class WaitNode(BaseNode[WaitInput, WaitOutput]):
    """Wait for async tasks to complete
    
    Used to wait for one or more async tasks to complete before continuing.
    
    Example:
        wait_result = Logic.Wait(tasks=["task_a", "task_b"])
    """
    
    node_type = "Logic.Wait"
    category = "logic"
    label = "Wait Task"
    description = "Wait for one or more async tasks to complete"
    
    input_model = WaitInput
    output_model = WaitOutput
    
    async def execute(self, inputs: WaitInput) -> AsyncIterator[WaitOutput]:
        """Execute the wait
        
        Note: the actual wait logic is handled in AsyncExecutor;
        this only returns a placeholder result.
        """
        yield WaitOutput(
            waited_tasks=inputs.tasks,
            count=len(inputs.tasks)
        )