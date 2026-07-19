from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.db.session import get_session
from app.db.models import OutputModel

router = APIRouter()

@router.get("/", response_model=List[OutputModel])
def list_output_models(db: Session = Depends(get_session)):
    return db.exec(select(OutputModel)).all()

@router.post("/", response_model=OutputModel)
def create_output_model(model: OutputModel, db: Session = Depends(get_session)):
    # Simple uniqueness check
    exists = db.exec(select(OutputModel).where(OutputModel.name == model.name)).first()
    if exists:
        raise HTTPException(status_code=400, detail="Output model name already exists")
    db.add(model)
    db.commit()
    db.refresh(model)
    return model

@router.put("/{model_id}", response_model=OutputModel)
def update_output_model(model_id: int, data: OutputModel, db: Session = Depends(get_session)):
    om = db.get(OutputModel, model_id)
    if not om:
        raise HTTPException(status_code=404, detail="Output model not found")
    # Only update writable fields
    om.description = data.description
    om.json_schema = data.json_schema
    om.version = (om.version or 1) + 1
    db.add(om)
    db.commit()
    db.refresh(om)
    return om

@router.delete("/{model_id}")
def delete_output_model(model_id: int, db: Session = Depends(get_session)):
    om = db.get(OutputModel, model_id)
    if not om:
        raise HTTPException(status_code=404, detail="Output model not found")
    if getattr(om, 'built_in', False):
        raise HTTPException(status_code=400, detail="Built-in output models cannot be deleted")
    db.delete(om)
    db.commit()
    return {"ok": True} 