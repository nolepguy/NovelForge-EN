from typing import Any, AsyncIterator, Dict

from loguru import logger
from pydantic import BaseModel, Field
from sqlmodel import select

from app.db.models import Project
from ...registry import register_node
from ..base import BaseNode


class SelectProjectInput(BaseModel):
    """Select project input"""

    project_id: int | None = Field(
        default=None,
        description="Project ID",
        json_schema_extra={"x-component": "ProjectSelect"},
    )
    project_name: str | None = Field(
        default=None,
        description="Project name (resolved by name when project_id is empty; provide either name or ID)",
        json_schema_extra={"x-component": "ProjectSelect"},
    )


class SelectProjectOutput(BaseModel):
    """Select project output"""

    project_id: int = Field(..., description="Project ID")
    project: Dict[str, Any] = Field(..., description="Project object")


@register_node
class SelectProjectNode(BaseNode[SelectProjectInput, SelectProjectOutput]):
    node_type = "Logic.SelectProject"
    category = "logic"
    label = "Select Project"
    description = "Select and output a project; can obtain a specific project by name or ID, the result includes the project ID"

    input_model = SelectProjectInput
    output_model = SelectProjectOutput

    async def execute(self, inputs: SelectProjectInput) -> AsyncIterator[SelectProjectOutput]:
        session = self.context.session

        project = None
        if inputs.project_id is not None:
            project = session.get(Project, inputs.project_id)

        if project is None and inputs.project_name:
            project = session.exec(
                select(Project).where(Project.name == inputs.project_name)
            ).first()
            if project is None:
                candidates = session.exec(select(Project)).all()
                lowered = inputs.project_name.lower()
                matches = [
                    item
                    for item in candidates
                    if lowered in (item.name or "").lower()
                ]
                if len(matches) == 1:
                    project = matches[0]
                elif len(matches) > 1:
                    raise ValueError(
                        f"Project name matched multiple candidates: {inputs.project_name}"
                    )

        if not project:
            raise ValueError(
                f"Project does not exist: id={inputs.project_id}, name={inputs.project_name}"
            )

        logger.info(f"[SelectProject] Selected project: {project.name} (id={project.id})")

        yield SelectProjectOutput(
            project_id=project.id,
            project={
                "id": project.id,
                "name": project.name,
                "description": project.description,
            },
        )