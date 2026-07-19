"""Unified execution state management

Responsibilities:
- Uniformly manage execution context, node state, and checkpoints
- Provide unified load and save interfaces
- Ensure state consistency
"""

from dataclasses import dataclass
from typing import Dict, Any, Set, Optional
from datetime import datetime
from sqlmodel import Session, select
from loguru import logger

from app.db.models import NodeExecutionState


@dataclass
class CheckpointData:
    """Checkpoint data"""
    percent: float
    message: str
    data: Optional[Dict[str, Any]]
    timestamp: datetime


@dataclass
class NodeState:
    """Node state"""
    node_id: str
    node_type: str
    status: str  # idle, running, success, error, paused
    progress: float
    outputs: Optional[Dict[str, Any]]
    checkpoint: Optional[CheckpointData]
    error: Optional[str]


class ExecutionState:
    """Unified execution state
    
    Responsibilities:
    - Manage all execution state (context, node state, checkpoints)
    - Provide unified load and save interfaces
    - Ensure state consistency
    
    Usage example:
        # Load state
        state = ExecutionState.load(run_id, session)
        
        # Update node state
        state.update_node_state(
            node_id="task_a",
            node_type="Example.Process",
            status="running",
            progress=50.0
        )
        
        # Save state
        state.save(session)
    """
    
    def __init__(self, run_id: int):
        self.run_id = run_id
        self.context: Dict[str, Any] = {}  # Execution context (variable values)
        self.completed_nodes: Set[str] = set()  # Completed nodes
        self.node_states: Dict[str, NodeState] = {}  # Node states
    
    @classmethod
    def load(cls, run_id: int, session: Session) -> 'ExecutionState':
        """Load the full state from the database
        
        Args:
            run_id: Run ID
            session: Database session
            
        Returns:
            ExecutionState instance
        """
        state = cls(run_id)
        
        # Load all node states
        stmt = select(NodeExecutionState).where(
            NodeExecutionState.run_id == run_id
        )
        db_states = session.exec(stmt).all()
        
        if not db_states:
            logger.info(f"[ExecutionState] No node states found: run_id={run_id}")
            return state
        
        logger.info(f"[ExecutionState] Loading node states: run_id={run_id}, node count={len(db_states)}")
        
        for db_state in db_states:
            # Build checkpoint data
            checkpoint = None
            if db_state.checkpoint_json:
                checkpoint = CheckpointData(
                    percent=db_state.checkpoint_json.get('percent', 0.0),
                    message=db_state.checkpoint_json.get('message', ''),
                    data=db_state.checkpoint_json.get('data'),
                    timestamp=datetime.fromisoformat(
                        db_state.checkpoint_json.get('timestamp', datetime.utcnow().isoformat())
                    )
                )
            
            # Build node state
            node_state = NodeState(
                node_id=db_state.node_id,
                node_type=db_state.node_type,
                status=db_state.status,
                progress=db_state.progress or 0.0,
                outputs=db_state.outputs_json,
                checkpoint=checkpoint,
                error=db_state.error_message
            )
            
            state.node_states[db_state.node_id] = node_state
            
            # Detailed log: record each node's state and outputs
            logger.info(
                f"[ExecutionState] Loaded node: {db_state.node_id}, "
                f"status={db_state.status}, "
                f"has_outputs={db_state.outputs_json is not None}, "
                f"outputs_keys={list(db_state.outputs_json.keys()) if db_state.outputs_json else []}"
            )
            
            # Recover completed nodes (including success and skipped)
            if db_state.status in ("success", "skipped"):
                state.completed_nodes.add(db_state.node_id)
                if db_state.outputs_json:
                    state.context[db_state.node_id] = db_state.outputs_json
                    logger.info(
                        f"[ExecutionState] Recovered node output into context: {db_state.node_id} "
                        f"(status={db_state.status}, outputs={db_state.outputs_json})"
                    )
                else:
                    logger.warning(
                        f"[ExecutionState] Node status is {db_state.status} but outputs_json is None: {db_state.node_id}"
                    )
        
        logger.info(
            f"[ExecutionState] State loading completed: run_id={run_id}, "
            f"completed={len(state.completed_nodes)} nodes, "
            f"context variables={list(state.context.keys())}"
        )
        
        return state
    
    def save(self, session: Session):
        """Save the full state to the database
        
        Saves all node states in batch, reducing database operations.
        
        Args:
            session: Database session
        """
        if not self.node_states:
            return
        
        for node_id, node_state in self.node_states.items():
            # Find or create the node state record
            stmt = select(NodeExecutionState).where(
                NodeExecutionState.run_id == self.run_id,
                NodeExecutionState.node_id == node_id
            )
            db_state = session.exec(stmt).first()
            
            if not db_state:
                db_state = NodeExecutionState(
                    run_id=self.run_id,
                    node_id=node_id,
                    node_type=node_state.node_type
                )
            
            # Update state
            db_state.status = node_state.status
            db_state.progress = node_state.progress
            db_state.outputs_json = node_state.outputs  # Save outputs for checkpoint recovery
            db_state.error_message = node_state.error
            db_state.updated_at = datetime.utcnow()
            
            # Update timestamps
            if node_state.status == "running" and not db_state.start_time:
                db_state.start_time = datetime.utcnow()
            elif node_state.status in ("success", "error", "paused"):
                if not db_state.end_time:
                    db_state.end_time = datetime.utcnow()
            
            # Update checkpoint
            if node_state.checkpoint:
                db_state.checkpoint_json = {
                    'percent': node_state.checkpoint.percent,
                    'message': node_state.checkpoint.message,
                    'data': node_state.checkpoint.data,
                    'timestamp': node_state.checkpoint.timestamp.isoformat()
                }
            
            session.add(db_state)
        
        session.commit()
        logger.debug(f"[ExecutionState] State saved: run_id={self.run_id}, node count={len(self.node_states)}")
    
    def get_node_state(self, node_id: str) -> Optional[NodeState]:
        """Get node state
        
        Args:
            node_id: Node ID
            
        Returns:
            Node state, or None if it does not exist
        """
        return self.node_states.get(node_id)
    
    def update_node_state(
        self,
        node_id: str,
        node_type: str,
        status: str,
        progress: float = 0.0,
        outputs: Optional[Dict[str, Any]] = None,
        checkpoint: Optional[CheckpointData] = None,
        error: Optional[str] = None
    ):
        """Update node state
        
        Args:
            node_id: Node ID
            node_type: Node type
            status: Status
            progress: Progress (0-100)
            outputs: Output data
            checkpoint: Checkpoint data
            error: Error message
        """
        if node_id not in self.node_states:
            # Create new state
            self.node_states[node_id] = NodeState(
                node_id=node_id,
                node_type=node_type,
                status=status,
                progress=progress,
                outputs=outputs,
                checkpoint=checkpoint,
                error=error
            )
        else:
            # Update existing state
            node_state = self.node_states[node_id]
            node_state.status = status
            node_state.progress = progress
            if outputs is not None:
                node_state.outputs = outputs
            if checkpoint is not None:
                node_state.checkpoint = checkpoint
            if error is not None:
                node_state.error = error
        
        # Update the completed list and context
        if status == "success":
            self.completed_nodes.add(node_id)
            if outputs:
                self.context[node_id] = outputs
    
    def is_completed(self, node_id: str) -> bool:
        """Check whether a node is completed
        
        Args:
            node_id: Node ID
            
        Returns:
            Whether it is completed
        """
        return node_id in self.completed_nodes
    
    def get_checkpoint(self, node_id: str) -> Optional[CheckpointData]:
        """Get a node checkpoint
        
        Args:
            node_id: Node ID
            
        Returns:
            Checkpoint data, or None if it does not exist
        """
        node_state = self.node_states.get(node_id)
        return node_state.checkpoint if node_state else None
    
    def clear_node_states(self, session: Session):
        """Clear all node states
        
        Called before starting a new run, ensuring no stale data interferes.
        
        Args:
            session: Database session
        """
        stmt = select(NodeExecutionState).where(
            NodeExecutionState.run_id == self.run_id
        )
        old_states = session.exec(stmt).all()
        
        for state in old_states:
            session.delete(state)
        
        if old_states:
            session.commit()
            logger.info(f"[ExecutionState] Cleaned up {len(old_states)} old node states: run_id={self.run_id}")
        
        # Clear in-memory state
        self.node_states.clear()
        self.completed_nodes.clear()
        self.context.clear()