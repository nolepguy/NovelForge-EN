from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlmodel import Session
from app.db.session import get_session
from app.schemas.prompt import PromptRead, PromptCreate, PromptUpdate
from app.schemas.response import ApiResponse
from app.services import prompt_service

router = APIRouter()

@router.post("/", response_model=ApiResponse[PromptRead], summary="Create a new prompt")
def create_prompt(
    *,
    session: Session = Depends(get_session),
    prompt: PromptCreate,
):
    """
    Create a new prompt template.
    """
    new_prompt = prompt_service.create_prompt(session=session, prompt_create=prompt)
    return ApiResponse(data=new_prompt)

@router.get("/", response_model=ApiResponse[List[PromptRead]], summary="Get the list of prompts")
def read_prompts(
    *,
    session: Session = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
):
    """
    Get a list of all prompt templates.
    """
    prompts = prompt_service.get_prompts(session=session, skip=skip, limit=limit)
    return ApiResponse(data=prompts)

@router.get("/{prompt_id}", response_model=ApiResponse[PromptRead], summary="Get a single prompt")
def read_prompt(
    *,
    session: Session = Depends(get_session),
    prompt_id: int,
):
    """
    Get the details of a single prompt template by ID.
    """
    db_prompt = prompt_service.get_prompt(session=session, prompt_id=prompt_id)
    if not db_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return ApiResponse(data=db_prompt)

@router.put("/{prompt_id}", response_model=ApiResponse[PromptRead], summary="Update a prompt")
def update_prompt(
    *,
    session: Session = Depends(get_session),
    prompt_id: int,
    prompt: PromptUpdate,
):
    """
    Update an existing prompt template.
    """
    updated_prompt = prompt_service.update_prompt(session=session, prompt_id=prompt_id, prompt_update=prompt)
    if not updated_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return ApiResponse(data=updated_prompt)

@router.delete("/{prompt_id}", response_model=ApiResponse, summary="Delete a prompt")
def delete_prompt(
    *,
    session: Session = Depends(get_session),
    prompt_id: int,
):
    """
    Delete a prompt template.
    """
    db_prompt = prompt_service.get_prompt(session=session, prompt_id=prompt_id)
    if not db_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if getattr(db_prompt, 'built_in', False):
        raise HTTPException(status_code=400, detail="Built-in prompts cannot be deleted")
    if not prompt_service.delete_prompt(session=session, prompt_id=prompt_id):
        raise HTTPException(status_code=404, detail="Prompt not found")
    return ApiResponse(message="Prompt deleted successfully") 