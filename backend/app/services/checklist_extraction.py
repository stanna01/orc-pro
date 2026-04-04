"""Checklist extraction service using OCR parsing and timeline normalization."""

import re
from typing import Dict, List
from backend.app.models.schemas import (
    ActivityEntryCreate,
    ChecklistFormCreate,
)
from backend.app.ocr.pipeline import (
    extract_activity_entries,
    extract_page1_fields,
    guess_shift,
)


def build_checklist_payload(raw_text: str) -> ChecklistFormCreate:
    """Build a checklist create payload from OCR text."""
    page1 = extract_page1_fields(raw_text)
    shift = page1.get("shift") or guess_shift(raw_text) or "day"
    activity_entries = extract_activity_entries(raw_text)

    return ChecklistFormCreate(
        source_filename=None,
        document_date=None,
        shift=shift,
        machine_number=page1.get("machine_number"),
        operator_name=page1.get("operator_name"),
        mine_number=page1.get("mine_number"),
        permit_number=page1.get("permit_number"),
        start_engine_hours=_parse_optional_float(page1.get("start_engine_hours")),
        end_engine_hours=_parse_optional_float(page1.get("end_engine_hours")),
        start_transmission_hours=_parse_optional_float(page1.get("start_transmission_hours")),
        end_transmission_hours=_parse_optional_float(page1.get("end_transmission_hours")),
        release_time=page1.get("release_time"),
        daily_checks=[],
        activity_entries=[ActivityEntryCreate(**entry) for entry in activity_entries],
    )


def _parse_optional_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(re.sub(r"[^0-9\.]+", "", value))
    except Exception:
        return None
