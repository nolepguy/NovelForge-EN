from __future__ import annotations

from typing import Dict, Any

# Centrally export all response/nested models that need to be exposed in OpenAPI
from app.schemas.wizard import (
    Text,
	WorldBuilding, Blueprint,
	VolumeOutline, ChapterOutline,
	SpecialAbilityResponse, OneSentence, ParagraphOverview,
	CharacterCard, SceneCard, StoryLine, StageLine, 
	Tags, WorldviewTemplate, Chapter,
  WritingGuide, ReviewResultCardContent
)
from app.schemas.entity import ConceptCard, ItemCard, OrganizationCard
from app.schemas.workflow_models import BookStageChunkPlan, BookStageFinalPlan

RESPONSE_MODEL_MAP: Dict[str, Any] = {
    "Text": Text,
	'Tags': Tags,
	'SpecialAbilityResponse': SpecialAbilityResponse,
	'OneSentence': OneSentence,
	'ParagraphOverview': ParagraphOverview,
	'WorldBuilding': WorldBuilding,
	'WorldviewTemplate': WorldviewTemplate,
	'Blueprint': Blueprint,
	# Use unwrapped models
	'VolumeOutline': VolumeOutline,
 	'WritingGuide': WritingGuide,
    'ReviewResultCardContent': ReviewResultCardContent,
	'ChapterOutline': ChapterOutline,
	'Chapter': Chapter,
	# Base schema, auto-included in OpenAPI
	'CharacterCard': CharacterCard,
	'SceneCard': SceneCard,
	'OrganizationCard': OrganizationCard,
	'ItemCard': ItemCard,
	'ConceptCard': ConceptCard,
	# Explicitly export nested types for frontend field tree parsing
	'StageLine': StageLine,
	'StoryLine': StoryLine,
	# Workflow-specific structural models
	'BookStageChunkPlan': BookStageChunkPlan,
	'BookStageFinalPlan': BookStageFinalPlan,
}
