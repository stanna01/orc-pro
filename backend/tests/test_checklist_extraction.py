"""Tests for checklist OCR extraction and parsing."""

from backend.app.ocr.pipeline import extract_page1_fields, extract_activity_entries
from backend.app.services.checklist_extraction import build_checklist_payload


def test_extract_page1_fields():
    raw_text = (
        "Machine Number: LOAD-001\n"
        "Operator Name: Juan Perez\n"
        "Mine Number: MINE-01\n"
        "Permit Number: PERMIT-123\n"
        "Date: 2026-04-04\n"
        "Shift: Night\n"
        "Start Engine Hours: 1200.5\n"
        "End Engine Hours: 1212.3\n"
        "Start Transmission Hours: 800.0\n"
        "End Transmission Hours: 810.2\n"
    )
    fields = extract_page1_fields(raw_text)
    assert fields["machine_number"] == "LOAD-001"
    assert fields["operator_name"] == "Juan Perez"
    assert fields["mine_number"] == "MINE-01"
    assert fields["permit_number"] == "PERMIT-123"
    assert fields["shift"] == "Night"
    assert fields["start_engine_hours"] == "1200.5"
    assert fields["end_transmission_hours"] == "810.2"


def test_extract_activity_entries():
    raw_text = (
        "Activity Code From Time To Time Workplace Ore/Waste Loads Remarks\n"
        "101 18:00 19:30 Pit A Ore 3 Normal\n"
        "300 19:30 20:15 Pit A Waste 0 Hydraulic fault\n"
    )
    entries = extract_activity_entries(raw_text)
    assert len(entries) == 2
    assert entries[0]["activity_code_raw"] == "101"
    assert entries[0]["workplace_raw"] == "Pit A"
    assert entries[1]["activity_code_raw"] == "300"
    assert "Hydraulic fault" in entries[1]["remarks_raw"]


def test_build_checklist_payload():
    raw_text = (
        "Machine Number: LOAD-001\n"
        "Operator Name: Juan Perez\n"
        "Mine Number: MINE-01\n"
        "Permit Number: PERMIT-123\n"
        "Shift: Night\n"
        "Start Engine Hours: 1200.5\n"
        "End Engine Hours: 1212.3\n"
        "Start Transmission Hours: 800.0\n"
        "End Transmission Hours: 810.2\n"
        "Activity Code From Time To Time Workplace Ore/Waste Loads Remarks\n"
        "101 18:00 19:30 Pit A Ore 3 Normal\n"
    )
    payload = build_checklist_payload(raw_text)
    assert payload.shift == "night"
    assert payload.machine_number == "LOAD-001"
    assert payload.activity_entries[0].activity_code_raw == "101"
    assert payload.activity_entries[0].from_time_raw == "18:00"
