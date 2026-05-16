"""Tests for checklist OCR extraction and parsing."""

from backend.app.ml.ocr.pipeline import extract_page1_fields, extract_activity_entries, extract_checklist_ocr
from backend.app.services.checklist_extraction import build_checklist_payload, validate_ocr_output
from backend.app.models.schemas import OCRField, OCRHeader, OCRActivityRow, OCROutput


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
    ocr_data = extract_checklist_ocr(raw_text, "test_doc_001")
    payload = build_checklist_payload(ocr_data)
    assert payload.shift == "night"
    assert payload.machine_number == "LOAD-001"
    assert payload.activity_entries[0].activity_code_raw == "101"
    assert payload.activity_entries[0].from_time_raw == "18:00"


def test_validate_ocr_output_valid():
    ocr_data = OCROutput(
        document_id="test_doc_001",
        header=OCRHeader(
            machine_id=OCRField(value="LOAD-001", confidence=0.9),
            operator_name=OCRField(value="Juan Perez", confidence=0.85),
            date=OCRField(value="2026-04-04", confidence=0.95),
            shift=OCRField(value="night", confidence=0.8),
            engine_hours_start=OCRField(value="1200.5", confidence=0.9),
            engine_hours_end=OCRField(value="1212.3", confidence=0.9)
        ),
        activities=[
            OCRActivityRow(
                row_index=0,
                activity_code=OCRField(value="101", confidence=0.8),
                from_time=OCRField(value="18:00", confidence=0.75),
                to_time=OCRField(value="19:30", confidence=0.75),
                location=OCRField(value="Pit A", confidence=0.7),
                loads=OCRField(value="3", confidence=0.8),
                remarks=OCRField(value="Normal", confidence=0.6)
            )
        ]
    )
    # Should not raise exception
    validate_ocr_output(ocr_data)


def test_validate_ocr_output_invalid_shift():
    ocr_data = OCROutput(
        document_id="test_doc_001",
        header=OCRHeader(
            machine_id=OCRField(value="LOAD-001", confidence=0.9),
            operator_name=OCRField(value="Juan Perez", confidence=0.85),
            date=OCRField(value="2026-04-04", confidence=0.95),
            shift=OCRField(value="morning", confidence=0.8),  # Invalid shift
            engine_hours_start=OCRField(value="1200.5", confidence=0.9),
            engine_hours_end=OCRField(value="1212.3", confidence=0.9)
        ),
        activities=[]
    )
    try:
        validate_ocr_output(ocr_data)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Invalid shift value" in str(e)
