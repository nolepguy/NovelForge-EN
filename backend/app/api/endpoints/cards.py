from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List, Dict, Any
from urllib.parse import quote

from app.db.session import get_session
from app.services.card_service import CardService, CardTypeService
from app.services.card_export_service import CardExportService
from app.services.schema_service import compose_schema_with_card_types, localize_schema_titles
from app.services.card_params_service import merge_effective_ai_params
from app.schemas.card import (
    CardRead, CardCreate, CardUpdate, 
    CardTypeRead, CardTypeCreate, CardTypeUpdate,
    CardBatchReorderRequest,
    CardExportRequest,
)
from app.db.models import Card, CardType
from app.exceptions import BusinessException
from loguru import logger

from app.schemas.card import CardCopyOrMoveRequest
from app.core import emit_event
from fastapi import Response

router = APIRouter()


def _resolve_card_type_name(db: Session, card: Card) -> str | None:
    """Resolve card type name for event payloads reliably."""
    card_type = getattr(card, "card_type", None)
    if card_type and getattr(card_type, "name", None):
        return str(card_type.name)

    card_type_id = getattr(card, "card_type_id", None)
    if not card_type_id:
        return None

    db_card_type = db.get(CardType, card_type_id)
    if db_card_type and getattr(db_card_type, "name", None):
        return str(db_card_type.name)
    return None

# --- CardType Endpoints ---
# Note: CardTypeRead must include the default_ai_context_template field (controlled by the Pydantic schema definition).

@router.post("/card-types", response_model=CardTypeRead)
def create_card_type(card_type: CardTypeCreate, db: Session = Depends(get_session)):
    service = CardTypeService(db)
    created = service.create(card_type)
    data = created.model_dump()
    data["json_schema"] = localize_schema_titles(data.get("json_schema"))
    return data

@router.get("/card-types", response_model=List[CardTypeRead])
def get_all_card_types(db: Session = Depends(get_session)):
    service = CardTypeService(db)
    result = []
    for card_type in service.get_all():
        data = card_type.model_dump()
        data["json_schema"] = localize_schema_titles(data.get("json_schema"))
        result.append(data)
    return result

@router.get("/card-types/{card_type_id}", response_model=CardTypeRead)
def get_card_type(card_type_id: int, db: Session = Depends(get_session)):
    service = CardTypeService(db)
    db_card_type = service.get_by_id(card_type_id)
    if db_card_type is None:
        raise HTTPException(status_code=404, detail="CardType not found")
    data = db_card_type.model_dump()
    data["json_schema"] = localize_schema_titles(data.get("json_schema"))
    return data

@router.put("/card-types/{card_type_id}", response_model=CardTypeRead)
def update_card_type(card_type_id: int, card_type: CardTypeUpdate, db: Session = Depends(get_session)):
    service = CardTypeService(db)
    db_card_type = service.update(card_type_id, card_type)
    if db_card_type is None:
        raise HTTPException(status_code=404, detail="CardType not found")
    data = db_card_type.model_dump()
    data["json_schema"] = localize_schema_titles(data.get("json_schema"))
    return data

@router.delete("/card-types/{card_type_id}", status_code=204)
def delete_card_type(card_type_id: int, db: Session = Depends(get_session)):
    service = CardTypeService(db)
    db_card_type = service.get_by_id(card_type_id)
    if not db_card_type:
        raise HTTPException(status_code=404, detail="CardType not found")
    if getattr(db_card_type, 'built_in', False):
        raise HTTPException(status_code=400, detail="Built-in card types cannot be deleted")
    if not service.delete(card_type_id):
        raise HTTPException(status_code=404, detail="CardType not found")
    return {"ok": True}

# --- CardType Schema Endpoints ---

@router.get("/card-types/{card_type_id}/schema")
def get_card_type_schema(card_type_id: int, db: Session = Depends(get_session)) -> Dict[str, Any]:
    ct = db.get(CardType, card_type_id)
    if not ct:
        raise HTTPException(status_code=404, detail="CardType not found")
    localized_schema = localize_schema_titles(ct.json_schema) if isinstance(ct.json_schema, dict) else ct.json_schema
    return {"json_schema": localized_schema}

@router.put("/card-types/{card_type_id}/schema")
def update_card_type_schema(card_type_id: int, payload: Dict[str, Any], db: Session = Depends(get_session)) -> Dict[str, Any]:
    ct = db.get(CardType, card_type_id)
    if not ct:
        raise HTTPException(status_code=404, detail="CardType not found")
    ct.json_schema = payload.get("json_schema")
    db.add(ct)
    db.commit()
    db.refresh(ct)
    localized_schema = localize_schema_titles(ct.json_schema) if isinstance(ct.json_schema, dict) else ct.json_schema
    return {"json_schema": localized_schema}

# --- CardType AI Params Endpoints ---

@router.get("/card-types/{card_type_id}/ai-params")
def get_card_type_ai_params(card_type_id: int, db: Session = Depends(get_session)) -> Dict[str, Any]:
    ct = db.get(CardType, card_type_id)
    if not ct:
        raise HTTPException(status_code=404, detail="CardType not found")
    return {"ai_params": getattr(ct, 'ai_params', None)}

@router.put("/card-types/{card_type_id}/ai-params")
def update_card_type_ai_params(card_type_id: int, payload: Dict[str, Any], db: Session = Depends(get_session)) -> Dict[str, Any]:
    ct = db.get(CardType, card_type_id)
    if not ct:
        raise HTTPException(status_code=404, detail="CardType not found")
    ct.ai_params = payload.get("ai_params")
    db.add(ct)
    db.commit()
    db.refresh(ct)
    return {"ai_params": ct.ai_params}

# --- Card Endpoints ---

@router.post("/projects/{project_id}/cards", response_model=CardRead)
def create_card_for_project(project_id: int, card: CardCreate, db: Session = Depends(get_session)):
    service = CardService(db)
    try:
        created = service.create(card, project_id)
        triggered_run_ids = []
        try:
            event_data = {
                "session": db,
                "card": created,
                "is_created": True,
                "card_type": _resolve_card_type_name(db, created),
            }
            emit_event("card.saved", event_data)
            triggered_run_ids = event_data.get("triggered_run_ids", [])
        except Exception:
            logger.exception("OnSave workflow trigger failed")
        
        # Header is managed by Middleware
        
        return created
    except BusinessException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/projects/{project_id}/cards/search", response_model=List[CardRead])
def search_cards(project_id: int, q: str, db: Session = Depends(get_session)):
    service = CardService(db)
    return service.search(project_id, q)

@router.get("/projects/{project_id}/cards", response_model=List[CardRead])
def get_all_cards_for_project(project_id: int, db: Session = Depends(get_session)):
    service = CardService(db)
    return service.get_all_for_project(project_id)


@router.post("/projects/{project_id}/cards/export")
def export_cards_for_project(project_id: int, payload: CardExportRequest, db: Session = Depends(get_session)):
    service = CardExportService(db)
    try:
        exported = service.export(project_id=project_id, request=payload)
        disposition = f"attachment; filename*=UTF-8''{quote(exported.filename)}"
        return Response(
            content=exported.content,
            media_type=exported.media_type,
            headers={"Content-Disposition": disposition},
        )
    except BusinessException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/cards/{card_id}", response_model=CardRead)
def get_card(card_id: int, db: Session = Depends(get_session)):
    service = CardService(db)
    db_card = service.get_by_id(card_id)
    if db_card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return db_card

@router.put("/cards/{card_id}", response_model=CardRead)
def update_card(card_id: int, card: CardUpdate, db: Session = Depends(get_session)):
    # Get the state before the update
    old_card = db.get(Card, card_id)
    old_content = None
    if old_card and old_card.content:
        import copy
        old_content = copy.deepcopy(old_card.content)

    was_needs_confirmation = getattr(old_card, 'needs_confirmation', False) if old_card else False
    
    service = CardService(db)
    db_card = service.update(card_id, card)
    if db_card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    
    # Check whether it transitioned from "needs confirmation" to "confirmed"
    is_now_confirmed = was_needs_confirmation and not getattr(db_card, 'needs_confirmation', False)
    
    # Handling on user save
    if is_now_confirmed:
        # Scenario 1: the user confirmed an AI-modified card
        logger.info(f"✅ User confirmed AI-modified card {card_id}, preparing to trigger workflow")
        db_card.last_modified_by = "user"
        db_card.ai_modified = False  # Clear the AI-modified flag
        db.add(db_card)
        db.commit()
        db.refresh(db_card)
    elif not was_needs_confirmation and getattr(db_card, 'last_modified_by', None) != 'user':
        # Scenario 2: the user manually edited the card (not AI-created, or already confirmed)
        # Mark as user-modified, but do not affect workflow triggering
        db_card.last_modified_by = "user"
        db.add(db_card)
        db.commit()
        db.refresh(db_card)
    
    triggered_run_ids = []
    try:
        event_data = {
            "session": db, 
            "card": db_card, 
            "is_created": False,
            "old_content": old_content,
            "card_type": _resolve_card_type_name(db, db_card),
        }
        emit_event("card.saved", event_data)
        triggered_run_ids = event_data.get("triggered_run_ids", [])
        
        if is_now_confirmed and triggered_run_ids:
            logger.info(f"🎯 AI-modified card confirmation triggered {len(triggered_run_ids)} workflows")
    except Exception:
        logger.exception("OnSave workflow trigger failed")
    
    # Header is managed by Middleware
    
    return db_card


@router.post("/cards/batch-reorder")
def batch_reorder_cards(request: CardBatchReorderRequest, db: Session = Depends(get_session)):
    """
    Batch update card ordering.
    
    Args:
        request: Contains the list of cards to update; each card includes card_id, display_order, parent_id
        
    Returns:
        The number of updated cards and a success status
    """
    try:
        updated_count = 0
        
        # Batch update all cards
        for item in request.updates:
            card = db.get(Card, item.card_id)
            if card:
                # Update display_order
                card.display_order = item.display_order
                
                # Update parent_id (always update whether changed or not, since the frontend explicitly passes the value)
                # This correctly handles: setting to root level (null), setting as a child card (with value), keeping unchanged (passing current value)
                card.parent_id = item.parent_id
                    
                db.add(card)
                updated_count += 1
        
        # Commit all updates at once
        db.commit()
        
        logger.info(f"Batch reorder completed, updated {updated_count} cards")
        
        return {
            "success": True,
            "updated_count": updated_count,
            "message": f"Successfully updated ordering for {updated_count} cards"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Batch reorder failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.delete("/cards/{card_id}", status_code=204)
def delete_card(card_id: int, db: Session = Depends(get_session)):
    service = CardService(db)
    if not service.delete(card_id):
        raise HTTPException(status_code=404, detail="Card not found")
    return {"ok": True}

@router.post("/cards/{card_id}/copy", response_model=CardRead)
def copy_card_endpoint(card_id: int, payload: CardCopyOrMoveRequest, db: Session = Depends(get_session)):
    service = CardService(db)
    try:
        copied = service.copy_card(card_id, payload.target_project_id, payload.parent_id)
        if not copied:
            raise HTTPException(status_code=404, detail="Card not found")
        return copied
    except BusinessException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/cards/{card_id}/move", response_model=CardRead)
def move_card_endpoint(card_id: int, payload: CardCopyOrMoveRequest, db: Session = Depends(get_session)):
    service = CardService(db)
    try:
        moved = service.move_card(card_id, payload.target_project_id, payload.parent_id)
        if not moved:
            raise HTTPException(status_code=404, detail="Card not found")
        return moved
    except BusinessException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) 

# --- Card Schema Endpoints ---

@router.get("/cards/{card_id}/schema")
def get_card_schema(card_id: int, db: Session = Depends(get_session)) -> Dict[str, Any]:
    c = db.get(Card, card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    effective = c.json_schema if c.json_schema is not None else (c.card_type.json_schema if c.card_type else None)
    # Dynamically assemble references
    composed = compose_schema_with_card_types(db, effective or {})
    return {"json_schema": c.json_schema, "effective_schema": composed, "follow_type": c.json_schema is None}

@router.put("/cards/{card_id}/schema")
def update_card_schema(card_id: int, payload: Dict[str, Any], db: Session = Depends(get_session)) -> Dict[str, Any]:
    c = db.get(Card, card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    # Passing null/None means restore follow-type behavior
    c.json_schema = payload.get("json_schema", None)
    db.add(c)
    db.commit()
    db.refresh(c)
    effective = c.json_schema if c.json_schema is not None else (c.card_type.json_schema if c.card_type else None)
    composed = compose_schema_with_card_types(db, effective or {})
    return {"json_schema": c.json_schema, "effective_schema": composed, "follow_type": c.json_schema is None}

@router.post("/cards/{card_id}/schema/apply-to-type")
def apply_card_schema_to_type(card_id: int, db: Session = Depends(get_session)) -> Dict[str, Any]:
    c = db.get(Card, card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    if not c.card_type:
        raise HTTPException(status_code=400, detail="Card has no type")
    # Take the instance schema; if empty, take the effective schema
    effective = c.json_schema if c.json_schema is not None else (c.card_type.json_schema or None)
    if effective is None:
        raise HTTPException(status_code=400, detail="No schema to apply")
    c.card_type.json_schema = effective
    db.add(c.card_type)
    db.commit()
    db.refresh(c.card_type)
    return {"json_schema": c.card_type.json_schema} 

# --- Card AI Params Endpoints ---

@router.get("/cards/{card_id}/ai-params")
def get_card_ai_params(card_id: int, db: Session = Depends(get_session)) -> Dict[str, Any]:
    c = db.get(Card, card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    effective = merge_effective_ai_params(db, c)
    return {"ai_params": c.ai_params, "effective_params": effective, "follow_type": c.ai_params is None}

@router.put("/cards/{card_id}/ai-params")
def update_card_ai_params(card_id: int, payload: Dict[str, Any], db: Session = Depends(get_session)) -> Dict[str, Any]:
    c = db.get(Card, card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    c.ai_params = payload.get("ai_params", None)
    db.add(c)
    db.commit()
    db.refresh(c)
    effective = merge_effective_ai_params(db, c)
    return {"ai_params": c.ai_params, "effective_params": effective, "follow_type": c.ai_params is None}

@router.post("/cards/{card_id}/ai-params/apply-to-type")
def apply_card_ai_params_to_type(card_id: int, db: Session = Depends(get_session)) -> Dict[str, Any]:
    c = db.get(Card, card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    effective = merge_effective_ai_params(db, c)
    if not effective:
        raise HTTPException(status_code=400, detail="No ai_params to apply")
    if not c.card_type:
        raise HTTPException(status_code=400, detail="Card has no type")
    c.card_type.ai_params = effective
    db.add(c.card_type)
    db.commit()
    db.refresh(c.card_type)
    return {"ai_params": c.card_type.ai_params} 
