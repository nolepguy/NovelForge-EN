from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class BookStageItem(BaseModel):
    """Book-splitting stage item (for stage division/merging)"""

    stage_name: str = Field(description="Stage name, e.g.: Crossing and Sprouting")
    chapter_start: int = Field(description="Stage starting chapter number (book-wide sequence, starting from 1)", ge=1)
    chapter_end: int = Field(description="Stage ending chapter number (book-wide sequence, starting from 1)", ge=1)
    stage_outline: str = Field(
        description=(
            "Stage story outline (Markdown text), must include: stage cause, stage goal, conflicts and obstacles, "
            "key event chain (at least 3), character relationship/ability changes, stage result and next stage hook; "
            "requires detail and executability, emphasizing changes to the protagonist and main characters."
        )
    )

    stage_summary: Optional[str] = Field(
        default=None,
        description="Stage plot summary (400~800 words), use fluent narrative to summarize the stage's plot progression",
    )


class BookStageChunkPlan(BaseModel):
    """Stage division result for a single chapter context chunk"""

    stages: List[BookStageItem] = Field(
        default_factory=list,
        description="Suggested stage list within the current context chunk (1~N allowed)"
    )


class BookStageFinalPlan(BaseModel):
    """Final stage plan for the whole book"""

    stages: List[BookStageItem] = Field(
        default_factory=list,
        description="Final stage division for the whole book (must satisfy the max stage count constraint)"
    )
