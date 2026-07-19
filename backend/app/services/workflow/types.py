"""Workflow engine type definitions

Contains only the types used by the new code-based workflow system.
"""

from typing import Literal, Any, Callable, Dict
from dataclasses import dataclass, field
from datetime import datetime


# Node status type
NodeStatus = Literal["idle", "pending", "running", "success", "error", "skipped"]

# Run status type
RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "paused", "timeout"]

# Error handling policy
ErrorHandling = Literal["stop", "continue"]

# Log level
LogLevel = Literal["debug", "info", "warn", "error"]


@dataclass
class NodeMetadata:
    """Node metadata"""
    type: str
    category: str
    label: str
    description: str
    documentation: str  # Full documentation (extracted from docstring)
    input_schema: Dict[str, Any]  # JSON Schema generated from input_model
    output_schema: Dict[str, Any]  # JSON Schema generated from output_model
    executor: Callable  # Node executor class


@dataclass
class WorkflowSettings:
    """Workflow execution settings"""
    max_execution_time: int | None = None  # seconds
    timeout: int = 300  # Default node timeout (seconds)
    error_handling: ErrorHandling = "stop"
    max_concurrency: int = 5  # Maximum number of concurrent nodes
    log_level: LogLevel = "info"


@dataclass
class ExecutionContext:
    """Node execution context (simplified version, for compatibility with legacy nodes)"""
    run_id: int
    node_id: str
    node_type: str
    config: dict[str, Any]
    inputs: dict[str, Any]
    variables: dict[str, Any]  # Global variables
    node_outputs: dict[str, dict[str, Any]]  # Outputs of other nodes
    settings: WorkflowSettings
    session: Any  # SQLModel Session
    checkpoint: dict[str, Any] | None = None  # Checkpoint data (injected on recovery)
    """Checkpoint data (injected by the executor on recovery)
    
    Nodes can access the last saved checkpoint data via self.context.checkpoint.
    
    Example:
        checkpoint = getattr(self.context, 'checkpoint', None)
        if checkpoint:
            start_index = checkpoint.get('processed_count', 0)
        else:
            start_index = 0
    
    Note:
    - Only lightweight metadata is saved (index, counter, ID, etc.)
    - Business data is not saved (card content, processing results, etc.)
    - Size limit: < 10KB
    """


@dataclass
class ExecutionEvent:
    """Execution event (for SSE push)"""
    type: str  # run.started | node.started | node.progress | node.completed | node.error | run.completed | run.paused | run.cancelled
    data: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_sse(self) -> str:
        """Convert to SSE format"""
        import json
        return f"event: {self.type}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"