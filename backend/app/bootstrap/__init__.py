"""Bootstrap initialization module

A decorator-based plugin initialization system.

## Architecture

Uses the @initializer decorator for auto-discovery and registration:
- Each initializer is a standalone file, declared via decorator
- On startup, all are scanned and executed in order
- Adding new initializers requires no changes to existing code

## Module structure

- registry.py: decorators and auto-discovery mechanism
- prompts.py: prompt initialization
- card_types.py: card type initialization
- knowledge.py: knowledge base initialization
- projects.py: reserved project initialization
- workflows.py: workflow initialization

## Usage

### Define an initializer
```python
from .registry import initializer

@initializer(name="My Feature", order=60)
def init_my_feature(session: Session):
    logger.info("Initializing my feature...")
    # ... initialization logic
```

### Auto-execute all initializers
```python
from app.bootstrap.registry import discover_and_run_initializers

with Session(engine) as session:
    discover_and_run_initializers(session)
```

## Execution order

Initializers execute in ascending order value:
- 10: Prompts
- 20: Card Types
- 30: Knowledge Base
- 40: Reserved Project
- 50: Workflows
- 60+: Custom initializers
"""

# Export core functionality
from .registry import initializer, discover_and_run_initializers

# Import all initializer modules to trigger decorator registration
from . import prompts
from . import card_types
from . import workflows
from . import knowledge

__all__ = [
    'initializer',
    'discover_and_run_initializers',
]
