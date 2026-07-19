"""Schema service layer

Handles Schema assembly, reference resolution, $defs augmentation, and other business logic.
"""

import re
from typing import Dict, Any, Set
from copy import deepcopy
from sqlmodel import Session
from app.db.models import CardType
from app.schemas.entity import DYNAMIC_INFO_TYPES
from app.schemas import entity as entity_schemas
from loguru import logger


# --- Schema reference collection ---

FIELD_TITLE_ZH_MAP: Dict[str, str] = {
    "content": "Content",
    "theme": "Theme",
    "audience": "Target Audience",
    "narrative_person": "Narrative Person",
    "story_tags": "Story Tags",
    "affection": "Affection",
    "name": "Name",
    "description": "Description",
    "special_abilities_thinking": "Special Ability Design Notes",
    "special_abilities": "Special Ability",
    "one_sentence_thinking": "One-Sentence Summary Notes",
    "one_sentence": "One-Sentence Summary",
    "overview_thinking": "Outline Expansion Notes",
    "overview": "Overview",
    "world_view_thinking": "Worldview Design Notes",
    "world_view": "Worldview",
    "title": "Title",
    "entity_type": "Entity Type",
    "life_span": "Life Span",
    "role_type": "Role Type",
    "born_scene": "Birth Scene",
    "personality": "Personality",
    "core_drive": "Core Drive",
    "character_arc": "Character Arc",
    "influence": "Influence",
    "relationship": "Relationship",
    "dynamic_info": "Dynamic Info",
    "last_appearance": "Last Appearance",
}

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _contains_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def _derive_title_from_description(description: Any) -> str | None:
    if not isinstance(description, str):
        return None
    desc = description.strip()
    if not desc or not _contains_cjk(desc):
        return None

    candidate = re.split(r"[，。；;！？:：\n（(]", desc, maxsplit=1)[0].strip()
    if not candidate:
        return None
    if len(candidate) > 16:
        candidate = candidate[:16].strip()
    return candidate or None


def localize_schema_titles(schema: Any) -> Any:
    """Localize schema field titles (does not modify field keys)."""
    if not isinstance(schema, (dict, list)):
        return schema

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                for field_name, field_schema in properties.items():
                    if isinstance(field_schema, dict):
                        current_title = str(field_schema.get("title") or "")
                        if not _contains_cjk(current_title):
                            localized = FIELD_TITLE_ZH_MAP.get(field_name) or _derive_title_from_description(
                                field_schema.get("description")
                            )
                            if localized:
                                field_schema["title"] = localized

            for defs_key in ("$defs", "definitions"):
                defs = node.get(defs_key)
                if isinstance(defs, dict):
                    for def_schema in defs.values():
                        visit(def_schema)

            items = node.get("items")
            if isinstance(items, dict):
                visit(items)

            prefix_items = node.get("prefixItems")
            if isinstance(prefix_items, list):
                for item in prefix_items:
                    visit(item)

            for union_key in ("anyOf", "oneOf", "allOf"):
                variants = node.get(union_key)
                if isinstance(variants, list):
                    for variant in variants:
                        visit(variant)

            for value in node.values():
                if isinstance(value, (dict, list)):
                    visit(value)

        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(schema)
    return schema

def collect_ref_names(node: Any) -> Set[str]:
    """Recursively collect all $ref reference names in the Schema
    
    Args:
        node: Schema node (dict/list/other)
        
    Returns:
        Set of reference names
    """
    names: Set[str] = set()
    if isinstance(node, dict):
        if '$ref' in node and isinstance(node['$ref'], str) and node['$ref'].startswith('#/$defs/'):
            names.add(node['$ref'].split('/')[-1])
        for v in node.values():
            names |= collect_ref_names(v)
    elif isinstance(node, list):
        for it in node:
            names |= collect_ref_names(it)
    return names


# --- Built-in model $defs cache ---

_BUILTIN_DEFS_CACHE: Dict[str, Any] | None = None

def get_builtin_defs() -> Dict[str, Any]:
    """Get the $defs of all built-in Pydantic models (cached)
    
    Returns:
        The merged $defs dict
    """
    global _BUILTIN_DEFS_CACHE
    if _BUILTIN_DEFS_CACHE is not None:
        return _BUILTIN_DEFS_CACHE
    
    # Import the response model registry
    from app.schemas.response_registry import RESPONSE_MODEL_MAP
    
    merged: Dict[str, Any] = {}
    for _, model_class in RESPONSE_MODEL_MAP.items():
        sch = model_class.model_json_schema(ref_template="#/$defs/{model}")
        sch = localize_schema_titles(sch)
        defs = sch.get('$defs') or {}
        merged.update(defs)
    
    _BUILTIN_DEFS_CACHE = merged
    return merged


def augment_schema_with_builtin_defs(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Inject the built-in model $defs into a custom Schema
    
    Args:
        schema: Original Schema
        
    Returns:
        The augmented Schema (deep copy)
    """
    sch = deepcopy(schema) if schema is not None else {}
    if not isinstance(sch, dict):
        return sch
    
    # Collect all references
    ref_names = collect_ref_names(sch)
    if not ref_names:
        return localize_schema_titles(sch)
    
    # Get built-in defs
    builtin_defs = get_builtin_defs()
    
    # Ensure $defs exists
    if '$defs' not in sch:
        sch['$defs'] = {}
    
    # Inject referenced built-in definitions
    for name in ref_names:
        if name in builtin_defs and name not in sch['$defs']:
            sch['$defs'][name] = builtin_defs[name]

    return localize_schema_titles(sch)


# --- CardType Schema assembly ---

def compose_schema_with_card_types(session: Session, schema: Dict[str, Any]) -> Dict[str, Any]:
    """Inject CardType Schemas into $defs
    
    Args:
        session: Database session
        schema: Original Schema
        
    Returns:
        The augmented Schema (deep copy)
    """
    sch = deepcopy(schema) if isinstance(schema, dict) else {}
    if not isinstance(sch, dict):
        return sch
    
    # Ensure $defs exists
    if '$defs' not in sch:
        sch['$defs'] = {}
    
    # Collect all references
    ref_names = collect_ref_names(sch)
    if not ref_names:
        return localize_schema_titles(sch)
    
    # Query all CardTypes and build a mapping
    all_types = session.query(CardType).all()
    by_model: Dict[str, Any] = {}
    
    for ct in all_types:
        if ct and ct.json_schema:
            localized_schema = localize_schema_titles(deepcopy(ct.json_schema))
            if ct.model_name:
                by_model[ct.model_name] = localized_schema
            by_model[ct.name] = localized_schema
    
    # Inject referenced CardType Schemas
    for name in ref_names:
        if name in by_model:
            sch['$defs'][name] = by_model[name]

    return localize_schema_titles(sch)


def compose_full_schema(session: Session, schema: Dict[str, Any]) -> Dict[str, Any]:
    """Complete Schema assembly: built-in defs + CardType defs
    
    Args:
        session: Database session
        schema: Original Schema
        
    Returns:
        The fully augmented Schema
    """
    # First inject built-in defs
    sch = augment_schema_with_builtin_defs(schema)
    # Then inject CardType defs
    sch = compose_schema_with_card_types(session, sch)
    return localize_schema_titles(sch)
