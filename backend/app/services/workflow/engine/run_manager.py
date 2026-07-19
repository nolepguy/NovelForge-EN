"""Run manager - uniformly manages code-based workflow runs"""

import asyncio
from typing import Optional, Dict, Any
from sqlmodel import Session, select
from loguru import logger

from app.db.models import Workflow, WorkflowRun
from .state_manager import StateManager
from .runtime import workflow_runtime


class RunManager:
    """Workflow run manager
    
    Responsibilities:
    - Create and start runs
    - Manage run lifecycle
    - Provide pause/resume/cancel interfaces
    - Coordinate components
    
    Only supports the code-based workflow system.
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.state_manager = StateManager(session)
    
    def create_run(
        self,
        workflow_id: int,
        trigger_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None
    ) -> WorkflowRun:
        """Create a workflow run
        
        Args:
            workflow_id: Workflow ID
            trigger_data: Trigger data (e.g. card info), injected into scope_json
            params: Run parameters, injected into params_json
            idempotency_key: Idempotency key to prevent duplicate execution
            
        Returns:
            WorkflowRun: Run record
        """
        # Check idempotency (only checks running tasks, to avoid blocking retries of failed tasks)
        if idempotency_key:
            stmt = select(WorkflowRun).where(
                WorkflowRun.idempotency_key == idempotency_key,
                WorkflowRun.status.in_(["queued", "running"])
            )
            existing = self.session.exec(stmt).first()
            if existing:
                logger.warning(
                    f"[RunManager] Idempotency key conflict, task is already running: "
                    f"run_id={existing.id}, status={existing.status}"
                )
                return existing
        
        # Get the workflow
        workflow = self.session.get(Workflow, workflow_id)
        if not workflow:
            raise ValueError(f"Workflow does not exist: {workflow_id}")
        
        if not workflow.is_active:
            raise ValueError(f"Workflow is not active: {workflow_id}")
        
        # Create the run record
        from datetime import datetime
        run = WorkflowRun(
            workflow_id=workflow_id,
            definition_version=workflow.dsl_version,  # Use dsl_version instead of version
            status="queued",
            scope_json=trigger_data,
            params_json=params,
            idempotency_key=idempotency_key,
            created_at=datetime.now()  # Use local time instead of UTC
        )
        
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        
        # Clean up old node states for this run_id (ensure a clean start)
        self.state_manager.clear_node_states(run.id)
        
        logger.info(
            f"[RunManager] Created run: run_id={run.id}, "
            f"workflow_id={workflow_id}"
        )
        
        return run
    
    async def start_run(
        self,
        run_id: int,
        priority: int = 0
    ) -> None:
        """Start a workflow run
        
        Args:
            run_id: Run ID
            priority: Priority
        """
        run = self.session.get(WorkflowRun, run_id)
        if not run:
            raise ValueError(f"Run does not exist: {run_id}")
        
        workflow = self.session.get(Workflow, run.workflow_id)
        if not workflow:
            raise ValueError(f"Workflow does not exist: {run.workflow_id}")
        
        if workflow_runtime.is_active(run_id):
            logger.info(f"[RunManager] Run is already being scheduled: run_id={run_id}")
            return

        task = asyncio.create_task(self._execute_run_in_new_session(run_id))
        workflow_runtime.register_task(run_id, task)

    async def _execute_run_in_new_session(self, run_id: int) -> None:
        """Execute a background run in an independent database session."""
        from app.db.session import engine as db_engine

        session = Session(db_engine)
        try:
            run = session.get(WorkflowRun, run_id)
            if not run:
                logger.error(f"[RunManager] Run does not exist: run_id={run_id}")
                return

            workflow = session.get(Workflow, run.workflow_id)
            if not workflow:
                logger.error(f"[RunManager] Workflow does not exist: workflow_id={run.workflow_id}")
                return

            manager = RunManager(session)
            await manager._execute_run(run, workflow)
        finally:
            session.close()
    
    async def _execute_run(
        self,
        run: WorkflowRun,
        workflow: Workflow
    ) -> None:
        """Execute a run (internal method)"""
        from ..parser.marker_parser import WorkflowParser
        from .async_executor import AsyncExecutor
        
        run_id = run.id

        try:
            slot_status = await workflow_runtime.acquire_slot(run_id)
            if slot_status == "cancelled":
                self.state_manager.update_run_status(run_id, "cancelled")
                return
            if slot_status == "paused":
                self.state_manager.update_run_status(run_id, "paused")
                return

            # Update status to running
            self.state_manager.update_run_status(run_id, "running")

            # Parse the workflow definition
            code = workflow.definition_code or ""

            if not code:
                raise ValueError("Workflow is missing code content")

            logger.info(f"[RunManager] Parsing code-based workflow: run_id={run_id}")

            # Parse the code
            parser = WorkflowParser()
            plan = parser.parse(code)

            logger.info(f"[RunManager] Executing code-based workflow: run_id={run_id}, statement count={len(plan.statements)}")

            # Prepare the initial context (inject trigger data)
            initial_context = {}

            # Expand scope_json and params_json directly to the top level
            if run.scope_json:
                initial_context.update(run.scope_json)
            if run.params_json:
                initial_context.update(run.params_json)

            # Execute the workflow (streaming)
            executor = AsyncExecutor(
                session=self.state_manager.session,
                state_manager=self.state_manager,
                run_id=run_id
            )
            
            # Save the executor reference (for pause/resume)
            workflow_runtime.register_executor(run_id, executor)
            
            try:
                # Consume all events (trigger scenarios do not need to handle progress)
                async for event in executor.execute_stream(plan, initial_context):
                    pass  # Logging could be added here
                
                if executor.is_paused or workflow_runtime.is_pause_requested(run_id):
                    self.state_manager.update_run_status(run_id, "paused")
                    logger.info(f"[RunManager] Run paused: run_id={run_id}")
                    return

                # Get the final result
                result_context = executor.context
            finally:
                # Clean up the executor reference
                workflow_runtime.unregister_executor(run_id, executor)

            # Update status to succeeded
            self.state_manager.update_run_status(
                run_id,
                "succeeded",
                summary_json={
                    "variables": list(result_context.keys()),
                    "outputs": self.state_manager._make_json_serializable(result_context)
                }
            )

            logger.info(f"[RunManager] Run succeeded: run_id={run_id}")

        except asyncio.CancelledError:
            logger.info(f"[RunManager] Run cancelled: run_id={run_id}")
            self.state_manager.update_run_status(run_id, "cancelled")
            raise
        except Exception as e:
            error_msg = str(e)
            logger.exception(f"[RunManager] Run failed: run_id={run_id}")

            # Determine whether it timed out
            if isinstance(e, asyncio.TimeoutError):
                self.state_manager.update_run_status(run_id, "timeout")
            else:
                self.state_manager.update_run_status(run_id, "failed")
                self.state_manager.save_error(run_id, error_msg)
        finally:
            workflow_runtime.finish_run(
                run_id,
                keep_pause=workflow_runtime.is_pause_requested(run_id)
            )
    
    async def cancel_run(self, run_id: int) -> bool:
        """Cancel a run
        
        Args:
            run_id: Run ID
            
        Returns:
            Whether the cancellation succeeded
        """
        if workflow_runtime.request_cancel(run_id):
            self.state_manager.update_run_status(run_id, "cancelled")
            logger.info(f"[RunManager] Run cancelled: run_id={run_id}")
            return True

        run = self.session.get(WorkflowRun, run_id)
        if run and run.status in {"queued", "running", "paused"}:
            self.state_manager.update_run_status(run_id, "cancelled")
            logger.info(f"[RunManager] No in-process task found; marked run as cancelled: run_id={run_id}")
            return True
        
        return False
    
    async def pause_run(self, run_id: int) -> bool:
        """Pause a run
        
        Args:
            run_id: Run ID
            
        Returns:
            Whether the pause succeeded
        """
        if workflow_runtime.request_pause(run_id):
            self.state_manager.update_run_status(run_id, "paused")
            logger.info(f"[RunManager] Run paused: run_id={run_id}")
            return True
        
        logger.warning(f"[RunManager] Unable to pause run (executor does not exist): run_id={run_id}")
        return False
    
    async def resume_run(self, run_id: int) -> bool:
        """Resume a run
        
        Args:
            run_id: Run ID
            
        Returns:
            Whether the resume succeeded
        """
        run = self.session.get(WorkflowRun, run_id)
        if not run:
            logger.warning(f"[RunManager] Run does not exist: run_id={run_id}")
            return False
        
        if run.status != "paused":
            logger.warning(f"[RunManager] Run status is not paused: run_id={run_id}, status={run.status}")
            return False
        
        # Check whether the executor exists
        if workflow_runtime.request_resume(run_id):
            # Executor exists, resume directly
            self.state_manager.update_run_status(run_id, "running")
            logger.info(f"[RunManager] Run resumed: run_id={run_id}")
            return True
        else:
            # Executor does not exist (server restart), restart the run
            logger.info(f"[RunManager] Executor does not exist, restarting run: run_id={run_id}")
            workflow = self.session.get(Workflow, run.workflow_id)
            if not workflow:
                logger.error(f"[RunManager] Workflow does not exist: workflow_id={run.workflow_id}")
                return False
            
            # Restart (will automatically recover state)
            await self.start_run(run_id)
            return True
    
    def get_run_status(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Get run status
        
        Args:
            run_id: Run ID
            
        Returns:
            Run status information
        """
        run = self.session.get(WorkflowRun, run_id)
        if not run:
            return None
        
        # Get node states
        node_states = self.state_manager.get_all_node_states(run_id)
        
        return {
            "run_id": run.id,
            "workflow_id": run.workflow_id,
            "status": run.status,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "error": run.error_json,
            "nodes": [
                {
                    "node_id": ns.node_id,
                    "node_type": ns.node_type,
                    "status": ns.status,
                    "progress": int(ns.progress) if ns.progress is not None else 0,
                    "error": ns.error_message,
                    "outputs_json": ns.outputs_json
                }
                for ns in node_states
            ]
        }