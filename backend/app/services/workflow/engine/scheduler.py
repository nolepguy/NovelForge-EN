"""Workflow scheduler - manages the workflow run queue"""

import asyncio
from typing import Dict, Optional
from loguru import logger

from app.db.models import WorkflowRun


class WorkflowScheduler:
    """Workflow scheduler
    
    Responsibilities:
    - Manage the run queue
    - Control the number of concurrent runs
    - Priority scheduling
    """
    
    def __init__(self, max_concurrent_runs: int = 5):
        self.max_concurrent_runs = max_concurrent_runs
        self.running_runs: Dict[int, asyncio.Task] = {}  # run_id -> task
        self.pending_queue: asyncio.Queue = asyncio.Queue()  # (priority, run_id)
    
    async def schedule_run(
        self,
        run_id: int,
        executor_coro,
        priority: int = 0
    ) -> None:
        """Schedule a workflow run
        
        Args:
            run_id: Run ID
            executor_coro: Executor coroutine
            priority: Priority (lower number means higher priority)
        """
        if len(self.running_runs) < self.max_concurrent_runs:
            # Start directly
            await self._start_run(run_id, executor_coro)
        else:
            # Enqueue and wait
            logger.info(
                f"[Scheduler] Run added to the waiting queue: run_id={run_id}, "
                f"priority={priority}"
            )
            await self.pending_queue.put((priority, run_id, executor_coro))
    
    async def _start_run(self, run_id: int, executor_coro) -> None:
        """Start a run"""
        logger.info(f"[Scheduler] Starting run: run_id={run_id}")
        
        # Create the task
        task = asyncio.create_task(self._run_with_cleanup(run_id, executor_coro))
        self.running_runs[run_id] = task
    
    async def _run_with_cleanup(self, run_id: int, executor_coro) -> None:
        """Execute a run and clean up"""
        try:
            await executor_coro
        finally:
            # Clean up
            if run_id in self.running_runs:
                del self.running_runs[run_id]
            
            logger.info(
                f"[Scheduler] Run completed: run_id={run_id}, "
                f"current running count={len(self.running_runs)}"
            )
            
            # Start the next run from the queue
            await self._start_next_from_queue()
    
    async def _start_next_from_queue(self) -> None:
        """Start the next run from the queue"""
        if self.pending_queue.empty():
            return
        
        if len(self.running_runs) >= self.max_concurrent_runs:
            return
        
        # Get the highest priority run
        priority, run_id, executor_coro = await self.pending_queue.get()
        logger.info(
            f"[Scheduler] Starting run from queue: run_id={run_id}, priority={priority}"
        )
        await self._start_run(run_id, executor_coro)
    
    def cancel_run(self, run_id: int) -> bool:
        """Cancel a run
        
        Args:
            run_id: Run ID
            
        Returns:
            Whether the cancellation succeeded
        """
        if run_id in self.running_runs:
            task = self.running_runs[run_id]
            task.cancel()
            logger.info(f"[Scheduler] Run cancelled: run_id={run_id}")
            return True
        return False
    
    def get_running_count(self) -> int:
        """Get the current running count"""
        return len(self.running_runs)
    
    def get_pending_count(self) -> int:
        """Get the waiting queue length"""
        return self.pending_queue.qsize()
    
    def is_running(self, run_id: int) -> bool:
        """Check whether a run is currently executing"""
        return run_id in self.running_runs