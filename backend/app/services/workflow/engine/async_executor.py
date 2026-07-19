"""Async executor

Async executor based on the code-based workflow, supporting SSE progress push.
Fully streaming design: all nodes are consumed via async for events.
"""

import asyncio
from typing import Dict, Any, List, Optional, AsyncIterator, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime
from loguru import logger
from sqlmodel import Session

from .execution_plan import ExecutionPlan, Statement
from .execution_state import ExecutionState, CheckpointData
from .error_handler import ErrorHandler
from ..registry import get_registered_nodes
from ..expressions.evaluator import evaluate_expression

if TYPE_CHECKING:
    from .state_manager import StateManager


# Unified progress event (shared by nodes and the executor)
@dataclass
class ProgressEvent:
    """Progress event (unified type)
    
    Used by nodes to report execution progress; the executor automatically saves it as a checkpoint.
    
    Node usage (simple version):
        yield ProgressEvent(
            percent=50.0,
            message="Processed 30/60",
            data={'processed_count': 30}
        )
    
    Executor usage (includes statement):
        yield ProgressEvent(
            statement=stmt,
            type='progress',
            percent=50.0,
            message="Processed 30/60"
        )
    
    Attributes:
        percent: Progress percentage (0-100)
        message: Progress message
        data: Checkpoint data (used by nodes, optional, lightweight metadata)
            - Only position info is saved: index, counter, ID, etc.
            - Business data is not saved: card content, processing results, etc.
            - Size limit: < 10KB
        statement: Statement object (used by the executor)
        type: Event type (used by the executor)
        result: Execution result (used by the executor)
        error: Error message (used by the executor)
    """
    # Node-layer fields
    percent: float = 0.0  # 0-100
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    
    # Executor-layer fields
    statement: Optional[Statement] = None
    type: Optional[str] = None  # 'start', 'progress', 'complete', 'error', 'workflow_complete'
    result: Optional[Any] = None
    error: Optional[str] = None


class AsyncExecutor:
    """Async executor
    
    Fully streaming design:
    1. All nodes are consumed via async for events
    2. Async tasks are collected and executed in parallel
    3. wait nodes wait for and forward events
    4. Sync nodes automatically wait for all async tasks
    5. Supports pause/resume and checkpoint recovery
    
    Uses the unified ExecutionState to manage all state.
    """

    def __init__(self, session: Session, state_manager: Optional['StateManager'] = None, run_id: int = 0):
        self.session = session  # Database session
        self.state_manager = state_manager  # State manager (optional, for compatibility)
        self.run_id = run_id  # Run ID
        self.execution_state = ExecutionState(run_id)  # Unified execution state
        self.node_registry = get_registered_nodes()
        self.async_tasks: Dict[str, asyncio.Task] = {}  # Async tasks (keep references for cancellation)
        self.node_instances: Dict[str, Any] = {}  # Node instances (for cleanup)
        self.event_queue: asyncio.Queue = asyncio.Queue()  # Event queue (real-time forwarding)
        self.pending_async_tasks: int = 0  # Number of pending async tasks
        self.pause_event = asyncio.Event()  # Pause signal
        self.pause_event.set()  # Not paused by default
        self.is_paused = False  # Whether paused
    
    @property
    def context(self) -> Dict[str, Any]:
        """Execution context (compatibility with legacy code)"""
        return self.execution_state.context
    
    @property
    def completed_statements(self) -> set:
        """Completed statements (compatibility with legacy code)"""
        return self.execution_state.completed_nodes

    async def execute_stream(
        self,
        plan: ExecutionPlan,
        initial_context: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[ProgressEvent]:
        """Stream-execute the workflow, yielding progress events
        
        Uses an event queue to forward progress in real time:
        1. Progress events from async tasks are put into the queue in real time
        2. The main coroutine reads events from the queue and yields them
        3. Supports multiple async tasks reporting progress simultaneously
        4. Supports pause/resume and checkpoint recovery
        
        Args:
            plan: Execution plan
            initial_context: Initial context
            
        Yields:
            Progress events
        """
        # Try to recover state (checkpoint recovery)
        is_resuming = False
        if self.run_id:
            # Load the full state from the database
            self.execution_state = ExecutionState.load(self.run_id, self.session)
            
            # Only consider it a resumed execution when there are completed nodes
            if self.execution_state.completed_nodes:
                is_resuming = True
                logger.info(
                    f"[AsyncExecutor] Resumed execution detected: run_id={self.run_id}, "
                    f"completed={len(self.execution_state.completed_nodes)} nodes"
                )
            else:
                # Has a run_id but no completed nodes: a new execution or a failed retry
                self.execution_state.context = initial_context or {}
                logger.info(f"[AsyncExecutor] New execution or retry: run_id={self.run_id}, using initial context")
        else:
            # New execution, use the initial context
            self.execution_state.context = initial_context or {}
            logger.info(f"[AsyncExecutor] New execution: using initial context")
        
        # If resuming, first push the state of completed nodes (so the frontend can display them)
        if is_resuming:
            for node_id in self.execution_state.completed_nodes:
                node_state = self.execution_state.get_node_state(node_id)
                if node_state and node_state.status == "success":
                    # Find the corresponding statement
                    stmt = next((s for s in plan.statements if s.variable == node_id), None)
                    if stmt:
                        # Push the completed event
                        await self.event_queue.put(ProgressEvent(
                            statement=stmt,
                            type='complete',
                            result=node_state.outputs,
                            message=f"[Resumed] {node_id}"
                        ))
                        logger.info(f"[AsyncExecutor] Pushed completed node state: {node_id}")
        
        logger.info(f"[AsyncExecutor] Starting streaming workflow execution, {len(plan.statements)} statements in total")
        
        # Start the event consumer coroutine
        consumer_task = asyncio.create_task(self._process_statements(plan))
        
        try:
            # Read events from the queue and forward them
            while True:
                event = await self.event_queue.get()
                
                if event is None:  # End marker
                    break
                    
                yield event
                
        finally:
            # Wait for statement processing to finish
            try:
                await consumer_task
            except Exception as e:
                logger.error(f"[AsyncExecutor] Statement processing failed: {e}")
                raise
    
    async def _process_statements(self, plan: ExecutionPlan):
        """Process all statements (runs in a separate coroutine)"""
        try:
            for stmt in plan.statements:
                # Skip completed statements (checkpoint recovery)
                if self.execution_state.is_completed(stmt.variable):
                    logger.info(f"[AsyncExecutor] Skipping completed statement: {stmt.variable}")
                    continue
                
                # Check the pause signal (if paused, stop execution)
                if self.is_paused:
                    logger.info(f"[AsyncExecutor] Paused state detected, stopping execution")
                    break
                
                # Wait for the pause signal (if paused, this will block here)
                await self.pause_event.wait()
                
                logger.info(f"[AsyncExecutor] Executing statement: {stmt.variable} (type: {stmt.node_type}, async: {stmt.is_async}, disabled: {stmt.disabled})")
                
                # Skip disabled nodes
                if stmt.disabled:
                    logger.info(f"[AsyncExecutor] Skipping disabled node: {stmt.variable}")
                    
                    # Send a skip event to the queue
                    await self.event_queue.put(ProgressEvent(
                        statement=stmt,
                        type='skipped',
                        message=f"Node is disabled, skipping execution: {stmt.variable}"
                    ))
                    
                    # Set the result to None (avoid errors when referenced by later nodes)
                    self.execution_state.context[stmt.variable] = None
                    self.execution_state.completed_nodes.add(stmt.variable)
                    continue
                
                # Send a start event to the queue
                await self.event_queue.put(ProgressEvent(
                    statement=stmt,
                    type='start',
                    message=f"Starting execution: {stmt.variable}"
                ))
                
                try:
                    if stmt.is_async:
                        # Async node: create a task, events are put into the queue in real time
                        logger.info(f"[AsyncNode] Creating async task: {stmt.variable}")
                        self.pending_async_tasks += 1
                        
                        # Create the task, putting events into the queue in real time (keep reference for cancellation)
                        task = asyncio.create_task(
                            self._execute_async_node_to_queue(stmt),
                            name=f"async_node_{stmt.variable}"  # Set task name for easier debugging
                        )
                        self.async_tasks[stmt.variable] = task
                        logger.info(f"[AsyncNode] Task created and reference saved: {stmt.variable}")
                        # Do not wait, continue to the next statement
                        
                    elif stmt.node_type == "Logic.Wait" or stmt.node_type == "_wait":
                        # wait node: wait for the specified async task(s)
                        # Supports two config formats: tasks (new) and wait_for (legacy)
                        wait_for = stmt.config.get("tasks") or stmt.config.get("wait_for", [])
                        
                        # Ensure wait_for is a list
                        if isinstance(wait_for, str):
                            # If it is a string, split by comma
                            wait_for = [v.strip() for v in wait_for.split(",") if v.strip()]
                        elif not isinstance(wait_for, list):
                            wait_for = [wait_for] if wait_for else []
                        
                        # Clean up variable names: remove the $ prefix (if any)
                        wait_for = [v.lstrip('$') if isinstance(v, str) else v for v in wait_for]
                        
                        logger.info(f"[Wait] Waiting for async tasks: {','.join(wait_for)}")
                        
                        for var in wait_for:
                            if var in self.async_tasks:
                                # The async task is still running, wait for it to complete
                                logger.info(f"[Wait] Waiting for async task to complete: {var}")
                                await self.async_tasks[var]
                                del self.async_tasks[var]
                            elif var in self.execution_state.context:
                                # The variable is already in the context (a completed or recovered node)
                                logger.info(f"[Wait] Variable already exists in context: {var}")
                            else:
                                # The variable does not exist
                                raise ValueError(f"Waited variable does not exist: {var}")
                        
                        # Save the wait result to the context
                        self.execution_state.context[stmt.variable] = {
                            'waited_tasks': wait_for,
                            'count': len(wait_for)
                        }
                        
                        # The wait node itself sends the complete event
                        await self.event_queue.put(ProgressEvent(
                            statement=stmt,
                            type='complete',
                            result=self.execution_state.context[stmt.variable]
                        ))
                        
                        # Mark as completed
                        self.execution_state.completed_nodes.add(stmt.variable)
                        
                    elif stmt.node_type is None:
                        # Pure expression
                        result = self._execute_expression(stmt)
                        self.execution_state.context[stmt.variable] = result
                        
                        # Save node outputs
                        self.execution_state.update_node_state(
                            node_id=stmt.variable,
                            node_type="expression",
                            status="success",
                            progress=100.0,
                            outputs=result
                        )
                        self.execution_state.save(self.session)
                        
                        await self.event_queue.put(ProgressEvent(
                            statement=stmt,
                            type='complete',
                            result=result
                        ))
                        
                    else:
                        # Sync node: execute directly, do not wait for async tasks
                        async for event in self._execute_node_stream(stmt):
                            await self.event_queue.put(event)
                    
                    # Mark the statement as completed
                    self.execution_state.completed_nodes.add(stmt.variable)
                            
                except Exception as e:
                    logger.error(f"[AsyncExecutor] Statement execution failed: {stmt.variable}, error: {e}")
                    # Use the error handler
                    error_event = await ErrorHandler.handle_node_error(
                        e, stmt, self.execution_state, self.session
                    )
                    await self.event_queue.put(error_event)
                    raise
            
            # Workflow finished, wait for all remaining async tasks
            if self.async_tasks:
                logger.info(f"[AsyncExecutor] Workflow finished, waiting for {len(self.async_tasks)} remaining async tasks")
                for var, task in list(self.async_tasks.items()):
                    logger.info(f"[AsyncExecutor] Waiting for async task: {var}")
                    await task
                    del self.async_tasks[var]
            
            logger.info(f"[AsyncExecutor] Workflow streaming execution completed, {len(self.execution_state.context)} variables defined in total")
            
            # Send the workflow-complete event
            await self.event_queue.put(ProgressEvent(
                statement=plan.statements[-1] if plan.statements else Statement(line_number=0, variable="", node_type=None, config={}, depends_on=[]),
                type='workflow_complete',
                message="Workflow execution completed"
            ))
            
        finally:
            # Send the end marker
            await self.event_queue.put(None)
    
    async def _execute_async_node_to_queue(self, stmt: Statement):
        """Execute an async node and put events into the queue in real time"""
        try:
            async for event in self._execute_node_stream(stmt):
                await self.event_queue.put(event)
        except asyncio.CancelledError:
            # Task was cancelled, use the error handler to save state
            await ErrorHandler.handle_cancellation(
                stmt, self.execution_state, self.session
            )
            raise  # Re-raise to let the upper layer handle it
        except Exception as e:
            # Node execution error
            logger.error(f"[AsyncNode] Async node execution failed: {stmt.variable}, error: {e}")
            error_event = await ErrorHandler.handle_node_error(
                e, stmt, self.execution_state, self.session
            )
            await self.event_queue.put(error_event)
            raise
        finally:
            self.pending_async_tasks -= 1

    async def _execute_node_stream(self, stmt: Statement) -> AsyncIterator[ProgressEvent]:
        """Execute a node and stream events (supports automatic checkpoints)
        
        Core features:
        1. Load the checkpoint (if any) and inject it into ExecutionContext
        2. Intercept all yields and automatically save checkpoints
        3. Forward progress events to the frontend
        
        Args:
            stmt: Statement object
            
        Yields:
            Progress events (progress and complete)
        """
        node_type = stmt.node_type
        
        # Get the node executor
        executor_fn = self.node_registry.get(node_type)
        if not executor_fn:
            raise ValueError(f"Unregistered node type: {node_type}")
        
        # Parse config, handling variable references
        config = self._resolve_config(stmt.config)
        
        # Build inputs
        inputs = self._resolve_inputs(config)
        
        # === Initialize node state ===
        self.execution_state.update_node_state(
            node_id=stmt.variable,
            node_type=node_type,
            status="running",
            progress=0.0
        )
        
        # === 1. Load checkpoint ===
        checkpoint_data = self.execution_state.get_checkpoint(stmt.variable)
        checkpoint = checkpoint_data.data if checkpoint_data else None
        
        if checkpoint:
            logger.info(
                f"[Checkpoint] Recovering node {stmt.variable}: "
                f"progress={checkpoint_data.percent}%, "
                f"data={checkpoint}"
            )
        
        # Execute the node
        import inspect
        if inspect.isclass(executor_fn):
            # Class-based node - needs to create an ExecutionContext
            from ..types import ExecutionContext, WorkflowSettings
            
            # === 2. Create the execution context (inject checkpoint) ===
            context = ExecutionContext(
                run_id=self.run_id or 0,
                node_id=stmt.variable,
                node_type=node_type,
                config=config,
                inputs=inputs,
                variables=self.execution_state.context,
                node_outputs={},
                settings=WorkflowSettings(),
                session=self.session,
                checkpoint=checkpoint  # Inject checkpoint data
            )
            
            # Instantiate the node
            node = executor_fn(context)
            
            # Keep node instance reference (for cleanup)
            self.node_instances[stmt.variable] = node
            
            # Prepare input data (merge config and inputs)
            if hasattr(executor_fn, 'input_model') and executor_fn.input_model:
                input_data = {**config, **inputs}
                input_instance = executor_fn.input_model(**input_data)
            else:
                raise ValueError(f"Node {node_type} is missing input_model definition")
            
            # === 3. Execute the node and intercept yields ===
            result = None
            async for event in node.execute(input_instance):
                # Handle progress events (the node's ProgressEvent)
                if isinstance(event, ProgressEvent):
                    # === Automatically save checkpoint ===
                    checkpoint_data = CheckpointData(
                        percent=event.percent,
                        message=event.message,
                        data=event.data,
                        timestamp=datetime.utcnow()
                    )
                    
                    self.execution_state.update_node_state(
                        node_id=stmt.variable,
                        node_type=node_type,
                        status="running",
                        progress=event.percent,
                        checkpoint=checkpoint_data
                    )
                    self.execution_state.save(self.session)
                    
                    # Forward the progress event (wrap as an executor event)
                    yield ProgressEvent(
                        statement=stmt,
                        type='progress',
                        percent=event.percent,
                        message=event.message
                    )
                else:
                    # This is the final result (a Pydantic model)
                    result = event
            
            # Check the execution result
            if result is None:
                raise ValueError(f"Node {node_type} did not return a result")
            
            # Convert to a dict
            if hasattr(result, 'model_dump'):
                final_result = result.model_dump()
            elif hasattr(result, 'dict'):
                final_result = result.dict()
            else:
                final_result = result
            
            # Save to context (use the full output dict uniformly)
            self.execution_state.context[stmt.variable] = final_result
            
            # === 4. Save the completed state (100% progress) ===
            self.execution_state.update_node_state(
                node_id=stmt.variable,
                node_type=node_type,
                status="success",
                progress=100.0,
                outputs=final_result,
                checkpoint=CheckpointData(
                    percent=100.0,
                    message="Completed",
                    data={'completed': True},
                    timestamp=datetime.utcnow()
                )
            )
            self.execution_state.save(self.session)
            
            # Send the complete event
            yield ProgressEvent(
                statement=stmt,
                type='complete',
                result=final_result
            )
                
        elif inspect.iscoroutinefunction(executor_fn):
            # Async function node
            result = await executor_fn(**inputs)
            self.execution_state.context[stmt.variable] = result
            
            # Save node outputs
            self.execution_state.update_node_state(
                node_id=stmt.variable,
                node_type=node_type or "async_function",
                status="success",
                progress=100.0,
                outputs=result
            )
            self.execution_state.save(self.session)
            
            yield ProgressEvent(
                statement=stmt,
                type='complete',
                result=result
            )
        else:
            # Sync function node
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: executor_fn(**inputs))
            self.execution_state.context[stmt.variable] = result
            
            # Save node outputs
            self.execution_state.update_node_state(
                node_id=stmt.variable,
                node_type=node_type or "sync_function",
                status="success",
                progress=100.0,
                outputs=result
            )
            self.execution_state.save(self.session)
            
            yield ProgressEvent(
                statement=stmt,
                type='complete',
                result=result
            )

    def _execute_expression(self, stmt: Statement) -> Any:
        """Execute a pure expression"""
        expression = stmt.config.get("expression", "")
        logger.info(f"[Expression] Executing expression: {expression}")
        
        # Evaluate using the expression evaluator
        context = self._resolve_context(stmt.depends_on)
        return evaluate_expression(expression, context)

    def _resolve_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Parse config, handling variable references (supports nested structures)"""
        resolved = {}
        for key, value in config.items():
            resolved[key] = self._resolve_value(value)
        return resolved

    def _resolve_value(self, value: Any) -> Any:
        """Recursively resolve a value, handling variable references"""
        if isinstance(value, str):
            if value.startswith("${") and value.endswith("}"):
                # Expression reference, e.g. ${len(items)}
                expression = value[2:-1]
                return evaluate_expression(expression, self.execution_state.context)
            elif value.startswith("$"):
                # Variable reference, e.g. $novel.chapter_list
                ref = value[1:]  # Remove the $ prefix
                return self._resolve_variable_reference(ref)
            else:
                return value
        elif isinstance(value, list):
            return [self._resolve_value(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._resolve_value(v) for k, v in value.items()}
        else:
            return value

    def _resolve_variable_reference(self, ref: str) -> Any:
        """Resolve a variable reference
        
        Supports:
        - Simple variable: novel
        - Attribute access: novel.title
        - Nested attribute: novel.metadata.author
        """
        parts = ref.split(".")
        value = self.execution_state.context.get(parts[0])
        
        if value is None:
            raise ValueError(f"Variable does not exist: {parts[0]}")
        
        # Handle attribute access
        for part in parts[1:]:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = getattr(value, part, None)
            
            if value is None:
                raise ValueError(f"Attribute does not exist: {ref}")
        
        return value

    def _resolve_inputs(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract input parameters from config"""
        # For most nodes, config is the inputs
        return config

    def _resolve_context(self, depends_on: List[str]) -> Dict[str, Any]:
        """Resolve the dependent context"""
        context = {}
        for var in depends_on:
            if var in self.execution_state.context:
                context[var] = self.execution_state.context[var]
        return context

    def pause(self):
        """Pause execution
        
        Immediately cancels all async tasks and pauses execution.
        Does not wait for tasks to complete; lets them cancel in the background.
        """
        self.is_paused = True
        self.pause_event.clear()
        
        # Clean up all node instances (do not wait for completion)
        if self.node_instances:
            logger.info(f"[AsyncExecutor] Cleaning up {len(self.node_instances)} node instances")
            for var, node in list(self.node_instances.items()):
                try:
                    logger.info(f"[AsyncExecutor] Cleaning up node: {var}")
                    # Create a cleanup task but do not wait (background cleanup)
                    asyncio.create_task(node.cleanup())
                except Exception as e:
                    logger.error(f"[AsyncExecutor] Failed to create cleanup task: {var}, error: {e}")
        
        # Cancel all async tasks (do not wait for completion)
        if self.async_tasks:
            logger.info(f"[AsyncExecutor] Cancelling {len(self.async_tasks)} async tasks")
            for var, task in list(self.async_tasks.items()):
                if not task.done():
                    logger.info(f"[AsyncExecutor] Cancelling async task: {var}")
                    task.cancel()
                    # Do not wait for the task to complete; let it cancel in the background
        
        logger.info(f"[AsyncExecutor] Workflow paused: run_id={self.run_id}")
    
    def resume(self):
        """Resume execution
        
        Resumes a previously paused workflow execution.
        """
        self.is_paused = False
        self.pause_event.set()
        logger.info(f"[AsyncExecutor] Workflow resumed: run_id={self.run_id}")
    
    def is_paused(self) -> bool:
        """Check whether it is in the paused state"""
        return not self.pause_event.is_set()