"""Phase 5: End-to-end pipeline verification.

Traces the full business-logic stack without loading any ML models:

  ChecklistParser.parse_checklist()
  → postprocess_ocr_output()
  → validate_checklist()
  → integrate_ocr_with_rule_engine()  (no DB, checklist_form=None)

Verifies cross-seam correctness that unit tests cannot catch:
- Data produced by the parser is correctly consumed by postprocessing
- Data produced by postprocessing is correctly consumed by the validator
- Data produced by the validator is correctly consumed by the rule engine
- Analytics computed by the rule engine are valid and non-crashing
"""

import pytest
from datetime import date

from backend.app.services.checklist_parser import ChecklistParser
from backend.app.ml.postprocessing import postprocess_ocr_output
from backend.app.services.validator import validate_checklist
from backend.app.services.ocr_rule_engine_integration import integrate_ocr_with_rule_engine


REF_DATE = date(2026, 6, 29)


def _run_pipeline(header_blob, activity_texts, doc_id, ref_date=REF_DATE):
    """Run the full pipeline and return (ocr_output, validation_report, result)."""
    parser = ChecklistParser()
    ocr_output = parser.parse_checklist(header_blob, activity_texts, doc_id)
    ocr_output = postprocess_ocr_output(ocr_output)
    validation_report = validate_checklist(ocr_output)
    result = integrate_ocr_with_rule_engine(
        db=None,
        ocr_output=ocr_output,
        checklist_form=None,
        reference_date=ref_date,
    )
    return ocr_output, validation_report, result


# ---------------------------------------------------------------------------
# Fixtures — representative mining shift documents
# ---------------------------------------------------------------------------

DAY_HEADER = {
    "text": (
        "Machine: EX-001 Operator: John Smith 29-06-2026 Day shift "
        "Engine Hours: 100.5 Engine Hours: 108.0"
    ),
    "confidence": 0.88,
    "classification": "high",
}

# Activity rows:
# - Row 3 uses "5OO" (letter O) — OCR noise that must be normalised to "500"
# - Row 0 code "101" must NOT pollute from_time (Phase 3 fix)
DAY_ACTIVITIES = [
    "101 07:00 09:00 Pit A 4 loads ore hauling",
    "101 09:00 12:00 Pit B 6 loads ore hauling",
    "200 12:00 13:00 Workshop service inspection",
    "5OO 13:00 14:30 Workshop breakdown hydraulic fault",
    "101 14:30 18:00 Pit A 7 loads ore hauling",
]

NIGHT_HEADER = {
    "text": (
        "Machine: EX-002 Operator: Jane Doe 29-06-2026 Night shift "
        "Engine Hours: 200.0 Engine Hours: 211.5"
    ),
    "confidence": 0.85,
    "classification": "high",
}

# Row 2 crosses midnight (22:30 → 01:00).  Phase 2 fix: delta must not wrap to ~1290 min.
NIGHT_ACTIVITIES = [
    "101 19:00 21:00 Pit A 5 loads ore hauling",
    "200 21:00 22:30 Workshop service inspection daily",
    "101 22:30 01:00 Pit B 4 loads ore hauling",
    "101 01:00 06:00 Pit A 6 loads ore hauling",
]


# ---------------------------------------------------------------------------
# Day-shift end-to-end
# ---------------------------------------------------------------------------

class TestDayShiftPipeline:

    def setup_method(self):
        self.ocr, self.report, self.result = _run_pipeline(
            DAY_HEADER, DAY_ACTIVITIES, "e2e_day"
        )

    # ---- pipeline integrity ----

    def test_no_crash_and_no_analytics_error(self):
        assert self.result is not None
        assert "analytics_error" not in self.result, (
            f"Analytics computation failed: {self.result.get('analytics_error')}"
        )

    def test_five_activities_parsed(self):
        assert len(self.ocr.activities) == 5

    def test_postprocessing_metadata_applied(self):
        assert self.ocr.processing_metadata.get("postprocessing_applied") is True

    def test_shift_detected_as_day(self):
        assert self.ocr.header.shift.value == "day"

    # ---- Phase 3 fix: activity code token must not pollute from_time ----

    def test_row0_code_101_from_time_is_not_the_code(self):
        """Bug fix (Phase 3): token_candidates[0]='101' was passed to
        parse_time_tolerant, producing from_time='01:01' instead of '07:00'."""
        row = self.ocr.activities[0]
        assert row.activity_code.value == "101"
        assert row.from_time.value == "07:00", (
            f"Expected from_time='07:00', got {row.from_time.value!r}. "
            "The activity code token '101' may have been misread as from_time."
        )
        assert row.to_time.value == "09:00"

    # ---- Phase 3 fix: OCR-noisy code '5OO' must survive postprocessing ----

    def test_row3_ocr_noise_code_normalised_to_500(self):
        """Bug fix (Phase 3): validate_activity_code rejected codes > 399.
        '5OO' (OCR noise) must normalise to '500' and survive postprocessing."""
        row = self.ocr.activities[3]
        assert row.activity_code.value == "500", (
            f"Expected '500' after OCR normalisation, got {row.activity_code.value!r}. "
            "Either the code range fix or the O→0 normalisation is broken."
        )

    # ---- validator ----

    def test_validation_passes_clean_document(self):
        critical = [e for e in self.report.errors if e.severity != "warning"]
        assert not self.report.needs_review, (
            f"Unexpected critical errors: {[e.message for e in critical]}"
        )

    # ---- rule engine ----

    def test_events_produced(self):
        assert len(self.result.get("events", [])) > 0

    def test_production_events_present(self):
        counts = self.result["summary"]["event_counts"]
        assert counts["production"] >= 1

    def test_service_event_present(self):
        counts = self.result["summary"]["event_counts"]
        assert counts["service"] >= 1, (
            f"Expected ≥1 service event; counts: {counts}"
        )

    def test_breakdown_event_present(self):
        """Code 500 + 'breakdown' keyword must produce a breakdown event,
        confirming both the code-range fix and cross-layer classification."""
        counts = self.result["summary"]["event_counts"]
        assert counts["breakdown"] >= 1, (
            f"Expected ≥1 breakdown event; counts: {counts}"
        )

    # ---- analytics ----

    def test_analytics_block_present(self):
        assert self.result.get("analytics") is not None

    def test_availability_ratio_in_range(self):
        ratio = self.result["analytics"]["performance_ratios"]["availability_ratio"]
        assert ratio is not None
        assert 0.0 <= ratio <= 1.0, f"availability_ratio={ratio} is out of range"

    def test_utilization_ratio_in_range(self):
        ratio = self.result["analytics"]["performance_ratios"]["utilization_ratio"]
        assert ratio is not None
        assert 0.0 <= ratio <= 1.0, f"utilization_ratio={ratio} is out of range"

    def test_production_minutes_positive(self):
        mins = self.result["analytics"]["availability_breakdown"]["production_minutes"]
        assert mins > 0

    def test_breakdown_minutes_positive(self):
        """The 90-minute breakdown event (13:00–14:30) must accumulate in breakdown_minutes."""
        mins = self.result["analytics"]["availability_breakdown"]["breakdown_minutes"]
        assert mins > 0, "Breakdown minutes should be > 0 for the '5OO' row"

    def test_release_delay_non_negative(self):
        """Phase 2 fix: release_delay_minutes must never be stored as a negative value."""
        delay = self.result["analytics"]["availability_breakdown"].get("release_delay_minutes")
        if delay is not None:
            assert delay >= 0.0, f"release_delay_minutes={delay} is negative"

    def test_total_shift_minutes_positive(self):
        total = self.result["analytics"]["availability_breakdown"]["total_shift_minutes"]
        assert total is not None and total > 0


# ---------------------------------------------------------------------------
# Night-shift end-to-end
# ---------------------------------------------------------------------------

class TestNightShiftPipeline:

    def setup_method(self):
        self.ocr, self.report, self.result = _run_pipeline(
            NIGHT_HEADER, NIGHT_ACTIVITIES, "e2e_night"
        )

    def test_no_crash_and_no_analytics_error(self):
        assert self.result is not None
        assert "analytics_error" not in self.result

    def test_shift_detected_as_night(self):
        assert self.ocr.header.shift.value == "night"

    def test_four_activities_parsed(self):
        assert len(self.ocr.activities) == 4

    def test_row0_code_101_from_time_not_polluted(self):
        """Phase 3 fix: same time-token bug must not affect night-shift rows."""
        row = self.ocr.activities[0]
        assert row.activity_code.value == "101"
        assert row.from_time.value == "19:00", (
            f"Expected from_time='19:00', got {row.from_time.value!r}"
        )

    def test_events_produced(self):
        assert len(self.result.get("events", [])) > 0

    def test_no_event_duration_exceeds_shift_window(self):
        """Phase 2 fix: _time_delta_minutes for night shift must not wrap midnight.
        A midnight-crossing event (22:30→01:00 = 150 min) must not appear as
        ~1290 min (24h - 150 min = wrong wrap direction)."""
        for event in self.result.get("events", []):
            duration = event.get("duration_minutes")
            if duration is not None:
                assert duration <= 720, (
                    f"Event {event.get('start_time')}–{event.get('end_time')} "
                    f"has duration {duration:.0f} min — exceeds 12-hour shift. "
                    "Midnight-wrap bug may still be present."
                )
                assert duration >= 0, (
                    f"Negative duration {duration:.0f} min for event "
                    f"{event.get('start_time')}–{event.get('end_time')}"
                )

    def test_analytics_computed(self):
        assert self.result.get("analytics") is not None

    def test_night_analytics_ratios_in_range(self):
        ratios = self.result["analytics"]["performance_ratios"]
        for name, value in ratios.items():
            if value is not None:
                assert 0.0 <= value <= 1.0, (
                    f"Night-shift ratio {name}={value} is out of [0, 1]"
                )


# ---------------------------------------------------------------------------
# Cross-seam: postprocessing → validator
# ---------------------------------------------------------------------------

class TestPostprocessingValidatorSeam:

    def test_ocr_noise_in_times_corrected_before_validation(self):
        """OCR noise in time fields ('09:3O', '10:OO') must be corrected by the
        parser so the validator sees valid HH:MM strings, not the raw OCR text."""
        header = {
            "text": "Machine: EX-003 Operator: Test Day shift Engine Hours: 50.0 Engine Hours: 56.0",
            "confidence": 0.85,
            "classification": "high",
        }
        activities = ["101 09:3O 10:OO Pit A 2 loads ore hauling"]
        ocr, report, _ = _run_pipeline(header, activities, "noise_time_test")
        time_format_errors = [
            e for e in report.errors
            if "time" in e.message.lower() and "invalid" in e.message.lower()
        ]
        assert len(time_format_errors) == 0, (
            f"OCR-corrected times produced format errors: "
            f"{[e.message for e in time_format_errors]}"
        )


# ---------------------------------------------------------------------------
# Cross-seam: Phase 3 code-range fix → rule engine
# ---------------------------------------------------------------------------

class TestCodeRangeFixReachesRuleEngine:

    def test_code_600_delay_survives_postprocessing_and_reaches_rule_engine(self):
        """Phase 3 fix: validate_activity_code previously rejected codes > 399.
        Code 600 (delay) must now survive postprocessing and be visible to the
        rule engine as activity_code='600'."""
        header = {
            "text": "Machine: EX-004 Operator: Test Day shift",
            "confidence": 0.85,
            "classification": "high",
        }
        activities = ["600 10:00 11:00 Standby waiting delay queue"]
        ocr, _, result = _run_pipeline(header, activities, "code600_test")
        assert ocr.activities[0].activity_code.value == "600", (
            "Code 600 should survive postprocessing. Was it rejected by validate_activity_code?"
        )
        assert "analytics_error" not in result
        events = result.get("events", [])
        assert any(e.get("activity_code") == "600" for e in events), (
            "Code 600 event should appear in rule engine output"
        )

    def test_code_400_maintenance_survives_postprocessing_and_reaches_rule_engine(self):
        """Phase 3 fix: code 400 (maintenance) was also rejected before the fix."""
        header = {
            "text": "Machine: EX-005 Operator: Test Day shift",
            "confidence": 0.85,
            "classification": "high",
        }
        activities = ["400 08:00 10:00 Workshop maintenance service repair"]
        ocr, _, result = _run_pipeline(header, activities, "code400_test")
        assert ocr.activities[0].activity_code.value == "400", (
            "Code 400 should survive postprocessing"
        )
        assert "analytics_error" not in result
        events = result.get("events", [])
        assert any(e.get("activity_code") == "400" for e in events)

    def test_ocr_confused_breakdown_code_5oo_reaches_rule_engine_as_500(self):
        """OCR noise '5OO' must be normalised to '500' and reach the rule engine
        as activity_code='500', confirming parser→postprocessor→rule-engine seam."""
        header = {
            "text": "Machine: EX-006 Operator: Test Day shift",
            "confidence": 0.85,
            "classification": "high",
        }
        activities = ["5OO 11:00 13:00 Workshop breakdown hydraulic fault"]
        ocr, _, result = _run_pipeline(header, activities, "5oo_test")
        assert ocr.activities[0].activity_code.value == "500"
        events = result.get("events", [])
        assert any(e.get("activity_code") == "500" for e in events), (
            "Normalised code '500' must reach the rule engine"
        )
        breakdown_events = [e for e in events if e.get("event_type") == "breakdown"]
        assert len(breakdown_events) >= 1, (
            f"Code 500 + 'breakdown' keyword should produce a breakdown event; "
            f"event_types seen: {[e.get('event_type') for e in events]}"
        )
