"""Tests for checklist_parser.py — tolerant OCR text parsing.

Covers:
- parse_header plain-string path: now returns values instead of all-None (Bug 5 fix)
- parse_header dict path: low confidence suppresses values, high confidence includes them
- parse_activity_row: activity code token no longer misread as from_time (Bug 4 fix)
- parse_activity_row: breakdown/delay codes (500, 600) extracted correctly
- parse_time_tolerant: various messy OCR time strings
- parse_code_tolerant: digit extraction and normalization
"""

import pytest
from backend.app.services.checklist_parser import (
    ChecklistParser,
    parse_time_tolerant,
    parse_code_tolerant,
)


# ---------------------------------------------------------------------------
# parse_header — plain string path (bug fix: row_conf was 0.0, now None)
# ---------------------------------------------------------------------------

class TestParseHeaderPlainString:

    def setup_method(self):
        self.parser = ChecklistParser()

    def test_night_shift_detected(self):
        """Fix: plain-string row_conf=0.0 made conf_ok=False, suppressing all values."""
        header = self.parser.parse_header("Operator: John Night shift Machine: EX100")
        assert header.shift.value == "night"

    def test_day_shift_detected(self):
        header = self.parser.parse_header("Operator: Jane Day shift Machine: EX200")
        assert header.shift.value == "day"

    def test_machine_id_extracted(self):
        header = self.parser.parse_header("Machine: EX300 Operator: Mary Day shift")
        assert header.machine_id.value == "EX300"

    def test_operator_name_extracted(self):
        header = self.parser.parse_header("Operator: Alice Day shift Machine: BUL-01")
        assert header.operator_name.value is not None
        assert "Alice" in header.operator_name.value

    def test_date_field_populated(self):
        """No date in text → fallback to today's date (not None)."""
        header = self.parser.parse_header("Operator: Bob Night shift Machine: EX001")
        assert header.date.value is not None

    def test_engine_hours_extracted_when_present(self):
        header = self.parser.parse_header(
            "Operator: Sam Day shift Machine: EX001 Engine Hours: 100.5 Engine Hours: 112.0"
        )
        assert header.engine_hours_start.value == "100.5"


# ---------------------------------------------------------------------------
# parse_header — dict input confidence guards
# ---------------------------------------------------------------------------

class TestParseHeaderDictInput:

    def setup_method(self):
        self.parser = ChecklistParser()

    def test_high_confidence_returns_values(self):
        raw = {
            "text": "Machine: LOAD-01 Operator: Tom Day shift",
            "confidence": 0.85,
            "classification": "high",
        }
        header = self.parser.parse_header(raw)
        assert header.machine_id.value == "LOAD-01"

    def test_boundary_confidence_0_7_returns_values(self):
        raw = {
            "text": "Machine: LOAD-02 Operator: Sue Day shift",
            "confidence": 0.7,
            "classification": "medium",
        }
        header = self.parser.parse_header(raw)
        assert header.machine_id.value == "LOAD-02"

    def test_low_confidence_suppresses_values(self):
        """Confidence below 0.7 must suppress machine_id, operator_name, date, shift."""
        raw = {
            "text": "Machine: LOAD-01 Operator: Tom Day shift",
            "confidence": 0.5,
            "classification": "low",
        }
        header = self.parser.parse_header(raw)
        assert header.machine_id.value is None
        assert header.operator_name.value is None
        assert header.shift.value is None

    def test_none_confidence_returns_values(self):
        """None confidence (unknown) should not suppress values."""
        raw = {
            "text": "Machine: LOAD-03 Operator: Kim Day shift",
            "confidence": None,
            "classification": "unknown",
        }
        header = self.parser.parse_header(raw)
        assert header.shift.value is not None


# ---------------------------------------------------------------------------
# parse_activity_row — activity code not misread as from_time (bug fix)
# ---------------------------------------------------------------------------

class TestParseActivityRowTimeFix:

    def setup_method(self):
        self.parser = ChecklistParser()
        self.standard_row = {
            "text": "101 08:30 09:00 PitA 3 loads",
            "confidence": 0.8,
            "classification": "high",
        }

    def test_from_time_not_derived_from_activity_code(self):
        """Bug: token_candidates[0]='101' was passed to parse_time_tolerant,
        producing from_time='01:01'. Fix: time_candidates excludes the code token."""
        row = self.parser.parse_activity_row(self.standard_row, row_index=0)
        assert row.from_time.value == "08:30", (
            f"from_time should be '08:30', got {row.from_time.value!r}"
        )

    def test_to_time_correctly_extracted(self):
        row = self.parser.parse_activity_row(self.standard_row, row_index=0)
        assert row.to_time.value == "09:00", (
            f"to_time should be '09:00', got {row.to_time.value!r}"
        )

    def test_activity_code_correctly_extracted(self):
        row = self.parser.parse_activity_row(self.standard_row, row_index=0)
        assert row.activity_code.value == "101"

    def test_row_index_preserved(self):
        row = self.parser.parse_activity_row(self.standard_row, row_index=7)
        assert row.row_index == 7

    def test_breakdown_code_500_extracted(self):
        """Code 500 (breakdown) must reach OCRActivityRow unchanged."""
        row = self.parser.parse_activity_row(
            {"text": "500 14:00 15:30 Workshop", "confidence": 0.8, "classification": "high"},
            row_index=0,
        )
        assert row.activity_code.value == "500"

    def test_delay_code_600_extracted(self):
        row = self.parser.parse_activity_row(
            {"text": "600 10:00 10:45 Standby", "confidence": 0.8, "classification": "high"},
            row_index=0,
        )
        assert row.activity_code.value == "600"

    def test_plain_string_row_does_not_crash(self):
        """parse_activity_row also accepts plain strings (non-dict)."""
        row = self.parser.parse_activity_row("101 08:00 09:00 Pit A", row_index=0)
        assert row.row_index == 0


# ---------------------------------------------------------------------------
# parse_time_tolerant
# ---------------------------------------------------------------------------

class TestParseTimeTolerant:

    def test_standard_hh_mm(self):
        r = parse_time_tolerant("08:30")
        assert r["valid"] is True
        assert r["parsed"] == "08:30"
        assert r["score"] >= 0.9

    def test_four_digit_no_colon(self):
        r = parse_time_tolerant("0830")
        assert r["valid"] is True
        assert r["parsed"] == "08:30"

    def test_three_digit(self):
        r = parse_time_tolerant("830")
        assert r["valid"] is True
        assert r["parsed"] == "08:30"

    def test_single_digit_hour(self):
        r = parse_time_tolerant("8")
        assert r["valid"] is True
        assert r["parsed"] == "08:00"

    def test_garbage_returns_invalid(self):
        r = parse_time_tolerant("XYZ")
        assert r["valid"] is False
        assert r["parsed"] is None

    def test_empty_returns_invalid(self):
        r = parse_time_tolerant("")
        assert r["valid"] is False

    def test_activity_code_101_parses_as_time(self):
        """Confirms the bug was real: '101' does parse as a valid time ('01:01'),
        which is why the time_candidates filter fix was essential."""
        r = parse_time_tolerant("101")
        assert r["valid"] is True  # it IS valid — but it belongs to the code column

    def test_end_of_shift_time(self):
        r = parse_time_tolerant("18:00")
        assert r["valid"] is True
        assert r["parsed"] == "18:00"


# ---------------------------------------------------------------------------
# parse_code_tolerant
# ---------------------------------------------------------------------------

class TestParseCodeTolerant:

    def setup_method(self):
        self.known = ["101", "102", "200", "300", "400", "500", "600"]

    def test_exact_code_returned(self):
        r = parse_code_tolerant("101", self.known)
        assert r["valid"] is True
        assert r["parsed"] == "101"

    def test_ocr_confused_code_normalized(self):
        """'lO1' normalizes to digits '101'."""
        r = parse_code_tolerant("lO1", self.known)
        assert r["valid"] is True
        assert r["parsed"] == "101"

    def test_breakdown_code_extracted(self):
        r = parse_code_tolerant("500", self.known)
        assert r["valid"] is True
        assert r["parsed"] == "500"

    def test_delay_code_extracted(self):
        r = parse_code_tolerant("600", self.known)
        assert r["valid"] is True
        assert r["parsed"] == "600"

    def test_garbage_returns_invalid(self):
        r = parse_code_tolerant("???", self.known)
        assert r["valid"] is False

    def test_empty_returns_invalid(self):
        r = parse_code_tolerant("", self.known)
        assert r["valid"] is False
