
from sqlmodel import SQLModel
from typing import Optional

# 1. Define base model (Base Model)
class ProjectBase(SQLModel):
    name: str
    description: Optional[str] = None

# 2. Model used to create a project (Create Schema)
class ProjectCreate(ProjectBase):
    # Project template identifier (e.g. "snowflake"), used to trigger the corresponding initialization workflow
    # None means a blank project, triggering no workflow
    template: Optional[str] = None

# 3. Model used to read a project from the database (Read Schema)
class ProjectRead(ProjectBase):
    id: int

# 4. Model used to update a project (Update Schema)
class ProjectUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
