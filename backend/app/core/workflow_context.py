from contextvars import ContextVar
from typing import List

# Define a context variable to store the list of workflow run IDs triggered by the current request
_workflow_runs_ctx: ContextVar[List[int]] = ContextVar("workflow_runs_ctx", default=[])

def init_workflow_context():
    """Initialize the context (called at the start of each request)"""
    _workflow_runs_ctx.set([])

def add_triggered_run_id(run_id: int):
    """Add a triggered run ID"""
    current_list = _workflow_runs_ctx.get()
    # ContextVar get returns a reference to the same list object (because default is only the initial value, after set it is new)
    # but to be safe, we should ensure we are modifying the current list
    # Note: if set was never called, get() returns that default empty list.
    # To avoid cross-request contamination (although the default is shared), the middleware must explicitly set([]).
    # Here we assume the middleware has already initialized a new empty list.
    current_list.append(run_id)

def get_triggered_run_ids() -> List[int]:
    """Get all triggered run IDs"""
    return _workflow_runs_ctx.get()

def clear_workflow_context():
    """Clear the context"""
    _workflow_runs_ctx.set([])