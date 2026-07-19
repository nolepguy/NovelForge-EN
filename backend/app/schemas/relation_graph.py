from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.relation_extract import RelationKind, RelationStance


CsvJsonFormat = Literal["json", "csv"]


class RelationGraphEvent(BaseModel):
    summary: str = Field(description="Event summary")
    volume_number: Optional[int] = Field(default=None, description="Volume number")
    chapter_number: Optional[int] = Field(default=None, description="Chapter number")


class RelationGraphKey(BaseModel):
    source: str = Field(description="Relation source entity")
    target: str = Field(description="Relation target entity")
    kind_en: str = Field(description="Relation English key")


class RelationGraphInput(BaseModel):
    source: str = Field(description="Relation source entity")
    target: str = Field(description="Relation target entity")
    kind_en: Optional[str] = Field(default=None, description="Relation English key")
    kind_cn: Optional[RelationKind] = Field(default=None, description="Relation Chinese type")
    kind: Optional[RelationKind] = Field(default=None, description="Relation Chinese type (compat field)")
    fact: Optional[str] = Field(default=None, description="Relation fact description")
    description: Optional[str] = Field(default=None, description="Relation description")
    a_to_b_addressing: Optional[str] = Field(default=None, description="A's address for B")
    b_to_a_addressing: Optional[str] = Field(default=None, description="B's address for A")
    recent_dialogues: List[str] = Field(default_factory=list, description="Recent dialogue evidence")
    recent_event_summaries: List[RelationGraphEvent] = Field(default_factory=list, description="Recent event evidence")
    stance: Optional[RelationStance] = Field(default=None, description="Stance: friendly/neutral/hostile")


class RelationGraphRecord(BaseModel):
    source: str
    target: str
    kind_en: str
    kind_cn: RelationKind
    kind: RelationKind
    fact: str
    a_to_b_addressing: Optional[str] = None
    b_to_a_addressing: Optional[str] = None
    recent_dialogues: List[str] = Field(default_factory=list)
    recent_event_summaries: List[RelationGraphEvent] = Field(default_factory=list)
    stance: Optional[RelationStance] = None
    updated_at: Optional[str] = None


class RelationGraphListRequest(BaseModel):
    project_id: int
    keyword: Optional[str] = None
    kinds: List[RelationKind] = Field(default_factory=list)
    stances: List[RelationStance] = Field(default_factory=list)
    offset: int = 0
    limit: int = 50


class RelationGraphListResponse(BaseModel):
    items: List[RelationGraphRecord] = Field(default_factory=list)
    total: int = 0


class RelationGraphUpsertRequest(BaseModel):
    project_id: int
    relation: RelationGraphInput


class RelationGraphDeleteRequest(BaseModel):
    project_id: int
    key: RelationGraphKey


class RelationGraphBatchDeleteRequest(BaseModel):
    project_id: int
    keys: List[RelationGraphKey] = Field(default_factory=list)


class RelationGraphBatchUpdateKindRequest(BaseModel):
    project_id: int
    keys: List[RelationGraphKey] = Field(default_factory=list)
    new_kind_en: Optional[str] = Field(default=None, description="New relation English key")
    new_kind_cn: Optional[RelationKind] = Field(default=None, description="New relation Chinese type")


class RelationGraphBatchUpdateStanceRequest(BaseModel):
    project_id: int
    keys: List[RelationGraphKey] = Field(default_factory=list)
    stance: Optional[RelationStance] = Field(default=None, description="New stance")


class RelationGraphBatchAppendEventsRequest(BaseModel):
    project_id: int
    keys: List[RelationGraphKey] = Field(default_factory=list)
    events: List[RelationGraphEvent] = Field(default_factory=list)
    max_size: int = 20


class RelationGraphBatchCreateRequest(BaseModel):
    project_id: int
    relations: List[RelationGraphInput] = Field(default_factory=list)


class RelationGraphWriteResponse(BaseModel):
    affected: int = 0


class RelationGraphExportRequest(BaseModel):
    project_id: int
    format: CsvJsonFormat = "json"
    keys: List[RelationGraphKey] = Field(default_factory=list)


class RelationGraphExportResponse(BaseModel):
    filename: str
    mime_type: str
    content: str


class RelationGraphImportRequest(BaseModel):
    project_id: int
    format: CsvJsonFormat = "json"
    content: str


class RelationGraphImportResponse(BaseModel):
    created: int = 0
    updated: int = 0
    failed: int = 0
    errors: List[str] = Field(default_factory=list)


class RelationGraphKindOption(BaseModel):
    kind_cn: RelationKind
    kind_en: str


class RelationGraphMetaResponse(BaseModel):
    kinds: List[RelationGraphKindOption] = Field(default_factory=list)
    stances: List[RelationStance] = Field(default_factory=list)
