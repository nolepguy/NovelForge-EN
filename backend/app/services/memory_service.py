from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import Session
from sqlalchemy.orm.attributes import flag_modified

from loguru import logger

from app.schemas.relation_extract import RelationExtraction, CN_TO_EN_KIND
from app.schemas.entity import Entity
from app.services.ai.core import llm_service
from pydantic import BaseModel
# Import dynamic info models
from app.schemas.entity import UpdateDynamicInfo, DynamicInfoType, DynamicInfoItem, DeletionInfo
from app.db.models import Card, CardType
from sqlmodel import select

# Import typed participant models
from app.schemas.memory import ParticipantTyped

# Load prompts from database
from app.services import prompt_service
from app.services.memory_extractors.memory_base import log_extract_prompt
from app.services.memory_extractors.registry_factory import get_memory_extractor_registry

# Use the swappable knowledge graph Provider
from app.services.kg_provider import get_provider, KnowledgeGraphUnavailableError

# Subject-object type constraints (suggestion table)
_ALLOWED_PAIRS: Dict[str, List[Tuple[str, str]]] = {
    'Alliance': [('character','character')],
    'Teammate': [('character','character')],
    'Fellow Disciple': [('character','character')],
    'Hostile': [('character','character')],
    'Family': [('character','character')],
    'Master-Student': [('character','character')],
    'Rival': [('character','character')],
    'Companion': [('character','character')],
    'Superior': [('character','character')],
    'Subordinate': [('character','character')],

    'Affiliated': [('character','organization')],
    'Member': [('character','organization')],
    'Leader': [('character','organization'), ('organization','organization')],
    'Founder': [('character','organization') , ('organization','organization')],

    'Owns': [('character','item'), ('organization','item')],
    'Uses': [('character','item'), ('organization','item')],
    'Cultivates': [('character','concept')],
    'Comprehends': [('character','concept')],
    'Carries': [('item','concept')],
    'Maps To': [('concept','item')],

    'Controls': [('organization','scene')],
    'Located In': [('scene','organization')],

    
    'About': [('character','character'), ('organization','organization'), ('character','organization'), ('organization','character'),
       #    ('item','item'), ('concept','concept'), ('character','concept'), ('character','item')
           ],
    'Other': [('character','character'), ('organization','organization'), ('character','organization'), ('organization','character'), ('item','item'), ('concept','concept'), ('character','concept'), ('character','item')],
    # 'Influences': [('character','character'), ('organization','organization'), ('character','organization'), ('organization','character'), ('item','item'), ('concept','concept'), ('character','concept'), ('character','item'), ('scene','organization'), ('organization','scene')],
    # 'Counters': [('item','item'), ('concept','concept'), ('character','character')],
}

# # Simplified: infer entity type from card type name
# _CARDTYPE_TO_ENTITYTYPE: Dict[str, str] = {
#     'Character Card': 'character',
#     'Scene Card': 'scene',
#     'Organization Card': 'organization',
#     # 'Item Card': 'item',
#     # 'Concept Card': 'concept',
# }

def _guess_entity_type(session: Session, project_id: int, name: str) -> Optional[str]:
    try:
        # Find the card with title == name in this project and read its type name
        st = select(Card).where(Card.project_id == project_id, Card.title == name)
        card = session.exec(st).first()
        if not card:
            return None
        ct = card.card_type
        if not ct:
            return None
        
        # Fix: card.content is already a dict, should use model_validate instead of model_validate_json
        entity=Entity.model_validate(card.content)
        return str(entity.entity_type)
        # return _CARDTYPE_TO_ENTITYTYPE.get(ct.name or '', None)
    except Exception as e:
        logger.error(f"Error guessing entity type: {e}")
        return None


# Upper limit per category for dynamic info (can be adjusted as needed)
DYNAMIC_INFO_LIMITS: Dict[str, int] = {
    "System / Simulator / Special Ability": 3,
    "Level / Cultivation Realm": 3,
    "Equipment / Treasure": 3,
    "Knowledge / Intel": 3,
    "Assets / Territory": 3,
    "Techniques / Skills": 3,
    "Bloodline / Constitution": 3,
    "Thoughts / Goal Snapshot": 3,
}

class MemoryService:
    def __init__(self, session: Session):
        self.session = session
        self.graph = get_provider()
        self.extractor_registry = get_memory_extractor_registry()

    def list_extractors(self) -> List[Dict[str, Any]]:
        return [
            {
                "code": extractor.code,
                "name": extractor.name,
                "target": extractor.target,
                "preview_supported": extractor.preview_supported,
            }
            for extractor in self.extractor_registry.list_all()
        ]

    async def extract_preview(
        self,
        *,
        extractor_code: str,
        project_id: int | None,
        text: str,
        participants: Optional[List[ParticipantTyped]] = None,
        llm_config_id: int = 1,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        extra_context: Optional[str] = None,
        volume_number: Optional[int] = None,
        chapter_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        extractor = self.extractor_registry.get(extractor_code)
        typed_participants = participants or []
        data = await extractor.extract(
            service=self,
            session=self.session,
            project_id=project_id,
            text=text,
            participants=typed_participants,
            llm_config_id=llm_config_id,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            extra_context=extra_context,
            context={
                "volume_number": volume_number,
                "chapter_number": chapter_number,
            },
        )
        return {
            "extractor_code": extractor.code,
            "preview_data": data.model_dump(mode="json"),
            "affected_targets": extractor.build_affected_targets(data),
        }

    def apply_preview(
        self,
        *,
        extractor_code: str,
        project_id: int,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
        volume_number: Optional[int] = None,
        chapter_number: Optional[int] = None,
        participants: Optional[List[ParticipantTyped]] = None,
    ) -> Dict[str, Any]:
        extractor = self.extractor_registry.get(extractor_code)
        preview_data = extractor.output_model.model_validate(data)
        result = extractor.persist(
            service=self,
            session=self.session,
            project_id=project_id,
            data=preview_data,
            options=options,
            context={
                "volume_number": volume_number,
                "chapter_number": chapter_number,
                "participants": participants or [],
            },
        )
        return {
            "success": True,
            "written": int(result.get("written", 0)),
            "updated_card_count": int(result.get("updated_card_count", 0)),
            "updated_relation_count": int(
                result.get("updated_relation_count", result.get("written", 0) if extractor.target == "graph" else 0)
            ),
            "affected_targets": extractor.build_affected_targets(preview_data),
            "raw_result": result,
        }

    async def extract_relations_preview(
        self,
        *,
        text: str,
        participants: Optional[List[ParticipantTyped]] = None,
        llm_config_id: int = 1,
        timeout: Optional[float] = None,
        prompt_name: Optional[str] = "Relation Extraction",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> RelationExtraction:
        prompt = prompt_service.get_prompt_by_name(self.session, prompt_name)
        system_prompt = prompt.template

        schema_json = RelationExtraction.model_json_schema()
        system_prompt += f"\n\nPlease strictly output in the following JSON Schema format:\n{schema_json}"

        participant_names = [p.name for p in participants] if participants else []
        user_prompt = (
            f"Participants: {', '.join(participant_names)}\n\n"
            "Please extract from the following text:\n"
            f"{text}"
        )
        log_extract_prompt("relation_preview", prompt_name, llm_config_id, system_prompt, user_prompt)
        res = await llm_service.generate_structured(
            session=self.session,
            llm_config_id=llm_config_id,
            user_prompt=user_prompt,
            output_type=RelationExtraction,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        if not isinstance(res, RelationExtraction):
            raise ValueError("LLM relation extraction failed: output format does not match RelationExtraction")
        return res

    async def extract_dynamic_info_preview(
        self,
        *,
        text: str,
        participants: Optional[List[ParticipantTyped]] = None,
        llm_config_id: int = 1,
        timeout: Optional[float] = None,
        prompt_name: Optional[str] = "Character Dynamic Info Extraction",
        project_id: Optional[int] = None,
        extra_context: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> UpdateDynamicInfo:
        prompt = prompt_service.get_prompt_by_name(self.session, prompt_name)
        if not prompt:
            raise ValueError(f"Prompt not found: {prompt_name}")
        system_prompt = prompt.template

        schema_json = UpdateDynamicInfo.model_json_schema()
        system_prompt += f"\n\nPlease strictly output in the following JSON Schema format:\n{schema_json}"

        ref_blocks: List[str] = []
        if extra_context:
            ref_blocks.append(f"[Outline reference info, extraction from this is not allowed]\n{extra_context}")

        character_participants = [p for p in (participants or []) if p.type == 'character']
        if project_id and character_participants:
            try:
                lines: List[str] = []
                for p in character_participants:
                    st = select(Card).where(Card.project_id == project_id, Card.title == p.name)
                    card = self.session.exec(st).first()
                    if not card or not card.card_type or card.card_type.name != 'Character Card':
                        continue
                    try:
                        from app.schemas.entity import CharacterCard

                        model = CharacterCard.model_validate(card.content or {})
                        di = model.dynamic_info or {}
                        if not di:
                            continue
                        lines.append(f"- {p.name}:")
                        for cat_enum, items in di.items():
                            if len(items) == 0:
                                continue
                            preview = "; ".join([f"[{it.id}] {it.info}" for it in items[:5]])
                            limit = DYNAMIC_INFO_LIMITS.get(cat_enum, 3)
                            info_line = f"  - {cat_enum} ({len(items)}/{limit}): {preview}"
                            lines.append(info_line)
                    except Exception as e:
                        logger.error(f"Error preparing dynamic info context: {e}")
                        continue
                if lines:
                    ref_blocks.append("[Existing character dynamic info (read-only reference)]\n" + "\n".join(lines))
            except Exception as e:
                logger.error(f"Error preparing dynamic info context: {e}")

        ref_text = ("\n\n".join(ref_blocks) + "\n\n") if ref_blocks else ""
        participant_text = ""
        if character_participants:
            participant_text = (
                "Characters currently participating in this chapter (for priority reference only, not a hard limit; if other important characters clearly appear in the text, they can also be extracted):\n"
                f"{', '.join([p.name for p in character_participants])}\n\n"
            )
        user_prompt = (
            f"{ref_text}"
            f"Chapter text:\n{text}\n\n"
            f"{participant_text}"
            "Please extract the dynamic info worth writing back to character cards from the text above."
        )

        log_extract_prompt("character_dynamic_preview", prompt_name, llm_config_id, system_prompt, user_prompt)
        res = await llm_service.generate_structured(
            session=self.session,
            llm_config_id=llm_config_id,
            user_prompt=user_prompt,
            output_type=UpdateDynamicInfo,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

        if not isinstance(res, UpdateDynamicInfo):
            raise ValueError("LLM dynamic info extraction failed: output format does not match UpdateDynamicInfo")

        return res

    async def extract_relations_llm(self, text: str, participants: Optional[List[ParticipantTyped]] = None, llm_config_id: int = 1, timeout: Optional[float] = None, prompt_name: Optional[str] = "Relation Extraction") -> RelationExtraction:
        # Prefer the default prompt; fall back to the hardcoded version if it does not exist
        prompt = prompt_service.get_prompt_by_name(self.session, prompt_name)
        system_prompt = prompt.template
        
        # Append the output model JSON Schema to the system prompt
        schema_json = RelationExtraction.model_json_schema()
        system_prompt += f"\n\nPlease strictly output in the following JSON Schema format:\n{schema_json}"

        participant_names = [p.name for p in participants] if participants else []
        user_prompt = (
            f"Participants: {', '.join(participant_names)}\n\n"
            "Please extract from the following text:\n"
            f"{text}"
        )
        log_extract_prompt("relation_extract", prompt_name, llm_config_id, system_prompt, user_prompt)
        res = await llm_service.generate_structured(
            session=self.session,
            llm_config_id=llm_config_id,
            user_prompt=user_prompt,
            output_type=RelationExtraction,
            system_prompt=system_prompt,
            timeout=timeout,
        )
        if not isinstance(res, RelationExtraction):
            raise ValueError("LLM relation extraction failed: output format does not match RelationExtraction")
        return res

    async def extract_dynamic_info_from_text(self, text: str, participants: Optional[List[ParticipantTyped]] = None, llm_config_id: int = 1, timeout: Optional[float] = None, prompt_name: Optional[str] = "Character Dynamic Info Extraction", project_id: Optional[int] = None, extra_context: Optional[str] = None) -> UpdateDynamicInfo:
        """Extract character dynamic info from text. participants is used as priority reference only, not as a hard limit."""
        prompt = prompt_service.get_prompt_by_name(self.session, prompt_name)
        if not prompt:
            raise ValueError(f"Prompt not found: {prompt_name}")
        system_prompt = prompt.template

        # Append JSON Schema to reinforce the output structure
        schema_json = UpdateDynamicInfo.model_json_schema()
        system_prompt += f"\n\nPlease strictly output in the following JSON Schema format:\n{schema_json}"

        # Reference context (entirely determined by the frontend) + existing character dynamic info
        ref_blocks: List[str] = []
        if extra_context:
            ref_blocks.append(f"[Outline reference info, extraction from this is not allowed]\n{extra_context}")

        # Use typed participants, only process the character type
        character_participants = [p for p in (participants or []) if p.type == 'character']
        if project_id and character_participants:
            try:
                lines: List[str] = []
                for p in character_participants:
                    st = select(Card).where(Card.project_id == project_id, Card.title == p.name)
                    card = self.session.exec(st).first()
                    if not card or not card.card_type or card.card_type.name != 'Character Card':
                        continue
                    try:
                        from app.schemas.entity import CharacterCard
                     
                        model = CharacterCard.model_validate(card.content or {})
    
                        di = model.dynamic_info or {}
                        if not di:
                            continue
                        lines.append(f"- {p.name}:")
                        for cat_enum, items in di.items():
                            if len(items)==0:
                                continue

                            # Add count/limit context (remove weight)
                            preview = "; ".join([f"[{it.id}] {it.info}" for it in items[:5]])
                            limit = DYNAMIC_INFO_LIMITS.get(cat_enum, 3)
                            info_line = f"  • {cat_enum} ({len(items)}/{limit}): {preview}"
                            lines.append(info_line)
                    except Exception as e:
                        logger.error(f"Error preparing dynamic info context: {e}")
                        continue
                if lines:
                    ref_blocks.append("[Existing character dynamic info (read-only reference)]\n" + "\n".join(lines))
            except Exception as e:
                logger.error(f"Error preparing dynamic info context: {e}")

        ref_text = ("\n\n".join(ref_blocks) + "\n\n") if ref_blocks else ""
        participant_text = ""
        if character_participants:
            participant_text = (
                "Characters currently participating in this chapter (for priority reference only, not a hard limit; if other important characters clearly appear in the text, they can also be extracted):\n"
                f"{', '.join([p.name for p in character_participants])}\n\n"
            )

        user_prompt = (
            f"{ref_text}"
            f"Chapter text:\n{text}\n\n"
            f"{participant_text}"
            "Please extract the dynamic info worth writing back to character cards from the text above."
        )

        log_extract_prompt("character_dynamic_extract", prompt_name, llm_config_id, system_prompt, user_prompt)
        res = await llm_service.generate_structured(
            session=self.session,
            llm_config_id=llm_config_id,
            user_prompt=user_prompt,
            output_type=UpdateDynamicInfo,
            system_prompt=system_prompt,
            timeout=timeout,
        )

        if not isinstance(res, UpdateDynamicInfo):
            raise ValueError("LLM dynamic info extraction failed: output format does not match UpdateDynamicInfo")
        
        return res

    def query_subgraph(
        self,
        project_id: int,
        participants: Optional[List[str]] = None,
        radius: int = 2,
        edge_type_whitelist: Optional[List[str]] = None,
        top_k: int = 50,
        max_chapter_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self.graph.query_subgraph(
            project_id=project_id,
            participants=participants,
            radius=radius,
            edge_type_whitelist=edge_type_whitelist,
            top_k=top_k,
            max_chapter_id=max_chapter_id,
        )

    def ingest_relations_from_llm(self, project_id: int, data: RelationExtraction, *, volume_number: Optional[int] = None, chapter_number: Optional[int] = None, participants_with_type: Optional[List[ParticipantTyped]] = None) -> Dict[str, Any]:
        # Write relation triples; also minimally persist addressing/event summaries/stance (as searchable evidence)
        # tuples: (subject, relation, object, attribute dict)
        triples_with_attrs: List[tuple[str, str, str, Dict[str, Any]]] = []

        DIALOGUES_QUEUE_SIZE = 2
        EVENTS_QUEUE_SIZE = 10

        # Create a participant type mapping for quick lookup
        participant_type_map = {p.name: p.type for p in participants_with_type} if participants_with_type else {}

        def _merge_queue(existing: List[Any], incoming: List[Any], key_fn=lambda x: x, max_size: int = 3) -> List[Any]:
            seen = set()
            merged: List[Any] = []
            # Old first then new, keeping newest at the tail, then trim to keep the tail (most recent)
            for it in (existing or []) + (incoming or []):
                k = key_fn(it)
                if k in seen:
                    continue
                seen.add(k)
                merged.append(it)
            if len(merged) <= max_size:
                return merged
            return merged[-max_size:]

        # Merge dialogues/event summaries by queue strategy (size=3) and serialize to dict
        merged_evidence_map: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

        # Prefetch: collect all (a, b, kind_cn) in this batch, do one subgraph query and filter in memory to avoid multiple round trips
        pairs: List[Tuple[str, str, str]] = []  # (a, b, kind_en)
        for r in (data.relations or []):
            pred = CN_TO_EN_KIND.get(r.kind or '', '')
            if pred:
                pairs.append((r.a, r.b, pred))

        # Build existing data index: key=(a,b,kind_en) -> {recent_dialogues, recent_event_summaries}
        existing_index: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        try:
            # Full set of participants (deduplicated)
            all_parts = list({p for t in pairs for p in (t[0], t[1])})
            if all_parts:
                sub = self.graph.query_subgraph(project_id=project_id, participants=all_parts, top_k=200)
                from app.schemas.relation_extract import EN_TO_CN_KIND
                for item in (sub.get("relation_summaries") or []):
                    try:
                        a0 = item.get("a"); b0 = item.get("b"); kind_cn = item.get("kind")
                        kind_en = CN_TO_EN_KIND.get(kind_cn or '', '')
                        if not (a0 and b0 and kind_en):
                            continue
                        key = (a0, b0, kind_en)
                        existing_index[key] = {
                            "recent_dialogues": item.get("recent_dialogues") or [],
                            "recent_event_summaries": item.get("recent_event_summaries") or [],
                        }
                    except Exception:
                        continue
        except Exception:
            existing_index = {}

        def _coerce_kind_by_types(kind_cn: str, type_a: Optional[str], type_b: Optional[str]) -> str:
            if not type_a or not type_b:
                return kind_cn
            allowed = _ALLOWED_PAIRS.get(kind_cn)
            if not allowed:
                return kind_cn
            if (type_a, type_b) in allowed:
                return kind_cn
            # Invalid: downgrade to about
            return 'About'

        for r in (data.relations or []):
            pred = CN_TO_EN_KIND.get(r.kind or '', '')
            if not pred:
                continue
            
            # Use the passed type info; fall back to guessing if missing
            type_a = participant_type_map.get(r.a) or _guess_entity_type(self.session, project_id, r.a)
            type_b = participant_type_map.get(r.b) or _guess_entity_type(self.session, project_id, r.b)

            # Constraint: correct the relation kind (Chinese) based on entity types
            kind_cn_fixed = _coerce_kind_by_types(r.kind, type_a, type_b)
            pred = CN_TO_EN_KIND.get(kind_cn_fixed, pred)
            
            # Prepare the attribute dict
            attributes = r.model_dump(exclude={"a", "b", "kind"}, exclude_none=True)

            # Backend forced filtering: if A or B is not character, remove addressing and dialogues
            if type_a != 'character' or type_b != 'character':
                attributes.pop('a_to_b_addressing', None)
                attributes.pop('b_to_a_addressing', None)
                attributes.pop('recent_dialogues', None)

            # Dialogues (filter by length)
            new_dialogues = [d.strip() for d in (attributes.get("recent_dialogues") or []) if isinstance(d, str) and len(d.strip()) >= 20]
            if new_dialogues:
                attributes["recent_dialogues"] = new_dialogues
            elif "recent_dialogues" in attributes:
                attributes.pop("recent_dialogues")


            # Event summaries (fill in volume/chapter)
            new_summaries: List[Dict[str, Any]] = []
            old_summaries_by_summary: Dict[str, Dict[str, Any]] = {}
            key = (r.a, r.b, pred)
            prev = existing_index.get(key, {})
            old_summaries: List[Dict[str, Any]] = list(prev.get("recent_event_summaries") or [])
            for old_item in old_summaries:
                summary_key = str(old_item.get("summary") or "").strip()
                if summary_key and summary_key not in old_summaries_by_summary:
                    old_summaries_by_summary[summary_key] = old_item

            for s in (r.recent_event_summaries or []):
                try:
                    item = s.model_dump()
                    summary_text = str(item.get("summary") or "").strip()
                    if not summary_text:
                        continue

                    matched_old = old_summaries_by_summary.get(summary_text)
                    if matched_old:
                        if item.get("volume_number") is None and matched_old.get("volume_number") is not None:
                            item["volume_number"] = matched_old.get("volume_number")
                        if item.get("chapter_number") is None and matched_old.get("chapter_number") is not None:
                            item["chapter_number"] = matched_old.get("chapter_number")

                    if volume_number is not None and item.get("volume_number") is None:
                        item["volume_number"] = int(volume_number)
                    if chapter_number is not None and item.get("chapter_number") is None:
                        item["chapter_number"] = int(chapter_number)

                    if summary_text:
                        new_summaries.append(item)
                except Exception:
                    continue

            # Read existing and merge into queue
            old_dialogues: List[str] = list(prev.get("recent_dialogues") or [])

            merged_dialogues = _merge_queue(old_dialogues, new_dialogues, key_fn=lambda x: x, max_size=DIALOGUES_QUEUE_SIZE)
            merged_summaries = _merge_queue(
                old_summaries,
                new_summaries,
                key_fn=lambda x: (
                    str((x or {}).get("summary") or "").strip(),
                    (x or {}).get("volume_number"),
                    (x or {}).get("chapter_number"),
                ),
                max_size=EVENTS_QUEUE_SIZE,
            )

            if merged_dialogues:
                attributes["recent_dialogues"] = merged_dialogues
            if merged_summaries:
                attributes["recent_event_summaries"] = merged_summaries

            # Clean up empty fields
            if not attributes.get("recent_dialogues") and "recent_dialogues" in attributes:
                attributes.pop("recent_dialogues", None)
            if not attributes.get("recent_event_summaries") and "recent_event_summaries" in attributes:
                attributes.pop("recent_event_summaries", None)
            
            triples_with_attrs.append((r.a, pred, r.b, attributes))
            
            # Return value (summary only)
            merged_evidence_map[key] = {
                "recent_dialogues": attributes.get("recent_dialogues", []),
                "recent_event_summaries": [s.get('summary') for s in attributes.get("recent_event_summaries", [])]
            }

        if triples_with_attrs:
            try:
                self.graph.ingest_triples_with_attributes(project_id, triples_with_attrs)
            except Exception as e:
                raise ValueError(f"Knowledge graph write failed: {e}")
        
        return {"written": len(triples_with_attrs), "merged_evidence": merged_evidence_map} 

    def update_dynamic_character_info(self, project_id: int, data: UpdateDynamicInfo, queue_size: int = 3) -> Dict[str, Any]:
        """
        Update the dynamic info of character cards, supporting additions and deletions.
        The maximum count per category uses the config in DYNAMIC_INFO_LIMITS; if not configured, falls back to queue_size (default 3).
        """
        from app.schemas.entity import CharacterCard

        # 1. Process deletions first
        if data.delete_info_list:
            for del_item in data.delete_info_list:
                # Psychological thoughts/goal snapshots: ignore deletion instructions from the LLM, let the system handle them by FIFO
                if str(del_item.dynamic_type) == 'Thoughts / Goal Snapshot':
                    continue
                st = select(Card).where(Card.project_id == project_id, Card.title == del_item.name)
                card = self.session.exec(st).first()
                if not card or card.card_type.name != 'Character Card':
                    continue
                
                try:
                    model = CharacterCard.model_validate(card.content or {})
                    if model.dynamic_info and del_item.dynamic_type in model.dynamic_info:
                        model.dynamic_info[del_item.dynamic_type] = [
                            item for item in model.dynamic_info[del_item.dynamic_type] if item.id != del_item.id
                        ]
                        card.content = model.model_dump(exclude_unset=True)
                        flag_modified(card, "content")
                        self.session.add(card)
                except Exception as e:
                    logger.warning(f"Failed to process deletion for {del_item.name}: {e}")
            self.session.commit()

        # 2. Then process additions and modifications
        updated_cards: Dict[str, Card] = {}
        # Preload all relevant character cards
        all_names = list(set([i.name for i in data.info_list]))
        if not all_names:
            return {"success": False, "updated_card_count": 0}

        stmt = select(Card).where(Card.project_id == project_id, Card.title.in_(all_names))
        cards = self.session.exec(stmt).all()
        card_map = {c.title: c for c in cards if c.card_type and c.card_type.name == 'Character Card'}


        # Process additions
        # (Similar to before, but ensure operating on the already-updated card object)
        for info_group in data.info_list:
            card = updated_cards.get(info_group.name) or card_map.get(info_group.name)
            if not card:
                continue

            try:
                model = CharacterCard.model_validate(card.content or {})
                if not model.dynamic_info:
                    model.dynamic_info = {}

                for cat, items in info_group.dynamic_info.items():
                    if not items:
                        continue
                    
                    if cat not in model.dynamic_info:
                        model.dynamic_info[cat] = []
                    
                    existing_items = model.dynamic_info[cat]
                    
                    # Merge (new items appended to the tail, for FIFO)
                    for new_item in items:
                        # Temporarily record placeholder or missing IDs as 0, assign positive IDs uniformly later
                        if not isinstance(new_item.id, int) or new_item.id <= 0:
                            new_item.id = 0
                        existing_items.append(new_item)
                    
                    # Uniform ID normalization: assign consecutive positive IDs to all entries with ID <=0 (do not change existing positive IDs)
                    existing_positive = [it.id for it in existing_items if isinstance(it.id, int) and it.id > 0]
                    next_id = (max(existing_positive) + 1) if existing_positive else 1
                    for it in existing_items:
                        if not isinstance(it.id, int) or it.id <= 0:
                            it.id = next_id
                            next_id += 1
                    
                    # Trim to the configured limit
                    limit = DYNAMIC_INFO_LIMITS.get(cat, queue_size)
                    if str(cat) == 'Thoughts / Goal Snapshot':
                        # Keep the latest limit items (FIFO, evict the oldest)
                        model.dynamic_info[cat] = existing_items[-limit:]
                    else:
                        # Other categories use the current strategy (change to existing_items[-limit:] if you want to keep the newest)
                        model.dynamic_info[cat] = existing_items[:limit]

                card.content = model.model_dump(exclude_unset=True)
                flag_modified(card, "content")
                updated_cards[card.title] = card
            except Exception as e:
                logger.warning(f"Failed to process addition for {info_group.name}: {e}")

        # Unified commit
        for card in updated_cards.values():
            self.session.add(card)
        
        if updated_cards:
            self.session.commit()
            for card in updated_cards.values():
                self.session.refresh(card)

        return {"success": True, "updated_card_count": len(updated_cards)} 
