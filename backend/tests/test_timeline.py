"""Tests for timeline inference and analytics."""

from backend.app.services.rule_engine import infer_to_times
from backend.app.ml.ocr.pipeline import is_breakdown


def test_infer_times_for_entries_missing_to_time():
    entries = [
        {"from_time_raw": "18:00", "to_time_raw": None, "duration_minutes": 0},
        {"from_time_raw": "19:30", "to_time_raw": "20:15", "duration_minutes": 45},
    ]

    processed = infer_to_times(entries)
    assert processed[0]["to_time_raw"] == "19:30"
    assert processed[0]["duration_minutes"] == 90
    assert processed[1]["from_time_raw"] == "19:30"


def test_check_for_breakdown_conditions():
    entries = [
        {"activity_code_raw": "300", "remarks_raw": "Hydraulic failure reported"},
        {"activity_code_raw": "101", "remarks_raw": "Normal"},
    ]

    alerts = [is_breakdown(entry.get("activity_code_raw"), entry.get("remarks_raw")) for entry in entries]
    assert any(alert for alert in alerts)
