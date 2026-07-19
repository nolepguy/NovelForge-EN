
from typing import List, Optional, Tuple
from sqlmodel import Session, select

from app.db.models import Project, Workflow
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.card_service import CardService
from app.services.kg_provider import get_provider


FREE_PROJECT_NAME = "__free__"

# Get or create the reserved project (__free__)
def get_or_create_free_project(session: Session) -> Project:
    proj = session.exec(select(Project).where(Project.name == FREE_PROJECT_NAME)).first()
    if proj:
        return proj
    proj = Project(name=FREE_PROJECT_NAME, description="System reserved project: stores free cards")
    session.add(proj)
    session.commit()
    session.refresh(proj)
    return proj


def get_projects(session: Session) -> List[Project]:
    statement = select(Project).order_by(Project.id.desc())
    return session.exec(statement).all()


def get_project(session: Session, project_id: int) -> Optional[Project]:
    statement = (
        select(Project)
        .where(Project.id == project_id)
    )
    return session.exec(statement).first()




from typing import List, Optional, Tuple

def create_project(session: Session, project_in: ProjectCreate) -> Tuple[Project, List[int]]:
    # Check if project name already exists
    from sqlmodel import select
    existing_project = session.exec(
        select(Project).where(Project.name == project_in.name)
    ).first()
    
    if existing_project:
        raise ValueError(f"Project name already exists: {project_in.name}")
    
    db_project = Project.model_validate(project_in)
    session.add(db_project)
    session.commit()
    session.refresh(db_project)
    
    triggered_run_ids = []
    # Trigger project creation event
    try:
        from app.core import emit_event
        
        event_data = {
            "session": session,
            "project_id": db_project.id,
            "template": project_in.template,  # Pass template identifier
        }
        
        emit_event("project.created", event_data)
        triggered_run_ids = event_data.get("triggered_run_ids", [])
    except Exception:
        # Do not block project creation
        pass
    
    # Refresh to load newly created cards into project relationships
    session.refresh(db_project)
    
    return db_project, triggered_run_ids


def update_project(session: Session, project_id: int, project_in: ProjectUpdate) -> Optional[Project]:
    db_project = session.get(Project, project_id)
    if not db_project:
        return None
    project_data = project_in.model_dump(exclude_unset=True)
    for key, value in project_data.items():
        setattr(db_project, key, value)
    session.add(db_project)
    session.flush()
    session.refresh(db_project)
    return db_project


def delete_project(session: Session, project_id: int) -> bool:
    project = session.get(Project, project_id)
    if not project:
        return False
    # Reserved projects cannot be deleted
    if getattr(project, 'name', None) == FREE_PROJECT_NAME:
        return False
    # First delete the project record from the database
    session.delete(project)
    session.commit()
    # Then clean up all entities and relations for this project in the graph database
    try:
        kg = get_provider()
        kg.delete_project_graph(project_id)
    except Exception:
        # Avoid impacting the main flow when the graph database is unavailable
        pass
    return True 