"""Unified error handler

Responsibilities:
- Uniformly handle node execution errors
- Handle task cancellation
- Save error information to state
"""

import asyncio
from typing import TYPE_CHECKING
from loguru import logger
from sqlmodel import Session

if TYPE_CHECKING:
    from .execution_state import ExecutionState
    from ..engine.execution_plan import Statement
    from .async_executor import ProgressEvent


class ExecutionError(Exception):
    """Base execution error"""
    def __init__(self, node_id: str, message: str, details: dict = None):
        self.node_id = node_id
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NodeExecutionError(ExecutionError):
    """Node execution error"""
    pass


class CheckpointError(ExecutionError):
    """Checkpoint error"""
    pass


class ErrorHandler:
    """Unified error handler"""
    
    @staticmethod
    async def handle_node_error(
        error: Exception,
        stmt: 'Statement',
        execution_state: 'ExecutionState',
        session: Session
    ) -> 'ProgressEvent':
        """Handle a node execution error
        
        Args:
            error: Exception object
            stmt: Statement object
            execution_state: Execution state
            session: Database session
            
        Returns:
            Error event
        """
        from .async_executor import ProgressEvent
        
        logger.error(f"[ErrorHandler] Node execution failed: {stmt.variable}, error: {error}")
        
        # Update node state
        execution_state.update_node_state(
            node_id=stmt.variable,
            node_type=stmt.node_type or "unknown",
            status="error",
            error=str(error)
        )
        
        # Save state
        execution_state.save(session)
        
        # Return the error event
        return ProgressEvent(
            statement=stmt,
            type='error',
            error=str(error)
        )
    
    @staticmethod
    async def handle_cancellation(
        stmt: 'Statement',
        execution_state: 'ExecutionState',
        session: Session
    ):
        """Handle task cancellation
        
        Called when an async task is cancelled, saving the current progress.
        
        Args:
            stmt: Statement object
            execution_state: Execution state
            session: Database session
        """
        logger.info(f"[ErrorHandler] Task cancelled: {stmt.variable}")
        
        # Get current progress
        node_state = execution_state.get_node_state(stmt.variable)
        current_progress = node_state.progress if node_state else 0.0
        
        # Mark as paused
        execution_state.update_node_state(
            node_id=stmt.variable,
            node_type=stmt.node_type or "unknown",
            status="paused",
            progress=current_progress
        )
        
        # Save state
        execution_state.save(session)
        
        logger.info(f"[ErrorHandler] Task cancellation handled: {stmt.variable}, progress={current_progress}%")