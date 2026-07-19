"""
Inspiration-assistant tool function collection (native LangChain tool implementations).
"""
import json
import uuid
from typing import Dict, Any, List, Optional
from contextvars import ContextVar

from loguru import logger
from langchain_core.tools import tool
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import select

from app.services.card_service import CardService
from app.db.models import Card, CardType
from app.services.ai.generation.instruction_validator import InstructionExecutor
from app.services.ai.card_type_schema import get_card_type_schema_payload
from app.schemas.tool_result import (
    ToolResult,
    ToolResultStatus,
    ConfirmationRequest,
    CardOperationResult,
    to_dict
)
import copy

REVIEW_RESULT_CARD_TYPE_NAME = "Content Review Card"


class AssistantDeps:
    """Dependencies for the inspiration assistant (used to pass session and project_id)."""

    def __init__(self, session, project_id: int):
        self.session = session
        self.project_id = project_id


# Use a ContextVar to inject dependencies into each request context, avoiding an
# extra wrapper layer for each tool.
_assistant_deps_var: ContextVar[AssistantDeps | None] = ContextVar(
    "assistant_deps", default=None
)


def set_assistant_deps(deps: AssistantDeps) -> None:
    """Set the assistant dependencies for the current request context; must be set before calling tools."""

    _assistant_deps_var.set(deps)


def _get_deps() -> AssistantDeps:
    """Get the assistant dependencies for the current request context."""

    deps = _assistant_deps_var.get()
    if deps is None:
        raise RuntimeError(
            "AssistantDeps is not set; please call set_assistant_deps(...) before calling assistant tools."
        )
    return deps


def _get_card_type_schema(session, card_type_name: str) -> Dict[str, Any]:
    """Get the JSON Schema for a card type"""
    result = get_card_type_schema_payload(
        session,
        card_type_name,
        allow_model_name=False,
        require_schema=True,
    )
    if not result.get("success"):
        error = result.get("error")
        if error == "not_found":
            raise ValueError(f"Card type '{card_type_name}' does not exist")
        if error == "schema_not_defined":
            raise ValueError(f"Card type '{card_type_name}' has no Schema defined")
        raise ValueError("Failed to get the card type Schema")
    return result.get("schema") or {}


def _create_empty_card(session, card_type_name: str, title: str, parent_card_id: Optional[int], project_id: int) -> Card:
    """Create an empty card"""
    card_type = session.query(CardType).filter_by(name=card_type_name).first()
    if not card_type:
        raise ValueError(f"Card type '{card_type_name}' does not exist")

    card = Card(
        card_type_id=card_type.id,
        project_id=project_id,
        title=title,
        parent_id=parent_card_id,
        content={}
    )
    session.add(card)
    session.flush()  # get card.id

    return card


def _get_card_by_id(session, card_id: int, project_id: int) -> Optional[Card]:
    """Get a card by ID"""
    card = session.get(Card, card_id)
    if card and card.project_id == project_id:
        return card
    return None


@tool
def search_cards(
    card_type: Optional[str] = None,
    title_keyword: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Search cards in the project

    Args:
        card_type: Card type name (optional)
        title_keyword: Title keyword (optional)
        limit: Maximum number of results to return

    Returns:
        success: True for success, False for failure
        error: Error message
        cards: Card list
        count: Number of cards
    """

    deps = _get_deps()

    logger.info(f" [Assistant.search_cards] card_type={card_type}, keyword={title_keyword}")

    query = deps.session.query(Card).filter(Card.project_id == deps.project_id)

    if card_type:
        query = query.join(CardType).filter(CardType.name == card_type)

    if title_keyword:
        query = query.filter(Card.title.ilike(f'%{title_keyword}%'))

    cards = query.limit(limit).all()

    result = {
        "success": True,
        "cards": [
            {
                "id": c.id,
                "title": c.title,
                "type": c.card_type.name if c.card_type else "Unknown"
            }
            for c in cards
        ],
        "count": len(cards)
    }

    logger.info(f"✅ [Assistant.search_cards] found {len(cards)} cards")
    return result

@tool
def create_card(
    card_type: str,
    title: str,
    instructions: List[Dict[str, Any]],
    parent_card_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a **new** card and fill in content.

    ⚠️ **Core rules**:
    - ✅ **Create a new card**: use only when the user explicitly asks to create one.
    - ❌ **Modify/refine**: if you need to modify an existing card or supplement content, you must use `update_card`.
    - ✅ **Explicit assignment**: even if a field has a default value, you must explicitly generate an instruction to assign it, to confirm the AI's intent.

    **Strategy suggestion (step-by-step creation)**:
    - **Complex cards**: recommended to first create a framework by filling only core fields (such as name), get the ID, and then use `update_card` to fill in the remaining content in batches. This reduces the error rate and allows midway adjustments.
    - **Simple cards**: can be created in one go.

    Args:
        card_type: Card type (e.g. Character Card, Worldbuilding Setting)
        title: Title
        instructions: Instruction array, e.g. `[{"op":"set", "path":"/name", "value":"Zhang San"}]`
        parent_card_id: (optional) parent card ID

    Returns:
        Contains success, card_id, missing_fields, etc.
        If success=False (content incomplete), generate supplementary instructions based on missing_fields and call update_card.
    """
    deps = _get_deps()

    logger.info(f"📝 [Assistant.create_card] type={card_type}, title={title}, instructions={len(instructions)}")

    try:
        # 1. Get the Schema
        schema = _get_card_type_schema(deps.session, card_type)

        # 2. Create an empty card
        card = _create_empty_card(
            session=deps.session,
            card_type_name=card_type,
            title=title,
            parent_card_id=parent_card_id,
            project_id=deps.project_id
        )

        logger.info(f"  Empty card created successfully, card_id={card.id}")

        # 3. Create the instruction executor
        executor = InstructionExecutor(schema=schema, initial_data={})

        # 4. Execute the instruction array
        result = executor.execute_batch(instructions)

        # 5. Save the data and mark it as AI-modified
        card.content = result["data"]
        flag_modified(card, "content")
        card.ai_modified = True
        card.needs_confirmation = True
        card.last_modified_by = "ai"
        deps.session.commit()

        logger.info(f"  Instruction execution complete: applied={result['applied']}, failed={result['failed']}")
        logger.info(f"  Marked as AI-modified, needs user confirmation")

        # 6. Build the return result
        if result["success"]:
            logger.info(f"✅ [Assistant.create_card] created successfully and content is complete")
            return {
                "success": True,
                "card_id": card.id,
                "card_title": title,
                "card_type": card_type,
                "message": f"✅ Card \"{title}\" created successfully, filled in {result['applied']} fields. Please review the content in the frontend and click save to trigger the workflow.",
                "applied": result['applied'],
                "needs_confirmation": True
            }
        else:
            # Data incomplete
            missing_fields_str = ", ".join(result["missing_fields"])
            logger.warning(f"⚠️ [Assistant.create_card] card created but content is incomplete: {missing_fields_str}")
            return {
                "success": False,
                "card_id": card.id,
                "card_title": title,
                "card_type": card_type,
                "message": f"⚠️ The card was created but the content is incomplete; fields need to be supplemented. After supplementing, please click save in the frontend to trigger the workflow.",
                "error": f"Missing required fields: {missing_fields_str}",
                "missing_fields": result["missing_fields"],
                "current_data": result["data"],
                "applied": result["applied"],
                "failed": result["failed"],
                "failed_instructions": result.get("errors", []),
                "needs_confirmation": True
            }

    except Exception as e:
        logger.error(f"❌ [Assistant.create_card] failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Creation failed: {str(e)}"
        }


def _update_card_impl(
    card_id: int,
    instructions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Internal implementation for updating a card (core logic)

    This function contains the actual update logic and can be reused by multiple tool functions.
    Do not expose it directly to the LLM; call it through @tool-decorated functions.
    """
    deps = _get_deps()

    logger.info(f"📝 [_update_card_impl] card_id={card_id}, instructions={len(instructions)}")

    try:
        # 1. Get the card
        card = _get_card_by_id(deps.session, card_id, deps.project_id)
        if not card:
            return {
                "success": False,
                "error": f"Card ID={card_id} does not exist or does not belong to the current project"
            }

        # 2. Get the Schema
        schema = _get_card_type_schema(deps.session, card.card_type.name)

        # 3. Create the executor (using existing data)
        initial_data = copy.deepcopy(card.content) if isinstance(card.content, dict) else {}
        executor = InstructionExecutor(
            schema=schema,
            initial_data=initial_data
        )

        # 4. Execute the instructions
        result = executor.execute_batch(instructions)

        # 5. Save and mark as AI-modified
        card.content = result["data"]
        flag_modified(card, "content")
        card.ai_modified = True
        card.needs_confirmation = True
        card.last_modified_by = "ai"
        deps.session.commit()

        logger.info(f"  Instruction execution complete: applied={result['applied']}, failed={result['failed']}")
        logger.info(f"  Marked as AI-modified, needs user confirmation")

        # 6. Return the result
        if result["success"]:
            logger.info(f"✅ [_update_card_impl] updated successfully and content is complete")
            return {
                "success": True,
                "card_id": card_id,
                "card_title": card.title,
                "message": f"✅ Card \"{card.title}\" updated successfully, modified {result['applied']} fields. Please review the content in the frontend and click save to trigger the workflow.",
                "current_data": result["data"],
                "applied": result["applied"],
                "needs_confirmation": True
            }
        else:
            missing_fields_str = ", ".join(result["missing_fields"])
            logger.warning(f"⚠️ [_update_card_impl] card updated but still incomplete: {missing_fields_str}")
            return {
                "success": True,
                "card_id": card_id,
                "card_title": card.title,
                "message": f"⚠️ The card was updated but is still incomplete; fields need to be supplemented. After supplementing, please click save in the frontend to trigger the workflow.",
                "is_complete": False,
                "completion_status": "incomplete",
                "warning": f"Missing required fields: {missing_fields_str}",
                "missing_fields": result["missing_fields"],
                "current_data": result["data"],
                "applied": result["applied"],
                "failed": result["failed"],
                "needs_confirmation": True
            }

    except Exception as e:
        logger.error(f"❌ [_update_card_impl] failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Update failed: {str(e)}"
        }


@tool
def update_card(
    card_id: int,
    instructions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Update an **existing** card's content (execute an instruction array)

    ⚠️ **Important: when to use this tool?**

    - ✅ **Modify an existing card**: the user selected/referenced a card and asked to modify or refine it
    - ✅ **Supplement content**: the user says things like "refine this card", "supplement content", "add fields"
    - ✅ **Step-by-step creation**: after creating a base framework with create_card, gradually fill in content
    - ❌ **Create a new card**: if creating a brand-new card, you should use create_card

    **Decision basis:**
    1. If there is a card reference in the conversation context (e.g. @card name), use this tool
    2. If the user says "modify", "refine", "supplement", "update", use this tool
    3. If create_card returned incomplete and you continue to fill in content, use this tool

    Used to supplement or modify the content of an existing card. Supports batch-modifying multiple fields.

    Args:
        card_id: Card ID
        instructions: Instruction array, each instruction contains:
            - op: operation type ("set" to set a field, "append" to append to an array)
            - path: field path (JSON Pointer format, e.g. "/name")
            - value: the value to set

    Returns:
        Dict containing:
        - success (bool): whether it succeeded
        - message (str): result message
        - card_id (int): card ID
        - card_title (str): card title
        - current_data (dict): the complete updated data
        - applied (int): number of successfully executed instructions
        - missing_fields (list, optional): list of still-missing required field paths
        - failed (int, optional): number of failed instructions

    Examples:
        # Supplement missing fields
        update_card(
            card_id=123,
            instructions=[
                {"op":"set", "path":"/personality", "value":"righteous and brave"},
                {"op":"set", "path":"/background", "value":"Wudang disciple"},
                {"op":"append", "path":"/skills", "value":"Eighteen Dragon-Subduing Palms"}
            ]
        )
    """
    return _update_card_impl(card_id, instructions)


@tool
def modify_card_field(
    card_id: int,
    field_path: str,
    new_value: Any,
) -> Dict[str, Any]:
    """
    Quickly modify a single field (convenience tool)

    This is a simplified version of update_card, used to quickly modify a single field.
    If you need to modify multiple fields at the same time, please use the update_card tool.

    Args:
        card_id: Card ID
        field_path: Field path, no leading slash needed (e.g. "name" or "personality")
        new_value: New value (string, number, boolean, etc.)

    Returns:
        Dict containing:
        - success (bool): whether it succeeded
        - message (str): result message
        - card_id (int): card ID
        - card_title (str): card title

    Examples:
        # Modify a character name
        modify_card_field(card_id=123, field_path="name", new_value="Li Si")

        # Modify a character's personality
        modify_card_field(card_id=123, field_path="personality", new_value="righteous and brave")
    """
    # Convert to instruction format (add a leading slash)
    path = "/" + field_path if not field_path.startswith("/") else field_path
    instruction = {"op": "set", "path": path, "value": new_value}

    # Call the internal implementation (not the @tool-decorated function)
    return _update_card_impl(card_id=card_id, instructions=[instruction])


@tool
def get_card_type_schema(
    card_type_name: str,
) -> Dict[str, Any]:
    """
    Get the JSON Schema definition of a specified card type

    Usage: call when you need to create a card but are unsure of its structure

    Args:
        card_type_name: Card type name

    Returns:
        success: True for success, False for failure
        error: Error message
        card_type: Card type name
        schema: The JSON Schema definition of the card type
        description: Description of the card type
    """

    deps = _get_deps()

    logger.info(f" [Assistant.get_card_type_schema] card_type={card_type_name}")

    result = get_card_type_schema_payload(
        deps.session,
        card_type_name,
        allow_model_name=False,
        require_schema=False,
    )

    if not result.get("success"):
        logger.warning(
            f"⚠️ [Assistant.get_card_type_schema] card type '{card_type_name}' does not exist"
        )
        return {
            "success": False,
            "error": f"Card type '{card_type_name}' does not exist"
        }

    output = {
        "success": True,
        "card_type": result.get("card_type") or card_type_name,
        "schema": result.get("schema") or {},
        "description": f"Complete structure definition of card type '{card_type_name}'"
    }

    logger.info(f"✅ [Assistant.get_card_type_schema] returned Schema: {output}")
    return output

@tool
def get_card_content(
    card_id: int,
) -> Dict[str, Any]:
    """
    Get the detailed content of a specified card

    Usage: call when you need to view the complete data of a card

    Args:
        card_id: Card ID

    Returns:
        success: True for success, False for failure
        error: Error message (on failure)
        card_id: Card ID
        title: Card title
        card_type: Card type
        parent_id: Parent card ID (None means a root-level card)
        parent_title: Parent card title (if there is a parent card)
        parent_type: Parent card type (if there is a parent card)
        content: Card content
        created_at: Card creation time
    """

    deps = _get_deps()

    logger.info(f" [Assistant.get_card_content] card_id={card_id}")

    card = deps.session.query(Card).filter(Card.id == card_id).first()

    if not card:
        logger.warning(f"⚠️ [Assistant.get_card_content] card #{card_id} does not exist")
        return {
            "success": False,
            "error": f"Card #{card_id} does not exist"
        }

    result = {
        "success": True,
        "card_id": card.id,
        "title": card.title,
        "card_type": card.card_type.name if card.card_type else "Unknown",
        "parent_id": card.parent_id,  # parent card ID, to understand the hierarchy
        "content": card.content or {},
        "created_at": str(card.created_at) if card.created_at else None
    }

    # If there is a parent card, add parent card info
    if card.parent_id and card.parent:
        result["parent_title"] = card.parent.title
        result["parent_type"] = card.parent.card_type.name if card.parent.card_type else "Unknown"

    logger.info(
        f"✅ [Assistant.get_card_content] returned card content (parent_id={card.parent_id})"
    )
    return result


# NF_ASSISTANT_BATCH_PATCH_BEGIN
def _nf_assistant_get_text_field_for_patch(card, field_path):
    raw = card.content or {}

    if isinstance(raw, str):
        if field_path in ("", "content", "/content"):
            return raw
        raise ValueError("card.content is a string, field_path must be content")

    if not isinstance(raw, dict):
        raise ValueError("card.content is not a readable text object")

    normalized = (field_path or "content").strip()
    candidates = []
    if normalized.startswith("/"):
        candidates.append([p for p in normalized.strip("/").split("/") if p])
    else:
        candidates.append([p for p in normalized.split(".") if p])

    if normalized == "content":
        candidates.append(["content", "content"])

    last_error = None
    for parts in candidates:
        cur = raw
        try:
            for part in parts:
                if not isinstance(cur, dict) or part not in cur:
                    raise KeyError(part)
                cur = cur[part]
            if isinstance(cur, str):
                return cur
            last_error = "field is not text: " + str(field_path)
        except Exception as exc:
            last_error = str(exc)

    raise ValueError(last_error or ("field path not found: " + str(field_path)))


def _nf_assistant_line_span(text, start_line, end_line):
    lines = text.split("\n")
    if start_line < 1 or end_line < start_line or end_line > len(lines):
        raise ValueError("invalid line range: %s-%s, total lines: %s" % (start_line, end_line, len(lines)))
    return "\n".join(lines[start_line - 1:end_line])


def _nf_assistant_context(text, old_text, radius=120):
    idx = text.find(old_text)
    if idx < 0:
        return "", ""
    return text[max(0, idx - radius):idx], text[idx + len(old_text):idx + len(old_text) + radius]


@tool
def propose_card_text_patches(card_id: int, field_path: str, patches: list) -> dict:
    """
    Batch-submit body-text edit suggestions without writing to the database directly;
    the frontend editor previews, accepts, or rejects them one by one.

    Usage:
    - When the user asks for multiple edit suggestions (polishing, error correction, rewriting, etc.) for the body text, use this tool.

    Args:
        card_id: The target card ID
        field_path: Field path (e.g. "content" means the chapter body)
        patches: List of edit suggestions (processes at most 30), each a dict containing:
            - old_text (required): the exact excerpt of the current body text to be replaced; should be as precise as possible
            - new_text (required): the new text to replace it with
            - start_line/end_line (optional): 1-based line-number range, only used as an auxiliary locating hint
            - context_before/context_after (optional): context excerpts before/after the original text, used by the frontend to re-locate
            - instruction/reason (optional): the reason or explanation for this edit

    Important constraints:
        - Each patch must contain both old_text and new_text.
        - old_text should be an exact excerpt of the current body text, to help the frontend locate it.

    Returns:
        success: True means suggestions were generated, False means failure
        kind: "assistant_text_patch_batch" (frontend recognition marker)
        count: number of valid suggestions
        patches: the normalized suggestion list
        failed_count: number of suggestions that failed validation
        failed_patches: failed entries and their reasons
        preview_only: True (means preview only, does not write to the database)
        needs_user_accept: True (requires per-item user confirmation)
    """
    deps = _get_deps()
    logger.info("[Assistant.propose_card_text_patches] card_id=%s path=%s count=%s", card_id, field_path, len(patches or []))

    try:
        card = deps.session.get(Card, card_id)
        if not card or card.project_id != deps.project_id:
            return {"success": False, "error": "card not found or not in current project: %s" % card_id}

        if not patches:
            return {"success": False, "error": "patches is empty"}

        full_text = _nf_assistant_get_text_field_for_patch(card, field_path or "content")
        normalized = []
        failed = []

        for i, item in enumerate(patches[:30], start=1):
            item = item or {}
            new_text = str(item.get("new_text") or item.get("revised_text") or item.get("replacement_text") or "")
            if not new_text:
                failed.append({"index": i, "error": "missing new_text"})
                continue

            start_line = item.get("start_line")
            end_line = item.get("end_line")
            old_text = item.get("old_text") or item.get("original_text")

            if (not old_text) and start_line and end_line:
                try:
                    old_text = _nf_assistant_line_span(full_text, int(start_line), int(end_line))
                except Exception as exc:
                    failed.append({"index": i, "error": "invalid line range: %s" % exc})
                    continue

            if not old_text:
                failed.append({"index": i, "error": "missing old_text and start_line/end_line"})
                continue

            old_text = str(old_text)
            context_before = str(item.get("context_before") or "")
            context_after = str(item.get("context_after") or "")
            if not context_before and not context_after:
                context_before, context_after = _nf_assistant_context(full_text, old_text)

            normalized.append({
                "id": int(item.get("id") or i),
                "index": i,
                "card_id": card.id,
                "field_path": field_path or "content",
                "start_line": int(start_line) if start_line else None,
                "end_line": int(end_line) if end_line else None,
                "old_text": old_text,
                "original_text": old_text,
                "new_text": new_text,
                "context_before": context_before,
                "context_after": context_after,
                "instruction": item.get("instruction") or item.get("reason") or "",
                "status": "pending",
            })

        if not normalized:
            return {
                "success": False,
                "kind": "assistant_text_patch_batch",
                "status": "text_patch_batch_failed",
                "error": "no valid patch proposals",
                "failed_count": len(failed),
                "failed_patches": failed,
            }

        return {
            "success": True,
            "kind": "assistant_text_patch_batch",
            "status": "text_patch_batch_partial" if failed else "text_patch_batch_proposed",
            "message": "Created %s text patch proposals. Review them in the chapter editor." % len(normalized),
            "card_id": card.id,
            "card_title": card.title,
            "field_path": field_path or "content",
            "count": len(normalized),
            "patches": normalized,
            "failed_count": len(failed),
            "failed_patches": failed,
            "preview_only": True,
            "needs_user_accept": True,
        }

    except Exception as e:
        logger.error("[Assistant.propose_card_text_patches] failed: %s", e, exc_info=True)
        return {"success": False, "error": "failed to create patch proposals: " + str(e)}
# NF_ASSISTANT_BATCH_PATCH_END

@tool
def replace_field_text(
    card_id: int,
    field_path: str,
    old_value: str,
    new_value: str,
) -> Dict[str, Any]:
    """
    Replace a specified text fragment in a card field (legacy compatibility tool, lower priority than line-based replacement).

    Usage:
    - Use it as a fallback only when you cannot get stable line numbers, have no `chapter_excerpt` reference, and no `snapshot_hash`.
    - If the context already clearly gives "lines X-Y", a `chapter_excerpt` reference, or a `snapshot_hash`, do not call this tool; use `replace_card_text_by_lines` instead.
    - Suitable for fuzzy-fragment replacement in outline descriptions, short paragraphs, or non-body long text.

    Examples:
        1. Exact match (short text, and no usable line numbers):
        replace_field_text(card_id=42, field_path="content",
                            old_value="Lin Feng hesitated for a moment",
                            new_value="Lin Feng did not hesitate at all")

        2. Fuzzy match (long-text fallback):
        replace_field_text(card_id=42, field_path="content",
                            old_value="The youth was pale-faced, veins bulging on his forehead...but now he had become a cripple.",
                            new_value="The new complete paragraph content...")

    Args:
        card_id: The target card ID
        field_path: Field path (e.g. "content" for chapter body, "overview" for overview)
        old_value: The original text fragment to be replaced, supporting two modes:
            1. Exact match: provide the complete original text (for short text, within 50 characters)
            2. Fuzzy match: provide the first 10 chars + "..." + the last 10 chars (for long text, over 50 characters)
        new_value: The new text content

    Important constraints:
        - If the line-number range is known, please do not use this tool.
        - If the reference source is a body-text selection, prefer `replace_card_text_by_lines`.

    Returns:
        success: True for success, False for failure
        error: Error message
        card_title: Card title
        replaced_count: Number of replacements
        message: User-friendly message
    """

    deps = _get_deps()

    logger.info(f" [Assistant.replace_field_text] card_id={card_id}, path={field_path}")
    logger.info(f"  Length of text to replace: {len(old_value)} chars")
    logger.info(f"  Length of new text: {len(new_value)} chars")

    try:
        # Use CardService logic directly
        service = CardService(deps.session)
        result = service.replace_field_text(
            card_id=card_id,
            field_path=field_path,
            old_text=old_value,
            new_text=new_value,
            fuzzy_match=True
        )

        # If the Service execution failed
        if not result.get("success"):
            raw_error = str(result.get("error") or "Replacement failed")
            raw_hint = str(result.get("hint") or "").strip()

            suggestion = ""
            if raw_error in ("Specified original text fragment not found", "Start text not found", "End text not found", "Fuzzy match format error"):
                suggestion = "It is recommended to first call get_card_content to get the latest content, then copy an accurate excerpt and retry; for long text, use the \"start...end\" format."
            elif "is not a text type" in raw_error:
                suggestion = "The target field is not a string text; it is recommended to use modify_card_field to update it in a structured way instead."
            elif "Field path" in raw_error:
                suggestion = "The field path may be incorrect; it is recommended to first view the card structure and confirm field_path."

            if suggestion:
                result["message"] = f"⚠️ Text replacement failed: {raw_error}. {suggestion}"
            else:
                result["message"] = f"⚠️ Text replacement failed: {raw_error}."

            if raw_hint:
                result["message"] = f"{result['message']} (locating hint: {raw_hint})"

            logger.warning(
                f"⚠️ [Assistant.replace_field_text] replacement failed: {result.get('error')}"
            )
            return result

        # Service already commits, but tool flow often expects us to handle it or just be sure.
        # CardService.replace_field_text does commit.

        logger.info(f"✅ [Assistant.replace_field_text] replacement succeeded")

        # Add a user-friendly message
        result["message"] = (
            f"✅ Replaced {result.get('replaced_count')} occurrence(s) of content in the "
            f"{field_path} field of \"{result.get('card_title')}\""
        )

        return result

    except Exception as e:
        logger.error(f"❌ [Assistant.replace_field_text] replacement failed: {e}")
        return {"success": False, "error": f"Replacement failed: {str(e)}"}


@tool
def replace_card_text_by_lines(
    card_id: int,
    field_path: str,
    start_line: int,
    end_line: int,
    new_text: str,
    snapshot_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Replace a card text fragment by line numbers (positional replacement; this should be the preferred
    tool when editing body-text fragments).

    This is the preferred tool for "chapter body / Markdown long-text fragment revision", suitable for:
    - The user explicitly specifies "lines 93-102"
    - A `chapter_excerpt` reference is already in the context
    - A `snapshot_hash` has been obtained
    - You want to avoid the fuzzy-match collateral damage of `replace_field_text`

    Call suggestions:
    - For chapter body, `field_path` is usually `content`
    - If you have a fragment reference, prefer passing `snapshot_hash`; usually you do not need to also pass the old fragment text
    - When you can locate specific line numbers, do not fall back to `replace_field_text`

    Examples:
        1. Replace directly based on a body-text fragment reference:
           replace_card_text_by_lines(
               card_id=666,
               field_path="content",
               start_line=93,
               end_line=102,
               new_text="The new body-text fragment...",
               snapshot_hash="abc123"
           )

        2. When you know the line range to modify but have no snapshot:
           replace_card_text_by_lines(
               card_id=666,
               field_path="content",
               start_line=40,
               end_line=44,
               new_text="The revised content"
           )
    """
    deps = _get_deps()
    logger.info(
        f"🧩 [Assistant.replace_card_text_by_lines] card_id={card_id}, "
        f"path={field_path}, lines={start_line}-{end_line}"
    )

    try:
        service = CardService(deps.session)
        result = service.replace_field_text_by_lines(
            card_id=card_id,
            field_path=field_path,
            start_line=start_line,
            end_line=end_line,
            new_text=new_text,
            snapshot_hash=snapshot_hash,
        )
        if not result.get("success"):
            raw_error = str(result.get("error") or "Line-based replacement failed")
            if "Snapshot verification failed" in raw_error or "Original fragment verification failed" in raw_error:
                result["message"] = (
                    f"⚠️ {raw_error}. It is recommended to re-reference the latest body fragment first, then replace by lines."
                )
            else:
                result["message"] = f"⚠️ Line-based replacement failed: {raw_error}"
            return result

        result["message"] = (
            f"✅ Replaced lines {start_line}-{end_line}, "
            f"replacing {result.get('replaced_line_count')} line(s) with {result.get('new_line_count')} line(s), "
            f"target field: {field_path}"
        )
        return result
    except Exception as e:
        logger.error(f"❌ [Assistant.replace_card_text_by_lines] failed: {e}")
        return {"success": False, "error": f"Line-based replacement failed: {str(e)}"}


@tool
def list_reviews_for_target(
    target_id: int,
    review_type: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Get the list of review-result cards bound to a specified target card (used to inject review_result references).
    """
    deps = _get_deps()
    logger.info(
        f"📚 [Assistant.list_reviews_for_target] target_id={target_id}, review_type={review_type}, limit={limit}"
    )
    try:
        review_card_type = deps.session.query(CardType).filter(CardType.name == REVIEW_RESULT_CARD_TYPE_NAME).first()
        if not review_card_type:
            return {"success": False, "error": f"Missing card type: {REVIEW_RESULT_CARD_TYPE_NAME}"}

        rows = (
            deps.session.query(Card)
            .filter(Card.project_id == deps.project_id, Card.card_type_id == review_card_type.id)
            .order_by(Card.created_at.desc())
            .all()
        )
        filtered = []
        for row in rows:
            content = dict(row.content or {})
            if int(content.get("review_target_card_id") or -1) != target_id:
                continue
            if review_type and review_type != "all" and str(content.get("review_type") or "") != review_type:
                continue
            filtered.append(row)
        filtered = filtered[: max(1, min(limit, 100))]
        return {
            "success": True,
            "count": len(filtered),
            "reviews": [
                {
                    "review_card_id": row.id,
                    "project_id": row.project_id,
                    "target_id": int((row.content or {}).get("review_target_card_id") or 0),
                    "target_title": (row.content or {}).get("review_target_title"),
                    "review_type": (row.content or {}).get("review_type"),
                    "review_profile": (row.content or {}).get("review_profile"),
                    "target_field": (row.content or {}).get("review_target_field"),
                    "quality_gate": (row.content or {}).get("quality_gate"),
                    "prompt_name": (row.content or {}).get("prompt_name"),
                    "created_at": (row.content or {}).get("reviewed_at") or str(row.created_at),
                    "title": row.title,
                }
                for row in filtered
            ],
        }
    except Exception as e:
        logger.error(f"❌ [Assistant.list_reviews_for_target] failed: {e}")
        return {"success": False, "error": f"Failed to get review records: {str(e)}"}


@tool
def get_review_record(review_id: int) -> Dict[str, Any]:
    """
    Get the details of a single review-result card (including the complete review Markdown).
    """
    deps = _get_deps()
    logger.info(f"📄 [Assistant.get_review_record] review_card_id={review_id}")
    try:
        row = deps.session.get(Card, review_id)
        review_card_type = deps.session.query(CardType).filter(CardType.name == REVIEW_RESULT_CARD_TYPE_NAME).first()
        if not row or row.project_id != deps.project_id or not review_card_type or row.card_type_id != review_card_type.id:
            return {"success": False, "error": f"Review-result card #{review_id} does not exist"}
        content = dict(row.content or {})
        return {
            "success": True,
            "review": {
                "review_card_id": row.id,
                "project_id": row.project_id,
                "target_id": int(content.get("review_target_card_id") or 0),
                "target_title": content.get("review_target_title"),
                "review_type": content.get("review_type"),
                "review_profile": content.get("review_profile"),
                "target_field": content.get("review_target_field"),
                "quality_gate": content.get("quality_gate"),
                "prompt_name": content.get("prompt_name"),
                "result_text": content.get("review_markdown"),
                "content_snapshot": content.get("target_snapshot"),
                "meta": content.get("meta"),
                "created_at": content.get("reviewed_at") or str(row.created_at),
                "title": row.title,
            },
        }
    except Exception as e:
        logger.error(f"❌ [Assistant.get_review_record] failed: {e}")
        return {"success": False, "error": f"Failed to read review record: {str(e)}"}


@tool
def delete_card(
    card_id: int,
    skip_confirmation: bool = False
) -> Dict[str, Any]:
    """
    Delete a card (dangerous operation)

    ⚠️ **Confirmation rules:**
    - **Explicit user instruction** (e.g. "delete the Character Card Zhang San"): you may execute directly, set skip_confirmation=True
    - **Ambiguous instruction or your own judgment**: you must first get user confirmation, set skip_confirmation=False

    **Decision criteria:**
    - The user's message explicitly specifies the card to delete (via title, ID, or other unique identifier) -> can execute directly
    - The user says ambiguous things like "delete that card", "delete the test one" -> needs confirmation
    - You yourself judge that a card needs deletion (the user did not say so explicitly) -> needs confirmation

    **Confirmation flow:**
    1. First call with skip_confirmation=False to get a confirmation request
    2. The tool returns status="confirmation_required" and card info
    3. Explain to the user the details of the card to be deleted, and ask "Do you confirm deletion?"
    4. After the user explicitly replies "confirm" or "confirm delete", call again with skip_confirmation=True

    Args:
        card_id: The ID of the card to delete
        skip_confirmation: Whether to skip confirmation (default False, confirmation required)

    Returns:
        Dict containing:
        - If confirmation needed: {"status": "confirmation_required", "message": "...", "data": {...}}
        - If confirmed: {"success": true, "message": "Card deleted", ...}

    Examples:
        # Example 1: explicit user instruction "delete the Character Card Zhang San"
        delete_card(card_id=123, skip_confirmation=True)  # execute directly

        # Example 2: ambiguous user instruction "delete the test card" or you judge deletion is needed
        # Step 1: get confirmation
        result = delete_card(card_id=123, skip_confirmation=False)
        # You: "I need to delete the card \"Test\". This action is irreversible. Do you confirm?"
        # User: "confirm delete"
        # Step 2: execute deletion
        result = delete_card(card_id=123, skip_confirmation=True)
    """
    deps = _get_deps()

    logger.info(f"🗑️ [Assistant.delete_card] card_id={card_id}, skip_confirmation={skip_confirmation}")

    try:
        # Get the card info
        card = _get_card_by_id(deps.session, card_id, deps.project_id)
        if not card:
            result = CardOperationResult(
                success=False,
                status=ToolResultStatus.FAILED,
                message=f"Card ID={card_id} does not exist or does not belong to the current project",
                error=f"Card ID={card_id} does not exist"
            )
            return to_dict(result)

        # Check whether there are child cards
        child_count = deps.session.query(Card).filter(
            Card.parent_id == card_id
        ).count()

        # If confirmation is needed, return a confirmation request
        if not skip_confirmation:
            warning = None
            if child_count > 0:
                warning = f"This card has {child_count} child card(s); the child cards will also be deleted"

            result = ConfirmationRequest(
                confirmation_id=str(uuid.uuid4()),
                action="delete_card",
                action_params={"card_id": card_id},
                message=f"❓ Confirm deletion of card \"{card.title}\"? Please have the user explicitly say \"confirm delete\" or \"cancel\"",
                warning=warning,
                data={
                    "card_id": card_id,
                    "card_title": card.title,
                    "card_type": card.card_type.name,
                    "child_count": child_count
                }
            )
            logger.info(f"⚠️ [Assistant.delete_card] waiting for user confirmation")
            return to_dict(result)

        # User confirmed, execute deletion
        logger.info(f"✅ [Assistant.delete_card] user confirmed, starting deletion")

        # Delete child cards (if any)
        if child_count > 0:
            deps.session.query(Card).filter(Card.parent_id == card_id).delete()
            logger.info(f"  Deleted {child_count} child card(s)")

        # Delete the card itself
        card_title = card.title
        deps.session.delete(card)
        deps.session.commit()

        result = CardOperationResult(
            success=True,
            status=ToolResultStatus.SUCCESS,
            message=f"✅ Card \"{card_title}\" deleted successfully" + (f" (including {child_count} child card(s))" if child_count > 0 else ""),
            card_id=card_id,
            card_title=card_title,
            data={"deleted_children": child_count}
        )
        logger.info(f"✅ [Assistant.delete_card] deletion succeeded")
        return to_dict(result)

    except Exception as e:
        logger.error(f"❌ [Assistant.delete_card] failed: {e}", exc_info=True)
        result = CardOperationResult(
            success=False,
            status=ToolResultStatus.FAILED,
            message=f"Deletion failed: {str(e)}",
            error=str(e)
        )
        return to_dict(result)


@tool
def move_card(
    card_id: int,
    new_parent_id: Optional[int] = None,
    skip_confirmation: bool = False
) -> Dict[str, Any]:
    """
    Move a card under a new parent card (dangerous operation)

    ⚠️ **Confirmation rules:**
    - **Explicit user instruction** (e.g. "move the Character Card Qingfeng under the Core Blueprint"): you may execute directly, set skip_confirmation=True
    - **Ambiguous instruction or your own judgment**: you must first get user confirmation, set skip_confirmation=False

    **Decision criteria:**
    - The user explicitly says which card to move where -> can execute directly
    - The user says ambiguous things like "move that card", "put it elsewhere" -> needs confirmation
    - You yourself judge that a card needs moving (the user did not say so explicitly) -> needs confirmation

    **Confirmation flow:**
    1. First call with skip_confirmation=False to get a confirmation request
    2. The tool returns status="confirmation_required" and move details
    3. Explain the move to the user: "Move card \"X\" from Y to Z, do you confirm?"
    4. After the user explicitly replies "confirm" or "confirm move", call again with skip_confirmation=True

    Args:
        card_id: The ID of the card to move
        new_parent_id: New parent card ID (None means move to root level)
        skip_confirmation: Whether to skip confirmation (default False, confirmation required)

    Returns:
        Dict containing:
        - If confirmation needed: {"status": "confirmation_required", "message": "...", "data": {...}}
        - If confirmed: {"success": true, "message": "Card moved", ...}

    Examples:
        # Example 1: explicit user instruction "move Qingfeng under the Core Blueprint"
        move_card(card_id=123, new_parent_id=456, skip_confirmation=True)  # execute directly

        # Example 2: ambiguous user instruction or your own judgment
        # Step 1: get confirmation
        result = move_card(card_id=123, new_parent_id=456, skip_confirmation=False)
        # You: "Move card \"Qingfeng\" from root level to under \"Core Blueprint\", do you confirm?"
        # User: "confirm move"
        # Step 2: execute the move
        result = move_card(card_id=123, new_parent_id=456, skip_confirmation=True)
    """
    deps = _get_deps()

    logger.info(f"📦 [Assistant.move_card] card_id={card_id}, new_parent={new_parent_id}, skip_confirmation={skip_confirmation}")

    try:
        # 1. Get the card to move
        card = _get_card_by_id(deps.session, card_id, deps.project_id)
        if not card:
            result = CardOperationResult(
                success=False,
                status=ToolResultStatus.FAILED,
                message=f"Card ID={card_id} does not exist or does not belong to the current project",
                error=f"Card ID={card_id} does not exist"
            )
            return to_dict(result)

        # 2. Validate the new parent card
        new_parent = None
        if new_parent_id is not None:
            new_parent = _get_card_by_id(deps.session, new_parent_id, deps.project_id)
            if not new_parent:
                result = CardOperationResult(
                    success=False,
                    status=ToolResultStatus.FAILED,
                    message=f"Target parent card ID={new_parent_id} does not exist or does not belong to the current project",
                    error=f"Target parent card does not exist"
                )
                return to_dict(result)

            # Prevent circular references: cannot move a card under itself or its own descendant
            if new_parent_id == card_id:
                result = CardOperationResult(
                    success=False,
                    status=ToolResultStatus.FAILED,
                    message="Cannot move a card under itself",
                    error="Circular reference error"
                )
                return to_dict(result)

            # TODO: check whether it is a descendant card (requires recursive checking)

        # 3. Get the current parent card info
        old_parent = None
        old_parent_title = "root level"
        if card.parent_id:
            old_parent = deps.session.get(Card, card.parent_id)
            if old_parent:
                old_parent_title = f"\"{old_parent.title}\""

        new_parent_title = "root level" if not new_parent else f"\"{new_parent.title}\""

        # 4. If confirmation is needed, return a confirmation request
        if not skip_confirmation:
            result = ConfirmationRequest(
                confirmation_id=str(uuid.uuid4()),
                action="move_card",
                action_params={
                    "card_id": card_id,
                    "new_parent_id": new_parent_id
                },
                message=f"❓ Confirm moving card \"{card.title}\" from {old_parent_title} to {new_parent_title}? Please have the user explicitly say \"confirm move\" or \"cancel\"",
                data={
                    "card_id": card_id,
                    "card_title": card.title,
                    "from_parent": old_parent_title,
                    "to_parent": new_parent_title
                }
            )
            logger.info(f"⚠️ [Assistant.move_card] waiting for user confirmation")
            return to_dict(result)

        # 5. User confirmed, execute the move
        logger.info(f"✅ [Assistant.move_card] user confirmed, starting move")

        card.parent_id = new_parent_id
        deps.session.commit()

        result = CardOperationResult(
            success=True,
            status=ToolResultStatus.SUCCESS,
            message=f"✅ Card \"{card.title}\" moved from {old_parent_title} to {new_parent_title}",
            card_id=card_id,
            card_title=card.title,
            data={
                "from_parent": old_parent_title,
                "to_parent": new_parent_title
            }
        )
        logger.info(f"✅ [Assistant.move_card] move succeeded")
        return to_dict(result)

    except Exception as e:
        logger.error(f"❌ [Assistant.move_card] failed: {e}", exc_info=True)
        result = CardOperationResult(
            success=False,
            status=ToolResultStatus.FAILED,
            message=f"Move failed: {str(e)}",
            error=str(e)
        )
        return to_dict(result)


# Export all LangChain tools (decorated via @tool)
ASSISTANT_TOOLS = [
    search_cards,
    create_card,
    update_card,
    modify_card_field,
    delete_card,
    move_card,
    replace_card_text_by_lines, propose_card_text_patches,
    replace_field_text,
    list_reviews_for_target,
    get_review_record,
    get_card_type_schema,
    get_card_content,
]

ASSISTANT_TOOL_REGISTRY = {tool.name: tool for tool in ASSISTANT_TOOLS}

ASSISTANT_TOOL_DESCRIPTIONS = {
    tool.name: {
        "description": tool.description,
        "args": tool.args,
    }
    for tool in ASSISTANT_TOOLS
}