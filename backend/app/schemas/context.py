from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.relation_extract import RelationItem


class AssembleContextRequest(BaseModel):
	project_id: Optional[int] = Field(default=None, description="Project ID")
	volume_number: Optional[int] = Field(default=None, description="Volume number")
	chapter_number: Optional[int] = Field(default=None, description="Chapter number")
	chapter_id: Optional[int] = Field(default=None, description="Chapter card ID (optional)")
	participants: Optional[List[str]] = Field(default=None, description="List of participating entity names")
	current_draft_tail: Optional[str] = Field(default=None, description="Context template (draft tail)")
	recent_chapters_window: Optional[int] = Field(default=None, description="Recent window (kept for future extension)")


class ItemSummary(BaseModel):
	name: str = Field(..., description="Item name")
	category: str = Field(default="", description="Item category")
	description: str = Field(default="", description="Item summary")
	owner_hint: Optional[str] = Field(default=None, description="Owner hint")
	current_state: Optional[str] = Field(default=None, description="Current state")
	power_or_effect: Optional[str] = Field(default=None, description="Ability or usage")
	constraints: Optional[str] = Field(default=None, description="Constraints")
	important_events: List[str] = Field(default_factory=list, description="Important events")


class ConceptSummary(BaseModel):
	name: str = Field(..., description="Concept name")
	category: str = Field(default="", description="Concept category")
	description: str = Field(default="", description="Concept summary")
	rule_definition: str = Field(default="", description="Rule definition")
	cost: Optional[str] = Field(default=None, description="Cost or price")
	mastery_hint: Optional[str] = Field(default=None, description="Mastery hint")
	known_by: List[str] = Field(default_factory=list, description="Known masters")
	counter_relations: List[str] = Field(default_factory=list, description="Opposition or counter relations")


class FactsStructured(BaseModel):
	fact_summaries: List[str] = Field(default_factory=list, description="Key fact summaries")
	relation_summaries: List[RelationItem] = Field(default_factory=list, description="Relation summaries (including recent dialogue/events)")
	item_summaries: List[ItemSummary] = Field(default_factory=list, description="Item summaries")
	concept_summaries: List[ConceptSummary] = Field(default_factory=list, description="Concept summaries")


class AssembleContextResponse(BaseModel):
	facts_subgraph: str = Field(default="", description="Text echo of the fact subgraph (optional, echo only)")
	budget_stats: Dict[str, Any] = Field(default_factory=dict, description="Context word budget stats (may include nested parts dict)")
	facts_structured: Optional[FactsStructured] = Field(default=None, description="Structured fact subgraph")


class ContextSettingsModel(BaseModel):
	recent_chapters_window: int
	total_context_budget_chars: int
	soft_budget_chars: int
	quota_recent: int
	quota_older_summary: int
	quota_facts: int


class UpdateContextSettingsRequest(BaseModel):
	recent_chapters_window: Optional[int] = None
	total_context_budget_chars: Optional[int] = None
	soft_budget_chars: Optional[int] = None
	quota_recent: Optional[int] = None
	quota_older_summary: Optional[int] = None
	quota_facts: Optional[int] = None
