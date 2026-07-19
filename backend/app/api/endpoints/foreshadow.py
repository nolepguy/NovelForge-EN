from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.services.foreshadow_service import ForeshadowService
from app.db.models import ForeshadowItem as ForeshadowItemModel
from app.schemas.foreshadow import (
	SuggestRequest, SuggestResponse,
	ForeshadowRegisterItem, ForeshadowRegisterRequest,
	ForeshadowListResponse, ForeshadowResolveRequest, ForeshadowDeleteRequest,
)

router = APIRouter()

@router.post('/suggest', response_model=SuggestResponse, summary='Foreshadow candidate suggestions (heuristic placeholder)')
def suggest(req: SuggestRequest, session: Session = Depends(get_session)):
    svc = ForeshadowService(session)
    data = svc.suggest(req.text)
    return SuggestResponse(**data)

@router.get('/list', response_model=ForeshadowListResponse, summary='List the project foreshadow registrations')
def list_items(project_id: int, status: str | None = None, session: Session = Depends(get_session)):
    svc = ForeshadowService(session)
    items = svc.list(project_id, status=status)
    return ForeshadowListResponse(items=items)

@router.post('/register', response_model=ForeshadowListResponse, summary='Register a set of foreshadow items')
def register(req: ForeshadowRegisterRequest, session: Session = Depends(get_session)):
    svc = ForeshadowService(session)
    out = svc.register(req.project_id, [i.model_dump() for i in req.items])
    return ForeshadowListResponse(items=out)

@router.post('/resolve/{item_id}', response_model=ForeshadowItemModel, summary='Mark a foreshadow as resolved')
def resolve(item_id: int, req: ForeshadowResolveRequest, session: Session = Depends(get_session)):
    svc = ForeshadowService(session)
    item = svc.resolve(req.project_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail='Foreshadow item not found')
    return item

@router.post('/delete/{item_id}', summary='Delete a foreshadow item')
def delete(item_id: int, req: ForeshadowDeleteRequest, session: Session = Depends(get_session)):
    svc = ForeshadowService(session)
    ok = svc.delete(req.project_id, item_id)
    return {"success": ok} 