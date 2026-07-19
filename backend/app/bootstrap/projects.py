"""Reserved project initialization

Initialize system reserved projects.
"""

from sqlmodel import Session, select
from loguru import logger

from app.db.models import Project
from .registry import initializer


@initializer(name="Reserved Project", order=40)
def init_reserved_project(session: Session) -> None:
    """Initialize reserved project

    Ensure a reserved project __free__ exists, used for archiving free cards across projects.

    Args:
        session: database session
    """
    FREE_NAME = "__free__"
    exists = session.exec(select(Project).where(Project.name == FREE_NAME)).first()
    if not exists:
        p = Project(name=FREE_NAME, description="System reserved project: stores free cards")
        session.add(p)
        session.commit()
        session.refresh(p)
        logger.info(f"Created reserved project: {FREE_NAME} (id={p.id})")
    else:
        # Incremental updates can be done here (e.g. description field)
        pass
