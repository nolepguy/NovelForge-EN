"""Trigger extractor - automatically extracts trigger configuration from workflow code

Used to optimize the trigger system, avoiding separate WorkflowTrigger table queries.
"""

from typing import List, Dict, Any
from loguru import logger


def extract_triggers_from_code(code: str) -> List[Dict[str, Any]]:
    """Extract trigger configuration from workflow code
    
    Parses trigger nodes in the code, extracts trigger information and caches it
    into the Workflow.triggers_cache field.
    
    Supported trigger nodes:
        - Trigger.ProjectCreated: project creation trigger
          parameter: template (optional)
          
        - Trigger.CardSaved: card save trigger
          parameters: card_type (optional), on_create (default false), on_update (default true)
    
    Args:
        code: Workflow code (comment-marker DSL)
        
    Returns:
        List of trigger configurations, format:
        [
            {
                "event": "project.created",
                "match": {"template": "snowflake"}  # built from node parameters
            },
            ...
        ]
    
    Example:
        >>> code = '''
        ... #@node()
        ... trigger = Trigger.ProjectCreated(template="snowflake")
        ... #</node>
        ... '''
        >>> extract_triggers_from_code(code)
        [{"event": "project.created", "match": {"template": "snowflake"}}]
    """
    from app.services.workflow.parser.marker_parser import WorkflowParser
    
    if not code or not code.strip():
        return []
    
    # Mapping from node type to event name
    NODE_TYPE_TO_EVENT = {
        "Trigger.ProjectCreated": "project.created",
        "Trigger.CardSaved": "card.saved",
    }
    
    try:
        # Parse the workflow code
        parser = WorkflowParser()
        plan = parser.parse(code)
        
        triggers = []
        
        # Iterate over all statements, looking for trigger nodes
        for stmt in plan.statements:
            # Skip disabled nodes
            if stmt.disabled:
                logger.debug(f"[TriggerExtractor] Skipping disabled trigger node: {stmt.variable}")
                continue
            
            node_type = stmt.node_type
            config = stmt.config or {}
            
            # Check whether it is a trigger node
            event = NODE_TYPE_TO_EVENT.get(node_type)
            if not event:
                continue
            
            # Build match conditions based on node type
            match = {}
            
            if node_type == "Trigger.ProjectCreated":
                # Extract the template parameter
                if "template" in config and config["template"]:
                    match["template"] = config["template"]
                    
            elif node_type == "Trigger.CardSaved":
                # Extract the card_type parameter
                if "card_type" in config and config["card_type"]:
                    match["card_type"] = config["card_type"]
                # Extract on_create and on_update parameters
                # Default values must match TriggerCardSavedInput: on_create=False, on_update=True
                on_create = bool(config.get("on_create", False))
                on_update = bool(config.get("on_update", True))

                # Both off: this trigger should not fire for any event, skip it
                if not on_create and not on_update:
                    logger.debug("[TriggerExtractor] Skipping invalid Trigger.CardSaved: both on_create and on_update are false")
                    continue

                # Create only / update only: collapse to the is_created condition
                if on_create and not on_update:
                    match["is_created"] = True
                elif not on_create and on_update:
                    match["is_created"] = False
                # Both true: do not add the is_created condition (fire for both create/update)
            
            trigger_config = {
                "event": event,
                "match": match if match else None
            }
            
            triggers.append(trigger_config)
        
        logger.debug(f"[TriggerExtractor] Extracted {len(triggers)} triggers from code")
        return triggers
    
    except Exception as e:
        logger.error(f"[TriggerExtractor] Failed to extract triggers: {e}")
        return []


def sync_triggers_cache(workflow, session) -> None:
    """Sync a workflow's trigger cache
    
    Extracts triggers from definition_code and updates the triggers_cache field.
    
    Args:
        workflow: Workflow object
        session: Database session
    """
    if not workflow.definition_code:
        workflow.triggers_cache = []
        return
    
    triggers = extract_triggers_from_code(workflow.definition_code)
    
    workflow.triggers_cache = triggers
    session.add(workflow)
    
    logger.info(f"[TriggerExtractor] Trigger cache updated for workflow {workflow.id} ({workflow.name}): {len(triggers)} triggers")


def match_event(event_name: str, event_data: Dict[str, Any], trigger: Dict[str, Any]) -> bool:
    """Determine whether an event matches a trigger
    
    Args:
        event_name: Event name (e.g. project.created, card.saved)
        event_data: Event data (e.g. {"project_id": 1, "template": "snowflake"})
        trigger: Trigger configuration (contains event and match fields)
        
    Returns:
        Whether it matches
    """
    # 1. Event name must match
    if trigger.get("event") != event_name:
        return False
    
    # 2. If there are no match conditions, it matches directly
    match_conditions = trigger.get("match")
    if not match_conditions:
        return True
    
    # 3. Check all match conditions
    for key, expected_value in match_conditions.items():
        actual_value = event_data.get(key)
        
        # Simple equality match
        if actual_value != expected_value:
            return False
    
    return True


def get_active_triggers_by_event(session, event_name: str, event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get triggers matching the specified event
    
    Args:
        session: Database session
        event_name: Event name (e.g. project.created, card.saved)
        event_data: Event data (e.g. {"project_id": 1, "template": "snowflake"})
        
    Returns:
        List of matching triggers, format:
        [
            {
                "workflow_id": 1,
                "event": "project.created",
                "match": {"template": "snowflake"}
            },
            ...
        ]
    """
    from sqlmodel import select
    from app.db.models import Workflow
    
    # Query all active workflows
    stmt = select(Workflow).where(
        Workflow.is_active == True,
        Workflow.triggers_cache.isnot(None)
    )
    workflows = session.exec(stmt).all()
    
    matched_triggers = []
    
    for wf in workflows:
        if not wf.triggers_cache:
            continue
        
        for trigger in wf.triggers_cache:
            # Use the new matching logic
            if match_event(event_name, event_data, trigger):
                matched_triggers.append({
                    "workflow_id": wf.id,
                    **trigger
                })
    
    logger.debug(f"[TriggerExtractor] Found {len(matched_triggers)} matching triggers: event={event_name}, data={event_data}")
    return matched_triggers