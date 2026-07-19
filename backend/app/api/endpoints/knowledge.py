from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List

from app.db.session import get_session
from app.schemas.prompt import KnowledgeRead, KnowledgeCreate, KnowledgeUpdate
from app.schemas.response import ApiResponse
from app.services.knowledge_service import KnowledgeService

router = APIRouter()

@router.get('/', response_model=ApiResponse[List[KnowledgeRead]], summary='Get the list of knowledge bases')
def list_knowledge(session: Session = Depends(get_session)):
    svc = KnowledgeService(session)
    items = svc.list()
    return ApiResponse(data=items)

@router.post('/', response_model=ApiResponse[KnowledgeRead], summary='Create a knowledge base')
def create_knowledge(body: KnowledgeCreate, session: Session = Depends(get_session)):
    svc = KnowledgeService(session)
    if svc.get_by_name(body.name):
        raise HTTPException(status_code=400, detail='A knowledge base with the same name already exists')
    item = svc.create(name=body.name, description=body.description, content=body.content)
    return ApiResponse(data=item)

@router.get('/{kid}', response_model=ApiResponse[KnowledgeRead], summary='Get a single knowledge base')
def get_knowledge(kid: int, session: Session = Depends(get_session)):
    svc = KnowledgeService(session)
    item = svc.get_by_id(kid)
    if not item:
        raise HTTPException(status_code=404, detail='Knowledge base not found')
    return ApiResponse(data=item)

@router.put('/{kid}', response_model=ApiResponse[KnowledgeRead], summary='Update a knowledge base')
def update_knowledge(kid: int, body: KnowledgeUpdate, session: Session = Depends(get_session)):
    svc = KnowledgeService(session)
    item = svc.update(kid, name=body.name, description=body.description, content=body.content)
    if not item:
        raise HTTPException(status_code=404, detail='Knowledge base not found')
    return ApiResponse(data=item)

@router.delete('/{kid}', response_model=ApiResponse, summary='Delete a knowledge base')
def delete_knowledge(kid: int, session: Session = Depends(get_session)):
    svc = KnowledgeService(session)
    item = svc.get_by_id(kid)
    if not item:
        raise HTTPException(status_code=404, detail='Knowledge base not found')
    if getattr(item, 'built_in', False):
        raise HTTPException(status_code=400, detail='Built-in knowledge bases cannot be deleted')
    ok = svc.delete(kid)
    if not ok:
        raise HTTPException(status_code=404, detail='Knowledge base not found')
    return ApiResponse(message='Deleted successfully') 