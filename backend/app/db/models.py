
from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from sqlalchemy import UniqueConstraint
import sqlalchemy as sa
from typing import Optional, List, Any
from datetime import datetime


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None

    cards: List["Card"] = Relationship(back_populates="project", sa_relationship_kwargs={"cascade": "all, delete-orphan"})



class LLMConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True)
    display_name: Optional[str] = None
    model_name: str
    api_base: Optional[str] = None
    api_key: str
    # Must include server_default here, otherwise the startup auto-add-column logic
    # will not consider it a "safe appended column". A Python default alone is not
    # enough; legacy databases need a database-side default during ALTER TABLE to
    # backfill historical rows.
    api_protocol: str = Field(
        default="chat_completions",
        sa_column=Column(sa.String, nullable=False, server_default="chat_completions"),
    )
    custom_request_path: Optional[str] = None
    models_path: Optional[str] = None
    user_agent: Optional[str] = None
    base_url: Optional[str] = None  # Legacy compatibility field; new implementations converge on api_base
    # Statistics and quota (-1 means unlimited) — also set server_default at the DB layer so Alembic auto-includes it
    token_limit: int = Field(
        default=-1,
        sa_column=Column(sa.Integer, nullable=False, server_default='-1')
    )
    call_limit: int = Field(
        default=-1,
        sa_column=Column(sa.Integer, nullable=False, server_default='-1')
    )
    used_tokens_input: int = Field(
        default=0,
        sa_column=Column(sa.Integer, nullable=False, server_default='0')
    )
    used_tokens_output: int = Field(
        default=0,
        sa_column=Column(sa.Integer, nullable=False, server_default='0')
    )
    used_calls: int = Field(
        default=0,
        sa_column=Column(sa.Integer, nullable=False, server_default='0')
    )
    # RPM/TPM are placeholders only, not implemented yet
    rpm_limit: int = Field(
        default=-1,
        sa_column=Column(sa.Integer, nullable=False, server_default='-1')
    )
    tpm_limit: int = Field(
        default=-1,
        sa_column=Column(sa.Integer, nullable=False, server_default='-1')
    )
    capability_summary: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    recommended_assistant_mode: str = Field(
        default="auto",
        sa_column=Column(sa.String, nullable=False, server_default="auto"),
    )
    disable_stream: bool = Field(
        default=False,
        sa_column=Column(sa.Boolean, nullable=False, server_default=sa.false()),
    )
    capability_last_checked_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(sa.DateTime, nullable=True),
    )


class Prompt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    template: str
    version: int = 1
    built_in: bool = Field(default=False)



class CardType(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    # Compatible with legacy model names (e.g. CharacterCard/SceneCard); if empty, defaults to name
    model_name: Optional[str] = Field(default=None, index=True)
    description: Optional[str] = None
    # Type built-in structure (JSON Schema)
    json_schema: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    # Type-level default AI params (model ID / prompt / sampling, etc.)
    ai_params: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    editor_component: Optional[str] = None  # e.g., 'NovelEditor' for custom UI
    is_ai_enabled: bool = Field(default=True)
    is_singleton: bool = Field(default=False)  # e.g., only one 'Synopsis' card per project
    built_in: bool = Field(default=False)
    # Card-type-level default context injection template
    default_ai_context_template: Optional[str] = Field(default=None)
    default_ai_context_template_review: Optional[str] = Field(default=None)
    # UI layout (optional), used by the frontend SectionedForm
    ui_layout: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    cards: List["Card"] = Relationship(back_populates="card_type")


class Card(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    # Compatible with legacy model names; if empty, follows the type's model_name or type name
    model_name: Optional[str] = Field(default=None, index=True)
    content: Any = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)

    # Allow instance-level custom structure; if empty, follows the type
    json_schema: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    # Instance-level AI params; if empty, follows the type
    ai_params: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Self-referential relationship, used for tree structures
    parent_id: Optional[int] = Field(default=None, foreign_key="card.id")
    parent: Optional["Card"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "[Card.id]"}
    )
    children: List["Card"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={
            "cascade": "all, delete, delete-orphan",
            "single_parent": True,
        },
    )

    # Project foreign key
    project_id: int = Field(foreign_key="project.id")
    project: "Project" = Relationship(back_populates="cards")

    # Card type foreign key
    card_type_id: int = Field(foreign_key="cardtype.id")
    card_type: "CardType" = Relationship(back_populates="cards")

    # Used for card sorting, for ordering under the same parent
    display_order: int = Field(default=0)
    ai_context_template: Optional[str] = Field(default=None)
    ai_context_template_review: Optional[str] = Field(default=None)
    
    # AI modification status flags
    ai_modified: bool = Field(default=False)  # Whether modified by AI
    needs_confirmation: bool = Field(default=False)  # Whether user confirmation is needed (used to trigger workflow)
    last_modified_by: Optional[str] = Field(default=None)  # Last modifier: 'user' | 'ai' | None

# Foreshadow registry table
class ForeshadowItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    chapter_id: Optional[int] = Field(default=None)  # Chapter card ID or chapter ID
    title: str
    type: str = Field(default='other', index=True)  # goal | item | person | other
    note: Optional[str] = None
    status: str = Field(default='open', index=True)  # open | resolved
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    resolved_at: Optional[datetime] = None


# Knowledge base model
class Knowledge(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    content: str
    built_in: bool = Field(default=False)


# Workflow system
class Workflow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    dsl_version: int = Field(default=2)  # DSL version: 2=code-style workflow
    is_built_in: bool = Field(default=False)
    is_active: bool = Field(default=True)
    
    # Workflow definition (code-style)
    definition_code: str = Field(default="")  # Workflow code
    
    # Workflow template
    is_template: bool = Field(default=False)
    template_category: Optional[str] = None  # e.g.: "Content Generation", "Data Processing"
    
    # Run data retention policy
    # True: long-term retention (subject to the global validity period)
    # False: short-term retention (only for the frontend to view results, auto-cleaned afterwards)
    keep_run_history: bool = Field(default=False)
    
    # Trigger cache (optimizes performance, avoids querying the WorkflowTrigger table separately)
    triggers_cache: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON))
    """Trigger cache (auto-extracted from code)
    
    Structure:
    [
        {
            "trigger_on": "onsave",           # Trigger event type
            "card_type_name": "Chapter",      # Card type (optional)
            "filter_json": {                  # Filter config (optional)
                "events": ["create", "update"],
                "conditions": [...]
            }
        },
        ...
    ]
    
    Advantages:
    - 100x startup performance improvement (5ms vs 500ms)
    - Avoids data redundancy and sync issues
    - Code is the single source of truth
    """
    
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.now, nullable=False)

    # Relations
    runs: List["WorkflowRun"] = Relationship(back_populates="workflow", sa_relationship_kwargs={
        "cascade": "all, delete-orphan"
    })


class WorkflowRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="workflow.id")
    workflow: Workflow = Relationship(back_populates="runs")

    definition_version: int = Field(default=1)
    # queued | running | succeeded | failed | cancelled | paused | timeout
    status: str = Field(default="queued", index=True)
    scope_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    params_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    idempotency_key: Optional[str] = Field(default=None, index=True)
    
    # Execution status
    state_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))  # Runtime state (variables, node outputs, etc.)
    error_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))  # Error info
    
    # Time control
    max_execution_time: Optional[int] = None  # Seconds; None means unlimited
    
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    summary_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    # Relations
    node_states: List["NodeExecutionState"] = Relationship(back_populates="run", sa_relationship_kwargs={
        "cascade": "all, delete-orphan"
    })


class NodeExecutionState(SQLModel, table=True):
    """Node execution state table - used to track each node's execution in detail"""
    __tablename__ = "nodeexecutionstate"
    __table_args__ = (
        # Add a unique constraint: the same node in the same run can only have one record
        UniqueConstraint('run_id', 'node_id', name='uq_run_node'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="workflowrun.id", index=True)
    run: WorkflowRun = Relationship(back_populates="node_states")

    node_id: str = Field(index=True)  # Node ID (from DSL)
    node_type: str  # Node type

    # Execution status: idle | pending | running | success | error | skipped
    status: str = Field(default="idle", index=True)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    progress: int = Field(default=0)  # 0-100
    
    # Node output (used for checkpoint resume)
    outputs_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    """Node output data (used for execution recovery)
    
    When a workflow is resumed after being paused, the outputs of completed nodes
    need to be read from here so that subsequent nodes can access the results
    of their predecessors.
    
    Example:
    {
        "project_id": 123,
        "card_id": 456,
        "result": {...}
    }
    """
    
    # Error info (simplified)
    error_message: Optional[str] = None
    
    # Checkpoint data (new)
    checkpoint_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    """Checkpoint data (lightweight metadata)
    
    Structure:
    {
        "percent": 50.0,                    # Progress percentage
        "message": "Processed 30/60",       # Progress message
        "data": {                           # Node custom data (optional)
            "processed_count": 30,          # ✅ Lightweight: counter
            "last_item_id": "item_30",      # ✅ Lightweight: identifier
            "current_batch": 3              # ✅ Lightweight: batch number
        },
        "timestamp": "2026-02-04T10:30:00"  # Save time
    }
    
    Notes:
    - The data field only stores positional info, not business data
    - Size limit: < 10KB
    - Used for checkpoint resume; nodes access it via context.checkpoint
    """
    
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.now, nullable=False)

class KGRelation(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("project_id", "source", "target", "kind_en", name="uq_kg_relation_key"),
        sa.Index("ix_kg_relation_project_source", "project_id", "source"),
        sa.Index("ix_kg_relation_project_target", "project_id", "target"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    source: str = Field(index=True)
    target: str = Field(index=True)
    kind_en: str = Field(index=True)
    kind_cn: str = Field(default="Other")
    fact: Optional[str] = None
    a_to_b_addressing: Optional[str] = None
    b_to_a_addressing: Optional[str] = None
    recent_dialogues: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    recent_event_summaries: List[dict] = Field(default_factory=list, sa_column=Column(JSON))
    stance: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.now, nullable=False)
