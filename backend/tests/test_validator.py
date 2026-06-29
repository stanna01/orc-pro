"""Tests for the validation engine (validator.py).

Covers:
- Time format validation
- Chronological order within rows
- Cross-row chronological order
- Overlap detection
- Shift boundary checks (day and night, including overnight logic)
- Confidence aggregation null-safety (checklist_extraction)
"""

import pytest
from backend.app.models.schemas import OCRField, OCRHeader, OCRActivityRow, OCROutput
from backend.app.services.validator import validate_checklist


def _field(val, conf=0.8):
    return OCRField(value=val, confidence=conf, classification="medium")


def _header(shift="day"):
    return OCRHeader(
        machine_id=_field("LOAD-1"),
        operator_name=_field("Op"),
        date=_field("2026-06-01"),
        shift=_field(shift),
        engine_hours_start=_field("100"),
        engine_hours_end=_field("112"),
    )


def _row(idx, from_t, to_t, code="101"):
    return OCRActivityRow(
        row_index=idx,
        activity_code=_field(code),
        from_time=_field(from_t),
        to_time=_field(to_t),
        location=_field("Pit A"),
        loads=_field("2"),
        remarks=_field(""),
    )


def _make(activities, shift="day"):
    return OCROutput(
        document_id="test",
        header=_header(shift),
        activities=activities,
    )


# ---------------------------------------------------------------------------
# Empty activities
# ---------------------------------------------------------------------------

def test_no_activities_needs_review():
    report = validate_checklist(_make([]))
    assert report.needs_review
    assert any("No activity rows" in e.message for e in report.errors)


# ---------------------------------------------------------------------------
# Time format
# ---------------------------------------------------------------------------

def test_invalid_start_time_flagged():
    report = validate_checklist(_make([_row(0, "8:00", "09:00")]))
    assert any("start time" in e.message for e in report.errors)


def test_invalid_end_time_flagged():
    report = validate_checklist(_make([_row(0, "08:00", "9:00")]))
    assert any("end time" in e.message for e in report.errors)


def test_valid_times_no_format_errors():
    report = validate_checklist(_make([_row(0, "08:00", "09:00")]))
    format_errors = [e for e in report.errors if "time" in e.message.lower() and "Invalid" in e.message]
    assert not format_errors


# ---------------------------------------------------------------------------
# Chronological order within a row
# ---------------------------------------------------------------------------

def test_end_before_start_flagged():
    report = validate_checklist(_make([_row(0, "10:00", "09:00")]))
    assert any("End time earlier" in e.message for e in report.errors)
    assert report.needs_review


def test_equal_times_not_flagged_as_order_error():
    report = validate_checklist(_make([_row(0, "08:00", "08:00")]))
    order_errors = [e for e in report.errors if "End time earlier" in e.message]
    assert not order_errors


# ---------------------------------------------------------------------------
# Overlap detection
# ---------------------------------------------------------------------------

def test_overlapping_activities_flagged():
    rows = [_row(0, "08:00", "09:30"), _row(1, "09:00", "10:00")]
    report = validate_checklist(_make(rows))
    assert any("Overlapping" in e.message for e in report.errors)
    assert report.needs_review


def test_non_overlapping_activities_not_flagged():
    rows = [_row(0, "08:00", "09:00"), _row(1, "09:00", "10:00")]
    report = validate_checklist(_make(rows))
    overlap_errors = [e for e in report.errors if "Overlapping" in e.message]
    assert not overlap_errors


# ---------------------------------------------------------------------------
# Day shift boundary
# ---------------------------------------------------------------------------

def test_day_shift_within_boundary_no_warning():
    rows = [_row(0, "07:00", "12:00"), _row(1, "12:00", "17:00")]
    report = validate_checklist(_make(rows, shift="day"))
    boundary_warnings = [e for e in report.errors if "outside" in e.message and e.severity == "warning"]
    assert not boundary_warnings


def test_day_shift_before_start_flagged():
    rows = [_row(0, "05:00", "07:00")]
    report = validate_checklist(_make(rows, shift="day"))
    assert any("outside" in e.message for e in report.errors)


def test_day_shift_after_end_flagged():
    rows = [_row(0, "17:00", "19:00")]
    report = validate_checklist(_make(rows, shift="day"))
    assert any("outside" in e.message for e in report.errors)


# ---------------------------------------------------------------------------
# Night shift boundary — the critical fix
# ---------------------------------------------------------------------------

def test_night_shift_evening_block_not_flagged():
    """19:00–21:00 is a valid night-shift activity in the evening."""
    rows = [_row(0, "19:00", "21:00")]
    report = validate_checklist(_make(rows, shift="night"))
    boundary_warnings = [e for e in report.errors if "outside" in e.message.lower()]
    assert not boundary_warnings, (
        f"Valid evening block flagged: {[e.message for e in boundary_warnings]}"
    )


def test_night_shift_early_morning_block_not_flagged():
    """01:00–05:30 is a valid night-shift activity after midnight."""
    rows = [_row(0, "01:00", "05:30")]
    report = validate_checklist(_make(rows, shift="night"))
    boundary_warnings = [e for e in report.errors if "outside" in e.message.lower()]
    assert not boundary_warnings, (
        f"Valid early-morning block flagged: {[e.message for e in boundary_warnings]}"
    )


def test_night_shift_midnight_spanning_not_flagged():
    """22:00–02:00 spans midnight — must not be flagged as out of bounds."""
    rows = [_row(0, "22:00", "02:00")]
    report = validate_checklist(_make(rows, shift="night"))
    boundary_warnings = [e for e in report.errors if "outside" in e.message.lower()]
    assert not boundary_warnings, (
        f"Midnight-spanning interval flagged: {[e.message for e in boundary_warnings]}"
    )


def test_night_shift_daytime_activity_flagged():
    """10:00–12:00 is in the middle of the day — clearly outside night shift."""
    rows = [_row(0, "10:00", "12:00")]
    report = validate_checklist(_make(rows, shift="night"))
    assert any("outside" in e.message.lower() for e in report.errors), (
        "Daytime activity during night shift should be flagged"
    )


# ---------------------------------------------------------------------------
# Confidence null safety (from checklist_extraction fix)
# ---------------------------------------------------------------------------

def test_confidence_none_field_does_not_crash():
    """Rows where some OCR fields have confidence=None must not crash build_checklist_payload."""
    from backend.app.services.checklist_extraction import build_checklist_payload
    ocr = OCROutput(
        document_id="nullconf",
        header=OCRHeader(
            machine_id=OCRField(value="M1", confidence=None),
            operator_name=OCRField(value="Op", confidence=0.9),
            date=OCRField(value="2026-06-01", confidence=0.9),
            shift=OCRField(value="day", confidence=0.9),
            engine_hours_start=OCRField(value="100", confidence=None),
            engine_hours_end=OCRField(value="112", confidence=None),
        ),
        activities=[
            OCRActivityRow(
                row_index=0,
                activity_code=OCRField(value="101", confidence=None),
                from_time=OCRField(value="08:00", confidence=None),
                to_time=OCRField(value="09:00", confidence=None),
                location=OCRField(value="Pit A", confidence=None),
                loads=OCRField(value="2", confidence=None),
                remarks=OCRField(value="", confidence=None),
            )
        ],
    )
    payload = build_checklist_payload(ocr)
    assert payload.activity_entries[0].confidence == 0.0


def test_confidence_mixed_none_and_float():
    """When some fields have confidence and others don't, min of non-None values is used."""
    from backend.app.services.checklist_extraction import build_checklist_payload
    ocr = OCROutput(
        document_id="mixedconf",
        header=OCRHeader(
            machine_id=OCRField(value="M1", confidence=0.9),
            operator_name=OCRField(value="Op", confidence=0.9),
            date=OCRField(value="2026-06-01", confidence=0.9),
            shift=OCRField(value="day", confidence=0.9),
            engine_hours_start=OCRField(value="100", confidence=0.9),
            engine_hours_end=OCRField(value="112", confidence=0.9),
        ),
        activities=[
            OCRActivityRow(
                row_index=0,
                activity_code=OCRField(value="101", confidence=0.7),
                from_time=OCRField(value="08:00", confidence=None),   # None
                to_time=OCRField(value="09:00", confidence=0.6),
                location=OCRField(value="Pit A", confidence=0.8),
                loads=OCRField(value="2", confidence=None),            # None
                remarks=OCRField(value="", confidence=0.5),
            )
        ],
    )
    payload = build_checklist_payload(ocr)
    # min of [0.7, 0.6, 0.8, 0.5] = 0.5
    assert abs(payload.activity_entries[0].confidence - 0.5) < 1e-9
