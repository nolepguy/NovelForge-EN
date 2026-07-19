"""State manager - manages workflow runtime state"""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlmodel import Session, select
from loguru import logger

from app.db.models import WorkflowRun, NodeExecutionState
from ..types import NodeStatus, RunStatus


class StateManager:
    """Workflow state manager
    
    Responsibilities:
    - Persist run state
    - Manage node execution state
    - Support pause/resume
    - Provide state query interfaces
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    # ==================== Run state management ====================
    
    def update_run_status(
        self, 
        run_id: int, 
        status: RunStatus,
        **kwargs
    ) -> WorkflowRun:
        """Update run status
        
        Args:
            run_id: Run ID
            status: New status
            **kwargs: Other fields to update
        """
        run = self.session.get(WorkflowRun, run_id)
        if not run:
            raise ValueError(f"Run does not exist: {run_id}")
        
        run.status = status
        
        # Update timestamps
        if status == "running" and not run.started_at:
            run.started_at = datetime.now()  # Use local time
        elif status in ("succeeded", "failed", "cancelled", "timeout"):
            run.finished_at = datetime.now()  # Use local time
        
        # Update other fields
        for key, value in kwargs.items():
            if hasattr(run, key):
                setattr(run, key, value)
        
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        
        # logger.debug(f"[StateManager] Run status updated: run_id={run_id}, status={status}")
        return run
    
    def save_run_state(
        self, 
        run_id: int, 
        state: Dict[str, Any]
    ) -> None:
        """Save runtime state (variables, node outputs, etc.)"""
        run = self.session.get(WorkflowRun, run_id)
        if not run:
            raise ValueError(f"Run does not exist: {run_id}")
        
        # Convert state to make it JSON-serializable (e.g. convert set to list)
        serializable_state = self._make_json_serializable(state)
        
        run.state_json = serializable_state
        self.session.add(run)
        self.session.commit()
    
    def _make_json_serializable(self, obj: Any) -> Any:
        """Recursively convert objects to a JSON-serializable format
        
        Mainly handles:
        - set -> list
        - Other non-serializable types added as needed
        """
        if isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(item) for item in obj]
        else:
            return obj
    
    def get_run_state(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Get runtime state"""
        run = self.session.get(WorkflowRun, run_id)
        if not run:
            return None
        return run.state_json or {}
    
    def save_error(
        self, 
        run_id: int, 
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Save error information"""
        run = self.session.get(WorkflowRun, run_id)
        if not run:
            return
        
        run.error_json = {
            "message": error_message,
            "details": error_details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        self.session.add(run)
        self.session.commit()
    
    # ==================== Node state management ====================
    
    def create_node_state(
        self,
        run_id: int,
        node_id: str,
        node_type: str
    ) -> NodeExecutionState:
        """Create or get a node execution state record (upsert)"""
        # First try to find an existing record
        stmt = select(NodeExecutionState).where(
            NodeExecutionState.run_id == run_id,
            NodeExecutionState.node_id == node_id
        )
        state = self.session.exec(stmt).first()

        if state:
            # If it already exists, reset the state (for re-execution)
            state.node_type = node_type
            state.status = "idle"
            state.start_time = None
            state.end_time = None
            state.progress = 0
            state.error_message = None
            state.inputs_json = None
            state.outputs_json = None
            state.logs_json = None
            state.updated_at = datetime.utcnow()
            logger.info(f"[StateManager] Reset node state: run_id={run_id}, node_id={node_id}")
        else:
            # If it does not exist, create a new record
            state = NodeExecutionState(
                run_id=run_id,
                node_id=node_id,
                node_type=node_type,
                status="idle"
            )
            logger.info(f"[StateManager] Created node state: run_id={run_id}, node_id={node_id}")

        self.session.add(state)
        self.session.commit()
        self.session.refresh(state)
        return state
    
    def update_node_status(
        self,
        run_id: int,
        node_id: str,
        status: NodeStatus,
        **kwargs
    ) -> Optional[NodeExecutionState]:
        """Update node status
        
        Args:
            run_id: Run ID
            node_id: Node ID
            status: New status
            **kwargs: Other fields to update (e.g. progress, error_message)
        """
        # Find the node state record
        stmt = select(NodeExecutionState).where(
            NodeExecutionState.run_id == run_id,
            NodeExecutionState.node_id == node_id
        )
        state = self.session.exec(stmt).first()
        
        if not state:
            logger.warning(
                f"[StateManager] Node state record does not exist: run_id={run_id}, node_id={node_id}"
            )
            return None
        
        state.status = status
        state.updated_at = datetime.utcnow()
        
        # Update timestamps
        if status == "running" and not state.start_time:
            state.start_time = datetime.utcnow()
        elif status in ("success", "error", "skipped"):
            state.end_time = datetime.utcnow()
        
        # Update other fields
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
        
        self.session.add(state)
        self.session.commit()
        self.session.refresh(state)
        
        return state
    
    def save_node_inputs(
        self,
        run_id: int,
        node_id: str,
        inputs: Dict[str, Any]
    ) -> None:
        """Save node inputs"""
        stmt = select(NodeExecutionState).where(
            NodeExecutionState.run_id == run_id,
            NodeExecutionState.node_id == node_id
        )
        state = self.session.exec(stmt).first()
        
        if state:
            state.inputs_json = inputs
            self.session.add(state)
            self.session.commit()
    
    def save_node_outputs(
        self,
        run_id: int,
        node_id: str,
        outputs: Dict[str, Any]
    ) -> None:
        """Save node outputs"""
        stmt = select(NodeExecutionState).where(
            NodeExecutionState.run_id == run_id,
            NodeExecutionState.node_id == node_id
        )
        state = self.session.exec(stmt).first()
        
        if state:
            state.outputs_json = outputs
            self.session.add(state)
            self.session.commit()
    
    def add_node_log(
        self,
        run_id: int,
        node_id: str,
        level: str,
        message: str,
        **kwargs
    ) -> None:
        """Add a node log"""
        stmt = select(NodeExecutionState).where(
            NodeExecutionState.run_id == run_id,
            NodeExecutionState.node_id == node_id
        )
        state = self.session.exec(stmt).first()
        
        if state:
            logs = state.logs_json or []
            logs.append({
                "level": level,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                **kwargs
            })
            state.logs_json = logs
            self.session.add(state)
            self.session.commit()
    
    def get_node_state(
        self,
        run_id: int,
        node_id: str
    ) -> Optional[NodeExecutionState]:
        """Get node state"""
        stmt = select(NodeExecutionState).where(
            NodeExecutionState.run_id == run_id,
            NodeExecutionState.node_id == node_id
        )
        return self.session.exec(stmt).first()
    
    def get_all_node_states(self, run_id: int) -> list[NodeExecutionState]:
        """Get all node states of a run"""
        stmt = select(NodeExecutionState).where(
            NodeExecutionState.run_id == run_id
        )
        return list(self.session.exec(stmt).all())
    
    def clear_node_states(self, run_id: int) -> None:
        """Clear all node states of a run
        
        Called before starting a new run, ensuring no stale data interferes
        """
        stmt = select(NodeExecutionState).where(
            NodeExecutionState.run_id == run_id
        )
        old_states = self.session.exec(stmt).all()
        
        for state in old_states:
            self.session.delete(state)
        
        if old_states:
            self.session.commit()
            logger.info(f"[StateManager] Cleaned up {len(old_states)} old node states: run_id={run_id}")

    # ==================== Checkpoint management ====================
    
    def save_checkpoint(
        self,
        run_id: int,
        node_id: str,
        percent: float,
        message: str = "",
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Save a node checkpoint
        
        Args:
            run_id: Run ID
            node_id: Node ID (variable name)
            percent: Progress percentage (0-100)
            message: Progress message
            data: Checkpoint data (lightweight metadata, < 10KB)
        
        Note:
        - data only saves position info (index, counter, ID, etc.)
        - Business data is not saved (card content, processing results, etc.)
        - Size limit: < 10KB
        """
        # Validate data size
        if data:
            import json
            data_size = len(json.dumps(data))
            if data_size > 10 * 1024:  # 10KB
                logger.warning(
                    f"[Checkpoint] Checkpoint data too large: {node_id}, "
                    f"size={data_size} bytes, recommended < 10KB"
                )
        
        # Build the checkpoint JSON
        checkpoint_json = {
            "percent": percent,
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Find or create NodeExecutionState
        stmt = select(NodeExecutionState).where(
            NodeExecutionState.run_id == run_id,
            NodeExecutionState.node_id == node_id
        )
        state = self.session.exec(stmt).first()
        
        if not state:
            # Create a new state (usually should not happen, but for robustness)
            logger.warning(
                f"[Checkpoint] Node state does not exist, creating new state: run_id={run_id}, node_id={node_id}"
            )
            state = NodeExecutionState(
                run_id=run_id,
                node_id=node_id,
                node_type="unknown",
                status="running",
                progress=percent,
                checkpoint_json=checkpoint_json
            )
            self.session.add(state)
        else:
            # Update the existing state
            state.progress = percent
            state.checkpoint_json = checkpoint_json
            state.updated_at = datetime.utcnow()
        
        self.session.commit()
        logger.debug(
            f"[Checkpoint] Saved: {node_id}, "
            f"progress={percent}%, message={message}"
        )
    
    def load_checkpoint(
        self,
        run_id: int,
        node_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load a node checkpoint
        
        Args:
            run_id: Run ID
            node_id: Node ID (variable name)
            
        Returns:
            Checkpoint data, format:
            {
                "percent": 50.0,
                "message": "Processed 30/60",
                "data": {"processed_count": 30},
                "timestamp": "2026-02-04T10:30:00"
            }
            Returns None if it does not exist
        """
        stmt = select(NodeExecutionState).where(
            NodeExecutionState.run_id == run_id,
            NodeExecutionState.node_id == node_id
        )
        state = self.session.exec(stmt).first()
        
        if state and state.checkpoint_json:
            logger.debug(
                f"[Checkpoint] Loaded: {node_id}, "
                f"progress={state.checkpoint_json.get('percent')}%"
            )
            return state.checkpoint_json
        
        return None