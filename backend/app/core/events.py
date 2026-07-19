"""Event bus system

Unified event publish-subscribe mechanism, supporting decorator registration and auto-discovery.
"""

from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class Event:
    """Event base class
    
    Attributes:
        name: Event name
        data: Event data
        source: Event source
    """
    name: str
    data: Dict[str, Any]
    source: Optional[str] = None


# Event handler registry
_EVENT_HANDLERS: Dict[str, List[Callable]] = {}


def on_event(event_name: str):
    """Decorator: register an event handler
    
    Usage:
        @on_event("card.saved")
        def handle_card_saved(event: Event):
            ...
    
    Args:
        event_name: Event name
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable):
        if event_name not in _EVENT_HANDLERS:
            _EVENT_HANDLERS[event_name] = []
        _EVENT_HANDLERS[event_name].append(func)
        logger.debug(f"[Event Register] {event_name} -> {func.__name__}")
        return func
    return decorator


def emit_event(event_name: str, data: Dict[str, Any], source: Optional[str] = None) -> None:
    """Publish an event
    
    Args:
        event_name: Event name
        data: Event data
        source: Event source
    """
    event = Event(name=event_name, data=data, source=source)
    handlers = _EVENT_HANDLERS.get(event_name, [])
    
    if not handlers:
        logger.debug(f"[Event Emit] {event_name} - no handlers")
        return
    
    logger.info(f"[Event Emit] {event_name} - {len(handlers)} handlers")
    
    for handler in handlers:
        try:
            handler(event)
        except Exception as e:
            logger.error(f"[Event Handler Failed] {event_name} - {handler.__name__}: {e}")


def get_event_handlers(event_name: str) -> List[Callable]:
    """Get all handlers for the specified event
    
    Args:
        event_name: Event name
        
    Returns:
        Handler list
    """
    return _EVENT_HANDLERS.get(event_name, []).copy()


def get_all_events() -> List[str]:
    """Get all registered event names
    
    Returns:
        Event name list
    """
    return list(_EVENT_HANDLERS.keys())


def discover_event_handlers():
    """Log the number of registered event handlers
    
    All event handler modules are imported in app.services.__init__.py,
    and decorators auto-register on package import.
    """
    total_handlers = sum(len(handlers) for handlers in _EVENT_HANDLERS.values())
    logger.debug(f"[Event Discovery] Loaded {len(_EVENT_HANDLERS)} events, {total_handlers} handlers in total")


def clear_handlers(event_name: Optional[str] = None) -> None:
    """Clear event handlers (mainly for testing)
    
    Args:
        event_name: Event name; if None, clear all
    """
    if event_name is None:
        _EVENT_HANDLERS.clear()
        logger.debug("[Event System] Cleared all handlers")
    else:
        _EVENT_HANDLERS.pop(event_name, None)
        logger.debug(f"[Event System] Cleared handlers for {event_name}")