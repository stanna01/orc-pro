"""Tests for OCR post-processing layer (postprocessing.py).

Covers:
- validate_activity_code: full range 100-699, OCR-confused inputs, out-of-range rejection
- postprocess_ocr_field: confidence=None crash fix (Bug 1), breakdown/delay code pass-through (Bug 3)
- postprocess_ocr_output: average confidence with mixed None/float fields (Bug 2)
- normalize_time_format: messy OCR time strings
- correct_vocabulary: mining-specific vocabulary correction
"""

import pytest
from backend.app.models.schemas import OCRField, OCRHeader, OCRActivityRow, OCROutput
from backend.app.ml.postprocessing import (
    validate_activity_code,
    postprocess_ocr_field,
    postprocess_ocr_output,
    normalize_time_format,
    correct_vocabulary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _field(val, conf=0.8):
    return OCRField(value=val, confidence=conf)


def _make_ocr(activities, header_conf=0.9):
    return OCROutput(
        document_id="pp_test",
        header=OCRHeader(
            machine_id=_field("M1", header_conf),
            operator_name=_field("Op", header_conf),
            date=_field("2026-06-01", header_conf),
            shift=_field("day", header_conf),
            engine_hours_start=_field("100", header_conf),
            engine_hours_end=_field("112", header_conf),
        ),
        activities=activities,
    )


# ---------------------------------------------------------------------------
# validate_activity_code
# ---------------------------------------------------------------------------

class TestValidateActivityCode:

    def test_production_codes_accepted(self):
        for code in ["101", "102", "103"]:
            valid, normalized = validate_activity_code(code)
            assert valid, f"Expected {code} to be valid"
            assert normalized == code

    def test_service_codes_accepted(self):
        for code in ["200", "201", "300"]:
            valid, normalized = validate_activity_code(code)
            assert valid, f"Expected {code} to be valid"

    def test_maintenance_code_400_accepted(self):
        valid, normalized = validate_activity_code("400")
        assert valid
        assert normalized == "400"

    def test_breakdown_code_500_accepted(self):
        valid, normalized = validate_activity_code("500")
        assert valid
        assert normalized == "500"

    def test_delay_code_600_accepted(self):
        valid, normalized = validate_activity_code("600")
        assert valid
        assert normalized == "600"

    def test_code_700_rejected(self):
        valid, _ = validate_activity_code("700")
        assert not valid

    def test_code_099_rejected(self):
        valid, _ = validate_activity_code("099")
        assert not valid

    def test_code_000_rejected(self):
        valid, _ = validate_activity_code("000")
        assert not valid

    def test_empty_code_rejected(self):
        valid, _ = validate_activity_code("")
        assert not valid

    def test_ocr_confused_production_code(self):
        """'lO1' with OCR misreads should normalize to '101'."""
        valid, normalized = validate_activity_code("lO1")
        assert valid
        assert normalized == "101"

    def test_ocr_confused_breakdown_code(self):
        """'5OO' should normalize to '500' (breakdown)."""
        valid, normalized = validate_activity_code("5OO")
        assert valid
        assert normalized == "500"

    def test_normalized_code_zero_padded(self):
        valid, normalized = validate_activity_code("101")
        assert normalized == "101"


# ---------------------------------------------------------------------------
# postprocess_ocr_field — confidence=None crash fix
# ---------------------------------------------------------------------------

class TestPostprocessOcrFieldNoneConfidence:

    def test_none_confidence_time_field_does_not_crash(self):
        """Bug fix: field.confidence=None caused TypeError on addition."""
        field = OCRField(value="14:3O", confidence=None)
        result = postprocess_ocr_field(field, "time")
        assert result.value == "14:30"
        assert result.confidence == pytest.approx(0.2, abs=1e-6)

    def test_none_confidence_code_field_does_not_crash(self):
        field = OCRField(value="5OO", confidence=None)
        result = postprocess_ocr_field(field, "code")
        assert isinstance(result.confidence, float)

    def test_none_confidence_text_field_does_not_crash(self):
        field = OCRField(value="loador", confidence=None)
        result = postprocess_ocr_field(field, "text")
        assert isinstance(result.confidence, float)

    def test_none_confidence_numeric_field_does_not_crash(self):
        field = OCRField(value="1OO", confidence=None)
        result = postprocess_ocr_field(field, "numeric")
        assert isinstance(result.confidence, float)

    def test_time_correction_with_real_confidence(self):
        field = OCRField(value="14:3O", confidence=0.5)
        result = postprocess_ocr_field(field, "time")
        assert result.value == "14:30"
        assert result.confidence == pytest.approx(0.7, abs=1e-6)

    def test_confidence_capped_at_1(self):
        field = OCRField(value="14:3O", confidence=0.95)
        result = postprocess_ocr_field(field, "time")
        assert result.confidence <= 1.0

    def test_empty_value_returned_unchanged(self):
        field = OCRField(value=None, confidence=0.5)
        result = postprocess_ocr_field(field, "time")
        assert result.value is None


# ---------------------------------------------------------------------------
# postprocess_ocr_field — breakdown/maintenance/delay code pass-through
# ---------------------------------------------------------------------------

class TestPostprocessOcrFieldHighCodes:

    def test_breakdown_code_500_passes_through(self):
        """Code 500 was previously rejected (range was 100-399)."""
        field = OCRField(value="500", confidence=0.8)
        result = postprocess_ocr_field(field, "code")
        assert result.value == "500"

    def test_maintenance_code_400_passes_through(self):
        field = OCRField(value="400", confidence=0.8)
        result = postprocess_ocr_field(field, "code")
        assert result.value == "400"

    def test_delay_code_600_passes_through(self):
        field = OCRField(value="600", confidence=0.8)
        result = postprocess_ocr_field(field, "code")
        assert result.value == "600"

    def test_code_700_not_normalized(self):
        """700 is out of range — value should revert to original."""
        field = OCRField(value="700", confidence=0.8)
        result = postprocess_ocr_field(field, "code")
        assert result.value == "700"


# ---------------------------------------------------------------------------
# postprocess_ocr_output — average confidence with None fields
# ---------------------------------------------------------------------------

class TestPostprocessOcrOutputConfidence:

    def test_all_none_confidence_does_not_crash(self):
        """Bug fix: sum(f.confidence...) crashed with TypeError for None confidence."""
        ocr = _make_ocr(
            activities=[
                OCRActivityRow(
                    row_index=0,
                    activity_code=OCRField(value="101", confidence=None),
                    from_time=OCRField(value="08:00", confidence=None),
                    to_time=OCRField(value="09:00", confidence=None),
                    location=OCRField(value="Pit A", confidence=None),
                    loads=OCRField(value="2", confidence=None),
                    remarks=OCRField(value="ok", confidence=None),
                )
            ],
            header_conf=None,
        )
        result = postprocess_ocr_output(ocr)
        assert "postprocessing_avg_confidence" in result.processing_metadata
        assert isinstance(result.processing_metadata["postprocessing_avg_confidence"], float)

    def test_mixed_none_and_float_does_not_crash(self):
        ocr = _make_ocr(
            activities=[
                OCRActivityRow(
                    row_index=0,
                    activity_code=OCRField(value="101", confidence=0.8),
                    from_time=OCRField(value="08:00", confidence=None),
                    to_time=OCRField(value="09:00", confidence=0.7),
                    location=OCRField(value="Pit A", confidence=None),
                    loads=OCRField(value="2", confidence=0.9),
                    remarks=OCRField(value="ok", confidence=0.6),
                )
            ]
        )
        result = postprocess_ocr_output(ocr)
        assert isinstance(result.processing_metadata["postprocessing_avg_confidence"], float)

    def test_postprocessing_metadata_flags_set(self):
        ocr = _make_ocr(activities=[])
        result = postprocess_ocr_output(ocr)
        meta = result.processing_metadata
        assert meta["postprocessing_applied"] is True
        assert meta["character_corrections"] is True
        assert meta["time_normalization"] is True
        assert meta["code_validation"] is True

    def test_activities_are_preserved(self):
        ocr = _make_ocr(
            activities=[
                OCRActivityRow(
                    row_index=0,
                    activity_code=OCRField(value="500", confidence=0.8),
                    from_time=OCRField(value="08:00", confidence=0.8),
                    to_time=OCRField(value="09:00", confidence=0.8),
                    location=OCRField(value="Pit A", confidence=0.8),
                    loads=OCRField(value="2", confidence=0.8),
                    remarks=OCRField(value="", confidence=0.8),
                )
            ]
        )
        result = postprocess_ocr_output(ocr)
        assert len(result.activities) == 1
        assert result.activities[0].activity_code.value == "500"


# ---------------------------------------------------------------------------
# normalize_time_format
# ---------------------------------------------------------------------------

class TestNormalizeTimeFormat:

    def test_ocr_letter_o_in_minutes(self):
        assert normalize_time_format("14:3O") == "14:30"

    def test_four_digit_no_colon(self):
        assert normalize_time_format("1430") == "14:30"

    def test_pm_conversion(self):
        assert normalize_time_format("2:30pm") == "14:30"

    def test_single_digit_hour_padded(self):
        assert normalize_time_format("9:05") == "09:05"

    def test_midnight_am(self):
        assert normalize_time_format("12:00am") == "00:00"

    def test_invalid_returns_none(self):
        assert normalize_time_format("invalid") is None

    def test_empty_returns_none(self):
        assert normalize_time_format("") is None


# ---------------------------------------------------------------------------
# correct_vocabulary
# ---------------------------------------------------------------------------

class TestCorrectVocabulary:

    def test_loader_misspelling_corrected(self):
        assert correct_vocabulary("loador") == "loader"

    def test_waste_dump_compact_corrected(self):
        assert correct_vocabulary("wastedump") == "waste dump"

    def test_safety_meeting_compact_corrected(self):
        assert correct_vocabulary("safetymeeting") == "safety meeting"

    def test_unknown_word_preserved(self):
        assert correct_vocabulary("unknownterm") == "unknownterm"

    def test_empty_string_returned_as_is(self):
        assert correct_vocabulary("") == ""
