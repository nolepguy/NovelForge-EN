"""Initializer registry mechanism

Provides decorators and auto-discovery for a plugin-based initialization system.

Usage:
    @initializer(name="prompts", order=10)
    def init_prompts(session: Session):
        ...

    # Auto-discover and run all initializers
    discover_and_run_initializers(session)
"""

from typing import Callable, List, Tuple
from sqlmodel import Session
from loguru import logger


# Global registry: stores all initializers
_INITIALIZERS: List[Tuple[int, str, Callable]] = []


def initializer(name: str, order: int = 100):
    """Initializer decorator

    Registers a function as an initializer, supporting auto-discovery and ordered execution.

    Args:
        name: initializer name, used for log output
        order: execution order, lower numbers run first (default 100)

    Example:
        @initializer(name="prompts", order=10)
        def init_prompts(session: Session):
            logger.info("Initializing prompts...")
    """
    def decorator(func: Callable):
        # Register to global list
        _INITIALIZERS.append((order, name, func))
        logger.debug(f"[Initializer Registry] {name} (order={order}) -> {func.__name__}")
        return func
    return decorator


def get_registered_initializers() -> List[Tuple[int, str, Callable]]:
    """Get all registered initializers

    Returns:
        List of initializers sorted by order [(order, name, func), ...]
    """
    return sorted(_INITIALIZERS, key=lambda x: x[0])


def discover_initializers():
    """Log the number of registered initializers

    All initializer modules are imported in app.bootstrap.__init__.py,
    and decorators auto-register on package import.
    """
    logger.debug(f"[Initializer Discovery] Loaded {len(_INITIALIZERS)} initializers")


def run_initializers(session: Session):
    """Execute all registered initializers

    Execute initializers in order.

    Args:
        session: database session
    """
    initializers = get_registered_initializers()

    if not initializers:
        logger.warning("[Initializers] No registered initializers found")
        return

    logger.info(f"[Initializers] Found {len(initializers)} initializers, starting execution...")

    for order, name, func in initializers:
        try:
            logger.info(f"[Initializers] Executing: {name} (order={order})")
            func(session)
        except Exception as e:
            logger.error(f"[Initializers] Execution failed {name}: {e}")
            raise


def discover_and_run_initializers(session: Session):
    """Auto-discover and execute all initializers

    This is the main entry function, which:
    1. Auto-discovers all initializer modules
    2. Executes all initializers in order

    Args:
        session: database session
    """
    discover_initializers()
    run_initializers(session)
