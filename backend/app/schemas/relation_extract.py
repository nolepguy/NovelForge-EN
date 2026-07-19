from __future__ import annotations

from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field



# Extended relation types (enum, single source maintained)
RelationKind = Literal[
    # Character relations
    'Alliance','Teammate','Fellow Disciple','Hostile','Family','Master-Student','Rival','Companion','Superior','Subordinate','Mentor',
    # Character ↔ Organization
    'Affiliated','Member','Leader','Founder',
    # Entity and item / concept
    'Owns','Uses','Cultivates','Comprehends','Carries','Maps To',
    # Organization ↔ Scene
    'Controls','Located In',
    # General and fallback
    'Influences','Counters','About','Other'
]
RelationStance = Literal['Friendly', 'Neutral', 'Hostile']
RELATION_STANCES: tuple[RelationStance, ...] = ('Friendly', 'Neutral', 'Hostile')

# Unified English-slug mapping (single source) — kept for compatibility (e.g. existing slug-based graph read/write logic)
CN_TO_EN_KIND: Dict[str, str] = {
    'Alliance': 'ally',
    'Teammate': 'team',
    'Fellow Disciple': 'fellow',
    'Hostile': 'enemy',
    'Family': 'family',
    'Master-Student': 'mentor',
    'Rival': 'rival',
    'Companion': 'partner',
    'Superior': 'superior',
    'Subordinate': 'subordinate',
    'Mentor': 'guide',

    'Affiliated': 'member_of',
    'Member': 'member',
    'Leader': 'lead',
    'Founder': 'found',

    'Owns': 'own',
    'Uses': 'use',
    'Cultivates': 'practice',
    'Comprehends': 'realize',
    'Carries': 'carry',
    'Maps To': 'map_to',


    'Controls': 'control',
    'Located In': 'locate_in',

    'Influences': 'influence',
    'Counters': 'counter',
    'About': 'about',
    'Other': 'other',
}
EN_TO_CN_KIND: Dict[str, str] = {v: k for k, v in CN_TO_EN_KIND.items()}


class RecentEventSummary(BaseModel):
    summary: str = Field(description="One-sentence summary of recent events between A and B (recommended to merge into one for this extraction)")
    volume_number: Optional[int] = Field(default=None, description="Volume number where it occurred (leave empty, system can fill in)")
    chapter_number: Optional[int] = Field(default=None, description="Chapter number where it occurred (leave empty, system can fill in)")


class RelationItem(BaseModel):
    a: str = Field(description="Entity A name (one of the participants)")
    b: str = Field(description="Entity B name (one of the participants)")
    kind: RelationKind = Field(description="Relation type")
    description: Optional[str] = Field(default=None, description="Brief text description of this relation (optional)")
    # Mutual addressing (optional, does not need to appear in recent dialogues)
    a_to_b_addressing: Optional[str] = Field(default=None, description="A's addressing word for B, e.g.: senior brother, sir. Only extract when both A and B are characters.")
    b_to_a_addressing: Optional[str] = Field(default=None, description="B's addressing word for A. Only extract when both A and B are characters.")
    # Recent evidence (for tone consistency and fact tracing) — recommend each ≤3 entries
    recent_dialogues: List[str] = Field(default_factory=list, description="Recent dialogue fragments (recommend at least one line from each side; can merge fragments with A: '...', B: '...'; length ≥20 chars). Only extract when both A and B are characters.")
    recent_event_summaries: List[RecentEventSummary] = Field(default_factory=list, description="Recent events that directly occurred between A and B; if the same fact involves three or more parties, record it only once on the most direct pair. Prioritize character-character pairings; only record the corresponding relation when the event subjects are indeed A and B as character-organization / organization-organization, to avoid mistaking organizational background for bilateral events.")
    # Stance (optional): Friendly / Neutral / Hostile
    stance: Optional[RelationStance] = Field(default=None, description="A's overall stance toward B (optional)")


class RelationExtraction(BaseModel):
    relations: List[RelationItem] = Field(default_factory=list)
