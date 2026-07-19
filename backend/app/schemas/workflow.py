from typing import Optional, Any, List
from datetime import datetime
from pydantic import BaseModel


class WorkflowBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: Optional[bool] = True
    is_built_in: Optional[bool] = False
    version: Optional[int] = 1
    dsl_version: Optional[int] = 2  # Code-style workflow version
    definition_code: str = ""  # Workflow code
    keep_run_history: Optional[bool] = False  # Default to False (Transient)
    triggers_cache: Optional[List[dict]] = None  # Trigger cache


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    version: Optional[int] = None
    dsl_version: Optional[int] = None
    definition_code: Optional[str] = None
    keep_run_history: Optional[bool] = None


class WorkflowRead(WorkflowBase):
    id: int

    class Config:
        from_attributes = True


class WorkflowRunRead(BaseModel):
    id: int
    workflow_id: int
    definition_version: int
    status: str
    scope_json: Optional[dict] = None
    params_json: Optional[dict] = None
    idempotency_key: Optional[str] = None
    summary_json: Optional[dict] = None
    error_json: Optional[dict] = None
    created_at: Optional[datetime] = None  # Added creation time
    started_at: Optional[datetime] = None  # Added start time
    finished_at: Optional[datetime] = None  # Added finish time
    workflow: Optional["WorkflowRead"] = None  # Include basic info

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class RunRequest(BaseModel):
    scope_json: Optional[dict] = None
    params_json: Optional[dict] = None
    idempotency_key: Optional[str] = None


class CancelResponse(BaseModel):
    ok: bool
    message: Optional[str] = None


class NodeExecutionStatus(BaseModel):
    """Node execution status"""
    node_id: str
    node_type: str
    status: str  # idle | pending | running | success | error | skipped
    progress: int
    error: Optional[str] = None


class RunStatus(BaseModel):
    """Workflow run status (includes node status)"""
    run_id: int
    workflow_id: int
    status: str  # idle | pending | running | succeeded | failed | cancelled
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[dict] = None
    nodes: List[NodeExecutionStatus]


# ---- Node Types ----

class NodeTypeInfo(BaseModel):
    """Node type info"""
    type: str
    category: str
    label: str
    description: str
    input_schema: dict = {}  # Pydantic JSON Schema
    output_schema: dict = {}  # Pydantic JSON Schema


class NodeTypesResponse(BaseModel):
    """Node type list response"""
    node_types: List[NodeTypeInfo]
