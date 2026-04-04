"""Business logic for checklist persistence and retrieval."""

from typing import List
from sqlalchemy.orm import Session
from backend.app.models.checklist import (
    ActivityEntry,
    ChecklistForm,
    DailyCheckEntry,
)
from backend.app.models.schemas import ChecklistFormCreate


def create_checklist_form(db: Session, payload: ChecklistFormCreate) -> ChecklistForm:
    """Create a new checklist form and associated table entries.

    Args:
        db: Database session.
        payload: Checklist form create schema.

    Returns:
        ChecklistForm: Newly created checklist form.
    """
    checklist_form = ChecklistForm(
        source_filename=payload.source_filename,
        document_date=payload.document_date,
        shift=payload.shift.lower(),
        machine_number=payload.machine_number,
        operator_name=payload.operator_name,
        mine_number=payload.mine_number,
        permit_number=payload.permit_number,
        start_engine_hours=payload.start_engine_hours,
        end_engine_hours=payload.end_engine_hours,
        start_transmission_hours=payload.start_transmission_hours,
        end_transmission_hours=payload.end_transmission_hours,
        release_time=payload.release_time,
    )

    if payload.daily_checks:
        checklist_form.daily_checks = [
            DailyCheckEntry(
                row_index=entry.row_index,
                check_item=entry.check_item,
                status=entry.status,
                raw_value=entry.raw_value,
                normalized_value=entry.normalized_value,
                remarks=entry.remarks,
                duration_minutes=entry.duration_minutes,
                is_service_action=entry.is_service_action,
            )
            for entry in payload.daily_checks
        ]

    if payload.activity_entries:
        checklist_form.activity_entries = [
            ActivityEntry(
                row_index=entry.row_index,
                activity_code_raw=entry.activity_code_raw,
                activity_code_normalized=entry.activity_code_normalized,
                from_time_raw=entry.from_time_raw,
                to_time_raw=entry.to_time_raw,
                workplace_raw=entry.workplace_raw,
                workplace_normalized=entry.workplace_normalized,
                ore_waste_raw=entry.ore_waste_raw,
                ore_waste_normalized=entry.ore_waste_normalized,
                loads_raw=entry.loads_raw,
                loads_normalized=entry.loads_normalized,
                remarks_raw=entry.remarks_raw,
                remarks_normalized=entry.remarks_normalized,
                confidence=entry.confidence,
                raw_text=entry.raw_text,
            )
            for entry in payload.activity_entries
        ]

    db.add(checklist_form)
    db.commit()
    db.refresh(checklist_form)
    return checklist_form


def get_checklist_form(db: Session, checklist_id: int) -> ChecklistForm | None:
    """Retrieve a checklist form by its ID."""
    return db.query(ChecklistForm).filter(ChecklistForm.id == checklist_id).first()


def list_checklist_forms(db: Session, limit: int = 50, offset: int = 0) -> List[ChecklistForm]:
    """Return a paginated list of checklist forms."""
    return db.query(ChecklistForm).order_by(ChecklistForm.created_at.desc()).limit(limit).offset(offset).all()
