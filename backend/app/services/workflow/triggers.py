"""Workflow triggers

Implements workflow triggering using the event system.
Only supports the new code-based workflow system.

"""

import asyncio
import threading
from typing import List, Dict, Any
from sqlmodel import Session, select
from time import monotonic
from loguru import logger

from app.db.models import Card, Workflow, WorkflowRun
from app.services.workflow.engine import StateManager
from app.services.workflow.engine.runtime import workflow_runtime
from app.db.session import engine as db_engine
from app.core import on_event, Event

# Debounce-related
_recent_keys: Dict[str, float] = {}
_DEBOUNCE_MS = 1500  # The same key will not trigger again within this time window


def _make_idempotency_key(event: str, workflow_id: int, card: Card | None, project_id: int | None) -> str:
    """Generate an idempotency key"""
    card_id = getattr(card, "id", None) or 0
    proj_id = project_id or getattr(card, "project_id", None) or 0
    return f"evt:{event}|wf:{workflow_id}|card:{card_id}|proj:{proj_id}"


def _should_suppress(session: Session, key: str, workflow_id: int) -> bool:
    """Check whether triggering should be suppressed (in-process debounce only)
    
    Only does short debounce (1.5 seconds) to avoid the same event triggering repeatedly within a very short time.
    Does not do persistence-layer checks, allowing failed tasks to be re-triggered.
    """
    # In-process debounce: do not re-trigger within 1.5 seconds
    now = monotonic()
    last = _recent_keys.get(key)
    if last is not None and (now - last) * 1000 < _DEBOUNCE_MS:
        logger.debug(f"[Trigger] Debounce suppressed: {key}")
        return True
    
    # Clean up expired entries (older than 1 minute)
    try:
        for k, v in list(_recent_keys.items()):
            if (now - v) * 1000 > 60000:
                _recent_keys.pop(k, None)
    except Exception:
        pass
    
    # Record this trigger
    _recent_keys[key] = now
    return False


def _get_value_by_path(obj: Any, path: str) -> Any:
    """Get an object attribute value via a dot path"""
    parts = path.split('.')
    current = obj
    
    for part in parts:
        if current is None:
            return None
            
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
            
    return current


def _check_condition(value: Any, op: str, target: Any) -> bool:
    """Check a single condition"""
    if op == "eq" or op == "==":
        return value == target
    elif op == "neq" or op == "!=":
        return value != target
    elif op == "contains":
        if isinstance(value, (list, str, dict)):
            return target in value
        return False
    elif op == "not_contains":
        if isinstance(value, (list, str, dict)):
            return target not in value
        return True
    elif op == "gt" or op == ">":
        try:
            return float(value) > float(target)
        except (ValueError, TypeError):
            return False
    elif op == "lt" or op == "<":
        try:
            return float(value) < float(target)
        except (ValueError, TypeError):
            return False
    elif op == "exists":
        if target:  # If target is true, check if exists (not None)
            return value is not None
        else:      # If target is false, check if not exists (is None)
            return value is None
    # The changed operator has special logic, handled in _evaluate_filter; the fallback here is just for safety
    return False


def _evaluate_filter(card: Card, filter_config: Dict, old_content: Dict | None = None) -> bool:
    """Evaluate whether a card satisfies the filter configuration"""
    if not filter_config:
        return True
        
    conditions = filter_config.get("conditions", [])
    if not conditions:
        return True
        
    operator = filter_config.get("operator", "and").lower()
    results = []
    
    # Build an old_obj wrapper so the same path logic can be used
    old_obj = {"content": old_content} if old_content else {}
    
    for cond in conditions:
        field = cond.get("field")
        op = cond.get("op", "eq")
        target = cond.get("value")
        
        if not field:
            continue
            
        value = _get_value_by_path(card, field)
        
        # Special handling for the changed operator
        if op == "changed":
            old_value = _get_value_by_path(old_obj, field)
            # If it is a creation (old_content is None), treat as changed
            if old_content is None: 
                res = True
            else:
                res = value != old_value
        else:
            res = _check_condition(value, op, target)
            
        results.append(res)
        
        # Optimization: if AND and one is False, return False directly
        if operator == "and" and not res:
            return False
        # Optimization: if OR and one is True, return True directly
        if operator == "or" and res:
            return True
            
    if operator == "and":
        return all(results)
    else:  # or
        return any(results)


def _match_triggers_for_card(session: Session, event: str, card: Card, is_created: bool = False, old_content: Dict | None = None) -> List[Dict[str, Any]]:
    """Match card-related triggers (using triggers_cache)"""
    from app.services.workflow.trigger_extractor import get_active_triggers_by_event
    
    if card.card_type is None and card.card_type_id:
        session.refresh(card, ["card_type"])
    
    card_type_name = card.card_type.name if card.card_type else None

    # Get triggers from triggers_cache (performance optimization)
    # The new trigger matching interface is based on event_name + event_data
    event_name = "card.saved" if event == "onsave" else event
    event_data = {
        "card_id": card.id,
        "project_id": card.project_id,
        "card_type": card_type_name,
        "is_created": bool(is_created),
    }
    all_triggers = get_active_triggers_by_event(session, event_name, event_data)
    
    matched: List[Dict[str, Any]] = []
    current_event = "create" if is_created else "update"
    
    for t in all_triggers:
        filter_json = t.get("filter_json")
        
        if filter_json:
            # 1. Check the fine-grained event type (create/update)
            if "events" in filter_json:
                allowed_events = filter_json["events"]
                if current_event not in allowed_events:
                    continue
            
            # 2. Check the condition filter
            if "conditions" in filter_json:
                if not _evaluate_filter(card, filter_json, old_content):
                    continue
                
        matched.append(t)
    return matched


def _async_execute_workflow(run_id: int):
    """Asynchronously execute a workflow (in a background task)
    
    Only supports the code-based workflow system.
    """
    async def _execute():
        session = Session(db_engine)
        try:
            workflow_runtime.register_task(run_id)

            slot_status = await workflow_runtime.acquire_slot(run_id)
            if slot_status == "cancelled":
                StateManager(session).update_run_status(run_id, "cancelled")
                return
            if slot_status == "paused":
                StateManager(session).update_run_status(run_id, "paused")
                return

            # 1. Get the run record
            state_manager = StateManager(session)
            run = session.get(WorkflowRun, run_id)
            if not run:
                logger.error(f"[Trigger] Run record does not exist: run_id={run_id}")
                return

            wf = session.get(Workflow, run.workflow_id)
            if not wf:
                logger.error(f"[Trigger] Workflow does not exist: wf_id={run.workflow_id}")
                return
            
            # 2. Update status to running
            state_manager.update_run_status(run_id, "running")
            
            try:
                # 3. Execute the code-based workflow
                await _execute_code_workflow(session, state_manager, run, wf)
            except asyncio.CancelledError:
                state_manager.update_run_status(run_id, "cancelled")
                logger.info(f"[Trigger] Background execution cancelled: run_id={run_id}")
                return
            except Exception as e:
                # Update status on execution failure
                state_manager.update_run_status(run_id, "failed")
                state_manager.save_error(run_id, str(e))
                raise
                
        except Exception as e:
            logger.exception(f"[Trigger] Background execution failed: run_id={run_id}")
        finally:
            workflow_runtime.finish_run(
                run_id,
                keep_pause=workflow_runtime.is_pause_requested(run_id)
            )
            session.close()

    try:
        try:
            # Check if we are in a running loop (async context)
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(_execute())
        else:
            # Sync endpoints run in a threadpool; start a background loop so the
            # request can return while the workflow keeps running.
            thread = threading.Thread(
                target=lambda: asyncio.run(_execute()),
                name=f"workflow-run-{run_id}",
                daemon=True,
            )
            thread.start()
            
    except Exception as e:
        logger.error(f"[Trigger] Unable to schedule background task: {e}")


async def _execute_code_workflow(
    session: Session,
    state_manager: StateManager,
    run: WorkflowRun,
    workflow: Workflow,
) -> None:
    """Execute a code-based workflow (trigger-specific)
    
    Unlike the API's streaming execution, this is background execution and does not need to push events.
    """
    from .engine.async_executor import AsyncExecutor
    from .parser.marker_parser import WorkflowParser
    
    run_id = run.id
    code = workflow.definition_code or ""
    
    if not code:
        raise ValueError("Workflow is missing code content")
    
    logger.info(f"[Trigger] Parsing code-based workflow: run_id={run_id}")
    
    # Parse the code
    parser = WorkflowParser()
    plan = parser.parse(code)
    
    logger.info(f"[Trigger] Executing code-based workflow: run_id={run_id}, statement count={len(plan.statements)}")
    
    # Prepare the initial context (inject trigger data)
    initial_context = {}
    
    # Inject trigger data into the __trigger_data__ key
    # Trigger nodes read data from here and output it
    trigger_data = {}
    if run.scope_json:
        trigger_data.update(run.scope_json)
    if run.params_json:
        trigger_data.update(run.params_json)
    
    if trigger_data:
        initial_context["__trigger_data__"] = trigger_data
    
    # Execute the workflow (consume all events)
    executor = AsyncExecutor(
        session=session,
        state_manager=state_manager,
        run_id=run_id
    )
    
    workflow_runtime.register_executor(run_id, executor)
    try:
        # execute_stream is an async generator; all events need to be consumed
        async for event in executor.execute_stream(plan, initial_context):
            # Record key events
            if event.type == "error":
                logger.error(f"[Trigger] Node execution failed: {event.statement.variable if event.statement else 'unknown'}, error={event.error}")
            elif event.type == "complete":
                logger.debug(f"[Trigger] Node execution completed: {event.statement.variable if event.statement else 'unknown'}")

        if executor.is_paused or workflow_runtime.is_pause_requested(run_id):
            state_manager.update_run_status(run_id, "paused")
            logger.info(f"[Trigger] Workflow paused: run_id={run_id}")
            return
    finally:
        workflow_runtime.unregister_executor(run_id, executor)
    
    # Update status to succeeded
    state_manager.update_run_status(
        run_id,
        "succeeded",
        summary_json={
            "variables": list(executor.context.keys()),
            "outputs": executor.context
        }
    )
    
    logger.info(f"[Trigger] Workflow execution completed: run_id={run_id}")


def _execute_triggers(session: Session, event_name: str, triggers: List[Dict[str, Any]], 
                     scope: Dict, card: Card | None = None, project_id: int | None = None,
                     payload: Dict[str, Any] | None = None) -> List[int]:
    """Execute triggers (using triggers_cache)"""
    from .engine import RunManager
    
    run_ids: List[int] = []
    
    run_manager = RunManager(session)
    
    for t in triggers:
        workflow_id = t.get("workflow_id")
        if not workflow_id:
            continue
            
        wf = session.get(Workflow, workflow_id)
        if not wf:
            logger.warning(f"[Trigger] Workflow {workflow_id} not found")
            continue
        if not wf.is_active:
            continue
        
        idem_key = _make_idempotency_key(event_name, workflow_id, card, project_id)
        if _should_suppress(session, idem_key, workflow_id):
            logger.debug(f"[Trigger] Trigger suppressed by idempotency: {idem_key}")
            continue
        
        try:
            # Filter out non-serializable objects
            serializable_payload = {}
            if payload:
                for key, value in payload.items():
                    if key in ['session', 'card']:
                        continue
                    if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                        serializable_payload[key] = value

            if "card_type" not in serializable_payload:
                resolved_card_type = payload.get("card_type") if payload else None
                if resolved_card_type is None and card is not None:
                    card_type = getattr(card, "card_type", None)
                    if card_type is None and getattr(card, "card_type_id", None):
                        try:
                            session.refresh(card, ["card_type"])
                            card_type = getattr(card, "card_type", None)
                        except Exception:
                            card_type = None
                    resolved_card_type = getattr(card_type, "name", None) if card_type else None
                if isinstance(resolved_card_type, str):
                    serializable_payload["card_type"] = resolved_card_type
            
            # Create the run record
            run = run_manager.create_run(
                workflow_id=workflow_id,
                trigger_data=scope,
                params=serializable_payload,
                idempotency_key=idem_key
            )
            
            if run.id:
                run_ids.append(int(run.id))
                
                try:
                    from app.core.workflow_context import add_triggered_run_id
                    add_triggered_run_id(int(run.id))
                except Exception:
                    pass

                # Schedule async execution
                _async_execute_workflow(run.id)
            else:
                 logger.error(f"[Trigger] Run creation returned no ID for wf {workflow_id}")
                
        except Exception as e:
            logger.exception(f"[Trigger] Failed to create/trigger run: wf={workflow_id}, err={e}")

    return run_ids


@on_event("card.saved")
def handle_card_saved(event: Event):
    """Handle the card save event"""
    session: Session = event.data.get("session")
    card: Card = event.data.get("card")
    
    if not session or not card:
        logger.warning("[Workflow Trigger] card.saved event is missing required data")
        return
    
    is_created = event.data.get("is_created", False)

    card_type_name = event.data.get("card_type")
    if card_type_name is None:
        card_type = getattr(card, "card_type", None)
        if card_type is None and getattr(card, "card_type_id", None):
            try:
                session.refresh(card, ["card_type"])
                card_type = getattr(card, "card_type", None)
            except Exception:
                card_type = None
        card_type_name = getattr(card_type, "name", None) if card_type else None
    
    triggers = _match_triggers_for_card(session, "onsave", card, is_created=is_created)
    scope = {
        "card_id": card.id,
        "project_id": card.project_id,
        "card_type": card_type_name,
        "is_created": bool(is_created),
    }
    # Pass event.data as the payload
    run_ids = _execute_triggers(session, "onsave", triggers, scope, card, card.project_id, payload=event.data)
    
    event.data["triggered_run_ids"] = run_ids
    if run_ids:
        logger.info(f"[Workflow Trigger] card.saved - triggered {len(run_ids)} workflows")


@on_event("project.created")
def handle_project_created(event: Event):
    """Handle the project creation event
    
    If template is None, no workflows are triggered (blank project).
    """
    from app.services.workflow.trigger_extractor import get_active_triggers_by_event
    
    try:
        session: Session = event.data.get("session")
        project_id: int = event.data.get("project_id")
        template: str | None = event.data.get("template")
        
        if not session or not project_id:
            logger.warning("[Workflow Trigger] project.created event is missing required data")
            return
        
        # If template is None, do not trigger any workflows (blank project)
        if template is None:
            logger.info(f"[Workflow Trigger] project.created - blank project, no workflows triggered")
            event.data["triggered_run_ids"] = []
            return
        
        # Prepare event data (for matching)
        event_data = {
            "project_id": project_id,
            "template": template,
            "user_id": event.data.get("user_id"),
        }
        
        # Match using the new format
        triggers = get_active_triggers_by_event(session, "project.created", event_data)
        
        scope = {"project_id": project_id, "template": template}
        run_ids = _execute_triggers(session, "project.created", triggers, scope, None, project_id, payload=event.data)
        
        event.data["triggered_run_ids"] = run_ids

        if run_ids:
            logger.info(f"[Workflow Trigger] project.created - triggered {len(run_ids)} workflows (template={template})")
    except Exception as e:
        logger.exception(f"[Workflow] handle_project_created failed: {e}")