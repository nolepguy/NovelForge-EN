from datetime import datetime, timedelta
from sqlmodel import Session, select, delete
from loguru import logger
from app.db.models import WorkflowRun, Workflow
from app.core.config import settings

def cleanup_expired_runs(session: Session):
    """Clean up expired workflow run records
    
    Strategy (simplified):
    1. Non-persistent (keep_run_history=False): clean up all completed runs on next startup
    2. Persistent (keep_run_history=True): retain for N days
    3. Runs with unfinished status (running/queued/paused) are not deleted
    """
    persistent_retention_days = settings.workflow.retention_persistent_days
        
    now = datetime.utcnow()
    deleted_count = 0
    
    try:
        # Strategy A: clean up all "non-persistent" and "completed" runs (no time check needed)
        stmt_transient = (
            select(WorkflowRun.id)
            .join(Workflow)
            .where(
                WorkflowRun.status.in_(["succeeded", "failed", "cancelled", "timeout"]),
                (Workflow.keep_run_history == False) | (Workflow.keep_run_history == None)
            )
        )
        transient_ids = session.exec(stmt_transient).all()
        
        if transient_ids:
            stmt_del = delete(WorkflowRun).where(WorkflowRun.id.in_(transient_ids))
            result = session.exec(stmt_del)
            deleted_count += result.rowcount if hasattr(result, 'rowcount') else len(transient_ids)
            logger.info(f"[Cleanup] Cleaned up non-persistent run records: {len(transient_ids)} records")

        # Strategy B: clean up "persistent" and "completed" runs that "exceed the retention period"
        persistent_cutoff = now - timedelta(days=persistent_retention_days)
        stmt_persistent = (
            select(WorkflowRun.id)
            .join(Workflow)
            .where(
                WorkflowRun.status.in_(["succeeded", "failed", "cancelled", "timeout"]),
                WorkflowRun.finished_at < persistent_cutoff,
                Workflow.keep_run_history == True
            )
        )
        persistent_ids = session.exec(stmt_persistent).all()
        
        if persistent_ids:
            stmt_del = delete(WorkflowRun).where(WorkflowRun.id.in_(persistent_ids))
            result = session.exec(stmt_del)
            count = result.rowcount if hasattr(result, 'rowcount') else len(persistent_ids)
            deleted_count += count
            logger.info(f"[Cleanup] Cleaned up expired persistent records: {count} records")
            
        session.commit()
        if deleted_count > 0:
            logger.info(f"[Cleanup] Workflow cleanup completed, deleted {deleted_count} records in total")
            
    except Exception as e:
        logger.error(f"[Cleanup] Failed to clean up workflows: {e}")
        session.rollback()