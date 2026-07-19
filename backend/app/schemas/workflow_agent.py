from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WorkflowAgentMode(str, Enum):
    SUGGEST = "suggest"
    AUTO_APPLY = "auto_apply"


class WorkflowAgentChatRequest(BaseModel):
    workflow_id: int = Field(description="Currently edited workflow ID")
    llm_config_id: int = Field(description="LLM config ID used for the conversation")
    user_prompt: str = Field(default="", description="User input")
    mode: WorkflowAgentMode = Field(default=WorkflowAgentMode.SUGGEST, description="Working mode")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")

    temperature: Optional[float] = Field(default=None, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, description="Max output tokens")
    timeout: Optional[float] = Field(default=None, description="Timeout (seconds)")
    thinking_enabled: Optional[bool] = Field(default=None, description="Whether to enable reasoning output")
    react_mode_enabled: Optional[bool] = Field(default=None, description="Whether to enable React text protocol mode")
    history_messages: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Conversation history passed in by the frontend (simplified), each item contains role/content",
    )
    pending_code: Optional[str] = Field(
        default=None,
        description="Candidate workflow code corresponding to the currently unapplied patch on the frontend (if any)",
    )


class WorkflowPatchOp(BaseModel):
    op: str = Field(description="Patch operation type")
    target_node: Optional[str] = Field(default=None, description="Target node variable name")
    new_code: Optional[str] = Field(default=None, description="Entire workflow code (used when replace_code)")
    new_block: Optional[str] = Field(default=None, description="Inserted new node block")
    new_meta: Optional[Dict[str, Any]] = Field(default=None, description="Updated node metadata fields")
    new_call: Optional[str] = Field(default=None, description="Updated node call expression")
    old_name: Optional[str] = Field(default=None, description="Old variable before rename")
    new_name: Optional[str] = Field(default=None, description="New variable after rename")
    reason: Optional[str] = Field(default=None, description="Operation reason")


class WorkflowPatchRequest(BaseModel):
    base_revision: str = Field(description="Patch baseline revision")
    patch_ops: List[WorkflowPatchOp] = Field(default_factory=list, description="Patch operation list")
    dry_run: bool = Field(default=False, description="Whether to only preview without persisting")


class WorkflowPatchResponse(BaseModel):
    success: bool
    workflow_id: int
    base_revision: str
    new_revision: Optional[str] = None
    applied_ops: int = 0
    changed_nodes: List[str] = Field(default_factory=list)
    diff: str = ""
    new_code: str = ""
    parse_result: Dict[str, Any] = Field(default_factory=dict)
    validation: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
