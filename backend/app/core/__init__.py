"""Core module

Contains core functionality such as the event system, startup initialization, and configuration management.
"""

# Event system
from .events import Event, on_event, emit_event, get_event_handlers, discover_event_handlers

# Configuration system
from .config import settings

# Note: startup and shutdown are not exported here to avoid circular imports
# Import directly from app.core.startup when needed

__all__ = [
    # Event system
    'Event',
    'on_event',
    'emit_event',
    'get_event_handlers',
    'discover_event_handlers',
    # Configuration system
    'settings',
]