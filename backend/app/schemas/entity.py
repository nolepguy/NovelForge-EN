from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


_LIFE_SPAN_ALIASES = {
    'long term': 'Long Term', 'long-term': 'Long Term', 'long_term': 'Long Term', 'longterm': 'Long Term', 'long': 'Long Term',
    'short term': 'Short Term', 'short-term': 'Short Term', 'short_term': 'Short Term', 'shortterm': 'Short Term', 'short': 'Short Term',
}

DynamicInfoType = Literal[
    "System / Simulator / Special Ability",
    "Level / Cultivation Realm",
    "Equipment / Treasure",
    "Knowledge / Intel",
    "Assets / Territory",
    "Techniques / Skills",
    "Bloodline / Constitution",
    "Thoughts / Goal Snapshot",
]

DYNAMIC_INFO_TYPES: List[str] = [
    "System / Simulator / Special Ability",
    "Level / Cultivation Realm",
    "Equipment / Treasure",
    "Knowledge / Intel",
    "Assets / Territory",
    "Techniques / Skills",
    "Bloodline / Constitution",
    "Thoughts / Goal Snapshot",
]

EntityType = Literal["character", "scene", "organization", "item", "concept"]


class DynamicInfoItem(BaseModel):
    id: int = Field(-1, description="Manually set, no need to generate; if -1 when merging, an auto-incremented index will be assigned")
    info: str = Field(description="Brief description of the specific dynamic info")


class DynamicInfo(BaseModel):
    name: str = Field(description="Character name")
    dynamic_info: Dict[DynamicInfoType, List[DynamicInfoItem]] = Field(
        default_factory=dict,
        description="Dynamic info dict, key is category, value is list of info items",
    )

    @staticmethod
    def _normalize_dynamic_info_dict(v: Any) -> Dict[str, Any]:
        if not isinstance(v, dict):
            return {}
        normalized: Dict[str, Any] = {}
        allowed = set(DYNAMIC_INFO_TYPES)
        for k, arr in v.items():
            key = k if isinstance(k, str) else str(k)
            if key in allowed:
                normalized[key] = arr
        return normalized

    @field_validator("dynamic_info", mode="before")
    @classmethod
    def _normalize_keys(cls, v: Any) -> Dict[str, Any]:
        return cls._normalize_dynamic_info_dict(v)


class DeletionInfo(BaseModel):
    name: str = Field(description="Character name")
    dynamic_type: DynamicInfoType = Field(description="Dynamic info type")
    id: int = Field(gt=0, description="ID of the dynamic info to delete")


class UpdateDynamicInfo(BaseModel):
    info_list: List[DynamicInfo] = Field(description="List of dynamic info to update")
    delete_info_list: Optional[List[DeletionInfo]] = Field(default=None, description="Optional deletion list")


class Entity(BaseModel):
    name: str = Field(..., min_length=1, description="Entity name")
    entity_type: EntityType = Field(..., description="Entity type")
    life_span: Literal["Long Term", "Short Term"] = Field(description="Lifecycle of the entity in the story")

    @field_validator("life_span", mode="before")
    @classmethod
    def _normalize_life_span(cls, v: Any) -> Any:
        if isinstance(v, str):
            mapped = _LIFE_SPAN_ALIASES.get(v.strip().lower())
            if mapped:
                return mapped
        return v


class CharacterCardCore(Entity):
    last_appearance: Optional[Tuple[int, int]] = Field(default=None, description="Last appearance time: [volume number, chapter number]")
    role_type: Literal["Protagonist", "Supporting Character", "NPC", "Antagonist"] = Field("Supporting Character", description="Character role")
    born_scene: str = Field(description="Appearance / resident scene")
    description: str = Field(description="One-line intro and background description")


class CharacterCard(CharacterCardCore):
    entity_type: EntityType = Field("character", description="Entity type marker")
    personality: str = Field(description="Personality keywords")
    core_drive: str = Field(description="Core drive / goal")
    character_arc: str = Field(description="Character arc throughout the book")
    dynamic_info: Dict[DynamicInfoType, List[DynamicInfoItem]] = Field(
        default_factory=dict,
        description="Dynamic info dict, leave empty, system maintains automatically",
    )

    @field_validator("dynamic_info", mode="before")
    @classmethod
    def _normalize_dynamic_info(cls, v: Any) -> Dict[str, Any]:
        return DynamicInfo._normalize_dynamic_info_dict(v)


class SceneCard(Entity):
    entity_type: EntityType = Field("scene", description="Entity type marker")
    description: str = Field(description="One-line intro of scene / map")
    function_in_story: str = Field(description="Role in the plot")
    dynamic_state: List[str] = Field(default_factory=list, description="Current state, supplemented and maintained by the system gradually")
    last_appearance: Optional[Tuple[int, int]] = Field(default=None, description="Last appearance time: [volume number, chapter number]")


class OrganizationCard(Entity):
    entity_type: EntityType = Field("organization", description="Entity type marker")
    description: str = Field(description="Organization / faction description")
    influence: Optional[str] = Field(default=None, description="Influence scope / power of this organization on the world")
    relationship: Optional[List[str]] = Field(default=None, description="Relationships with other organizations")
    dynamic_state: List[str] = Field(default_factory=list, description="Current state, supplemented and maintained by the system gradually")
    last_appearance: Optional[Tuple[int, int]] = Field(default=None, description="Last appearance time: [volume number, chapter number]")


class SceneCardMemory(Entity):
    entity_type: EntityType = Field("scene", description="scene entity type")
    life_span: Optional[Literal["Long Term", "Short Term"]] = Field(default=None, description="scene lifespan")
    description: str = Field(default="", description="scene description")
    function_in_story: str = Field(default="", description="scene function in story")
    dynamic_state: List[str] = Field(default_factory=list, description="scene dynamic state summary")


class OrganizationCardMemory(Entity):
    entity_type: EntityType = Field("organization", description="organization entity type")
    life_span: Optional[Literal["Long Term", "Short Term"]] = Field(default=None, description="organization lifespan")
    description: str = Field(default="", description="organization description")
    influence: Optional[str] = Field(default=None, description="organization influence")
    relationship: List[str] = Field(default_factory=list, description="organization relationships")
    dynamic_state: List[str] = Field(default_factory=list, description="organization dynamic state summary")


class ItemCard(Entity):
    entity_type: EntityType = Field("item", description="Entity type")
    life_span: Literal["Long Term", "Short Term"] = Field("Long Term", description="Lifecycle of the item in the story")
    category: str = Field(
        default="",
        description="Item category",
        json_schema_extra={"x-knowledge-source": "Item category"},
    )
    description: str = Field(default="", description="One-line intro or background of the item")
    owner_hint: Optional[str] = Field(default=None, description="Current or common owner")
    power_or_effect: Optional[str] = Field(default=None, description="Item ability, effect or usage")
    constraints: Optional[str] = Field(default=None, description="Usage restrictions, cost or trigger conditions")
    current_state: Optional[str] = Field(default=None, description="Item current state")
    important_events: List[str] = Field(default_factory=list, description="Summary of important events related to the item")

class ConceptCard(Entity):
    entity_type: EntityType = Field("concept", description="Entity type")
    life_span: Literal["Long Term", "Short Term"] = Field("Long Term", description="Lifecycle of the concept in the story")
    category: str = Field(
        default="",
        description="Concept category",
        json_schema_extra={"x-knowledge-source": "Concept category"},
    )
    description: str = Field(default="", description="Concept intro")
    rule_definition: str = Field(default="", description="Rule definition, application method or core mechanism")
    cost: Optional[str] = Field(default=None, description="Cost of using or mastering this concept")
    counter_relations: List[str] = Field(default_factory=list, description="Opposition, counter or restriction relationships")
    mastery_hint: Optional[str] = Field(default=None, description="Mastery threshold, comprehension method or common users")
    known_by: List[str] = Field(default_factory=list, description="Entities that are known to master, know or be affected")
