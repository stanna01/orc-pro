"""Checklist API routes for ORC Pro."""

from typing import List
from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.models.schemas import ChecklistFormCreate, ChecklistFormResponse
from backend.app.services.checklist_service import (
    create_checklist_form,
    get_checklist_form,
    list_checklist_forms,
)
from backend.app.services.checklist_extraction import build_checklist_payload

router = APIRouter(prefix="/checklists", tags=["checklists"])


@router.post("/", response_model=ChecklistFormResponse, status_code=status.HTTP_201_CREATED)
def create_checklist(checklist: ChecklistFormCreate, db: Session = Depends(get_session)) -> ChecklistFormResponse:
    """Create a new checklist form with page 1 and page 2 data."""
    created = create_checklist_form(db=db, payload=checklist)
    return created


@router.get("/", response_model=List[ChecklistFormResponse])
def read_checklists(limit: int = 50, offset: int = 0, db: Session = Depends(get_session)) -> List[ChecklistFormResponse]:
    """List checklist forms with pagination."""
    return list_checklist_forms(db=db, limit=limit, offset=offset)


@router.post("/extract", response_model=ChecklistFormCreate, status_code=status.HTTP_200_OK)
def extract_checklist(raw_text: str = Body(..., description="Raw OCR text for the checklist document.")) -> ChecklistFormCreate:
    """Parse raw OCR text into a structured checklist payload."""
    parsed = build_checklist_payload(raw_text)
    return parsed


@router.get("/{checklist_id}", response_model=ChecklistFormResponse)
def read_checklist(checklist_id: int, db: Session = Depends(get_session)) -> ChecklistFormResponse:
    """Retrieve a checklist form by its unique identifier."""
    checklist = get_checklist_form(db=db, checklist_id=checklist_id)
    if not checklist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist form not found")
    return checklist
