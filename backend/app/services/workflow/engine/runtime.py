"""Shared workflow runtime state.

This module only holds in-process run control state and does not own a database Session.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

from loguru import logger


@dataclass
class _LoopBoundTask:
    task: asyncio.Task
    loop: asyncio.AbstractEventLoop


@dataclass
class _LoopBoundExecutor:
    executor: Any
    loop: asyncio.AbstractEventLoop


class WorkflowRuntime:
    """Cross-request shared workflow run controller."""

    def __init__(self, max_concurrent_runs: int = 5):
        self.max_concurrent_runs = max_concurrent_runs
        self._semaphore = threading.BoundedSemaphore(max_concurrent_runs)
        self._lock = threading.RLock()
        self._tasks: Dict[int, _LoopBoundTask] = {}
        self._executors: Dict[int, _LoopBoundExecutor] = {}
        self._acquired_runs: set[int] = set()
        self._pending_runs: set[int] = set()
        self._cancel_requested: set[int] = set()
        self._pause_requested: set[int] = set()

    def register_task(self, run_id: int, task: asyncio.Task | None = None) -> None:
        """Register the currently running asyncio task."""
        loop = asyncio.get_running_loop()
        task = task or asyncio.current_task()
        if task is None:
            logger.warning(f"[WorkflowRuntime] Unable to register task: run_id={run_id}")
            return

        with self._lock:
            self._tasks[run_id] = _LoopBoundTask(task=task, loop=loop)

        def _cleanup(done_task: asyncio.Task) -> None:
            with self._lock:
                current = self._tasks.get(run_id)
                if current and current.task is done_task:
                    self._tasks.pop(run_id, None)

        task.add_done_callback(_cleanup)
        logger.debug(f"[WorkflowRuntime] Task registered: run_id={run_id}")

    def unregister_task(self, run_id: int) -> None:
        with self._lock:
            self._tasks.pop(run_id, None)

    async def acquire_slot(self, run_id: int) -> str:
        """Wait for a global concurrency slot.

        Returns:
            acquired | cancelled | paused
        """
        with self._lock:
            if run_id in self._cancel_requested:
                return "cancelled"
            if run_id in self._pause_requested:
                return "paused"
            self._pending_runs.add(run_id)

        try:
            while True:
                with self._lock:
                    if run_id in self._cancel_requested:
                        return "cancelled"
                    if run_id in self._pause_requested:
                        return "paused"

                if self._semaphore.acquire(blocking=False):
                    with self._lock:
                        self._pending_runs.discard(run_id)
                        self._acquired_runs.add(run_id)
                    logger.info(
                        f"[WorkflowRuntime] Acquired run slot: run_id={run_id}, "
                        f"running={len(self._acquired_runs)}/{self.max_concurrent_runs}"
                    )
                    return "acquired"

                await asyncio.sleep(0.1)
        finally:
            with self._lock:
                self._pending_runs.discard(run_id)

    def release_slot(self, run_id: int) -> None:
        should_release = False
        with self._lock:
            if run_id in self._acquired_runs:
                self._acquired_runs.remove(run_id)
                should_release = True

        if should_release:
            self._semaphore.release()
            logger.info(
                f"[WorkflowRuntime] Released run slot: run_id={run_id}, "
                f"running={len(self._acquired_runs)}/{self.max_concurrent_runs}"
            )

    def register_executor(self, run_id: int, executor: Any) -> None:
        loop = asyncio.get_running_loop()
        with self._lock:
            self._executors[run_id] = _LoopBoundExecutor(executor=executor, loop=loop)
        logger.debug(f"[WorkflowRuntime] Executor registered: run_id={run_id}")

    def unregister_executor(self, run_id: int, executor: Any | None = None) -> None:
        with self._lock:
            current = self._executors.get(run_id)
            if current and (executor is None or current.executor is executor):
                self._executors.pop(run_id, None)
        logger.debug(f"[WorkflowRuntime] Executor cleaned up: run_id={run_id}")

    def get_executor(self, run_id: int) -> Optional[Any]:
        with self._lock:
            current = self._executors.get(run_id)
            return current.executor if current else None

    def request_pause(self, run_id: int) -> bool:
        """Request to pause a running or pending task."""
        with self._lock:
            self._pause_requested.add(run_id)
            executor_ref = self._executors.get(run_id)
            active = (
                executor_ref is not None
                or run_id in self._tasks
                or run_id in self._pending_runs
                or run_id in self._acquired_runs
            )

        if executor_ref:
            self._call_on_loop(executor_ref.loop, executor_ref.executor.pause)

        return active

    def request_resume(self, run_id: int) -> bool:
        """Resume an executor still paused in-process."""
        with self._lock:
            self._pause_requested.discard(run_id)
            self._cancel_requested.discard(run_id)
            executor_ref = self._executors.get(run_id)

        if not executor_ref:
            return False

        self._call_on_loop(executor_ref.loop, executor_ref.executor.resume)
        return True

    def request_cancel(self, run_id: int) -> bool:
        """Request to cancel a running or pending task."""
        with self._lock:
            self._cancel_requested.add(run_id)
            self._pause_requested.discard(run_id)
            task_ref = self._tasks.get(run_id)
            executor_ref = self._executors.get(run_id)
            active = (
                task_ref is not None
                or executor_ref is not None
                or run_id in self._pending_runs
                or run_id in self._acquired_runs
            )

        if executor_ref:
            self._call_on_loop(executor_ref.loop, executor_ref.executor.pause)
        if task_ref:
            self._call_on_loop(task_ref.loop, task_ref.task.cancel)

        return active

    def is_cancel_requested(self, run_id: int) -> bool:
        with self._lock:
            return run_id in self._cancel_requested

    def is_pause_requested(self, run_id: int) -> bool:
        with self._lock:
            return run_id in self._pause_requested

    def finish_run(self, run_id: int, *, keep_pause: bool = False) -> None:
        """Clean up control state after a run finishes."""
        with self._lock:
            self._tasks.pop(run_id, None)
            self._executors.pop(run_id, None)
            self._pending_runs.discard(run_id)
            self._cancel_requested.discard(run_id)
            if not keep_pause:
                self._pause_requested.discard(run_id)
        self.release_slot(run_id)

    def is_active(self, run_id: int) -> bool:
        with self._lock:
            return (
                run_id in self._tasks
                or run_id in self._executors
                or run_id in self._pending_runs
                or run_id in self._acquired_runs
            )

    @staticmethod
    def _call_on_loop(loop: asyncio.AbstractEventLoop, callback) -> None:
        if loop.is_closed():
            return

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if current_loop is loop:
            callback()
        else:
            loop.call_soon_threadsafe(callback)


workflow_runtime = WorkflowRuntime(max_concurrent_runs=5)