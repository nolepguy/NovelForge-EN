"""Workflow service module

Next-generation code-based workflow system, supporting:
- Code-based DSL editing
- Asynchronous concurrent execution
- Node type system
- Real-time status push (SSE)
- Agent orchestration

## Usage

### Defining nodes
```python
from app.services.workflow import register_node
from app.services.workflow.nodes.base import BaseNode
from pydantic import BaseModel
from typing import AsyncIterator

class MyNodeInput(BaseModel):
    value: str

class MyNodeOutput(BaseModel):
    result: str

@register_node
class MyNode(BaseNode):
    node_type = "My.Node"
    category = "custom"
    label = "My Node"
    description = "Node description"
    input_model = MyNodeInput
    output_model = MyNodeOutput
    
    async def execute(self, input_data: MyNodeInput) -> AsyncIterator[MyNodeOutput]:
        # Node processing logic
        yield MyNodeOutput(result=f"processed: {input_data.value}")
```

### Auto-discovery (call at startup)
```python
from app.services.workflow import discover_workflow_nodes
discover_workflow_nodes()
```
"""

from .registry import (
    get_registered_nodes,
    get_node_types,
    get_node_metadata,
    get_all_node_metadata,
    get_nodes_by_category,
    discover_workflow_nodes,
    register_node
)

from .engine import (
    WorkflowScheduler,
    StateManager,
    RunManager,
    AsyncExecutor
)

# Import all workflow node modules to trigger decorator registration
from . import nodes  # noqa: F401

# Import the triggers module to register event handlers
from . import triggers  # noqa: F401

__all__ = [
    # Registration
    'get_registered_nodes',
    'get_node_types',
    'get_node_metadata',
    'get_all_node_metadata',
    'get_nodes_by_category',
    'discover_workflow_nodes',
    'register_node',
    # Engine
    'WorkflowScheduler',
    'StateManager',
    'RunManager',
    'AsyncExecutor',
]