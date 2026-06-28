"""Checklist extraction service using OCR parsing and timeline normalization."""

import re
from datetime import date
from typing import Dict, List, Optional
from backend.app.models.schemas import (
    ActivityEntryCreate,
    ChecklistFormCreate,
    OCROutput,
)
from backend.app.ml.ocr.pipeline import (
    extract_activity_entries,
    extract_page1_fields,
    guess_shift,
)


def validate_ocr_output(ocr_data: OCROutput) -> None:
    """Validate OCR output against schema and business rules."""
    if not ocr_data.document_id:
        raise ValueError("OCR output must have a valid document_id")

    if not ocr_data.header:
        raise ValueError("OCR output must have header information")

    # Check required header fields have values
    required_fields = ["machine_id", "operator_name", "date", "shift"]
    for field_name in required_fields:
        field = getattr(ocr_data.header, field_name)
        if not field.value:
            raise ValueError(f"Required header field '{field_name}' is missing or empty")

    # Validate shift value (normalize to lowercase before checking)
    shift_val = (ocr_data.header.shift.value or "").lower().strip()
    if shift_val not in ["day", "night"]:
        raise ValueError(f"Invalid shift value: {ocr_data.header.shift.value!r}. Must be 'day' or 'night'")

    # Validate date format (basic check)
    if ocr_data.header.date.value:
        try:
            # Simple YYYY-MM-DD check
            parts = ocr_data.header.date.value.split("-")
            if len(parts) != 3 or len(parts[0]) != 4:
                raise ValueError(f"Invalid date format: {ocr_data.header.date.value}. Expected YYYY-MM-DD")
        except:
            raise ValueError(f"Invalid date format: {ocr_data.header.date.value}. Expected YYYY-MM-DD")

    # Validate activity rows
    for activity in ocr_data.activities:
        if activity.row_index < 0:
            raise ValueError(f"Invalid row_index: {activity.row_index}. Must be >= 0")


def build_checklist_payload(ocr_data: OCROutput) -> ChecklistFormCreate:
    """Build a checklist create payload from validated OCR output."""
    # Validate input
    validate_ocr_output(ocr_data)

    # Map OCR header to checklist fields
    header = ocr_data.header

    # Convert activity rows to ActivityEntryCreate
    activity_entries = []
    for activity in ocr_data.activities:
        activity_entries.append(ActivityEntryCreate(
            row_index=activity.row_index,
            activity_code_raw=activity.activity_code.value,
            from_time_raw=activity.from_time.value,
            to_time_raw=activity.to_time.value,
            workplace_raw=activity.location.value,
            loads_raw=activity.loads.value,
            remarks_raw=activity.remarks.value,
            confidence=min([
                activity.activity_code.confidence,
                activity.from_time.confidence,
                activity.to_time.confidence,
                activity.location.confidence,
                activity.loads.confidence,
                activity.remarks.confidence
            ]) if all([
                activity.activity_code.value,
                activity.from_time.value,
                activity.to_time.value
            ]) else 0.0,
            raw_text=f"{activity.activity_code.value or ''} {activity.from_time.value or ''} {activity.to_time.value or ''} {activity.location.value or ''} {activity.loads.value or ''} {activity.remarks.value or ''}".strip()
        ))

    return ChecklistFormCreate(
        source_filename=ocr_data.document_id,
        document_date=_parse_date(header.date.value),
        shift=(header.shift.value or "").lower().strip(),
        machine_number=header.machine_id.value,
        operator_name=header.operator_name.value,
        mine_number=None,  # Not in current OCR schema
        permit_number=None,  # Not in current OCR schema
        start_engine_hours=_parse_optional_float(header.engine_hours_start.value),
        end_engine_hours=_parse_optional_float(header.engine_hours_end.value),
        start_transmission_hours=None,  # Not in current OCR schema
        end_transmission_hours=None,  # Not in current OCR schema
        release_time=None,  # Not in current OCR schema
        daily_checks=[],  # Not extracted by OCR
        activity_entries=activity_entries,
    )


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return date.fromisoformat(value) if fmt == "%Y-%m-%d" else __import__("datetime").datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _parse_optional_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(re.sub(r"[^0-9\.]+", "", value))
    except Exception:
        return None
