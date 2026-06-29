"""Validation engine for checklist data.

Performs strict checks on OCR-derived checklist data and returns a
validation report with errors, severities, and affected rows.

Rules implemented:
- Time format must be HH:MM
- Chronological order (start <= end)
- Required fields present (activity_code, from_time, to_time)
- Shift boundaries respected (uses SHIFT_WINDOWS from rule_engine)
- No overlapping intervals between activities

Invalid timelines must never pass silently; critical errors will be
returned in the report so callers (orchestrator) can flag for review
or attempt logged corrections.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import List, Optional, Tuple, Dict, Any

from backend.app.models.schemas import OCROutput, OCRActivityRow
from backend.app.services.rule_engine import SHIFT_WINDOWS


TIME_RE = re.compile(r"^\d{2}:\d{2}$")


@dataclass
class ValidationErrorEntry:
    message: str
    severity: str  # 'critical' | 'warning'
    affected_rows: List[int] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    errors: List[ValidationErrorEntry] = field(default_factory=list)
    corrected: List[Dict[str, Any]] = field(default_factory=list)
    needs_review: bool = False


def _parse_time_str(t: Optional[str]) -> Optional[time]:
    if not t:
        return None
    if not isinstance(t, str):
        return None
    t = t.strip()
    if not TIME_RE.match(t):
        return None
    try:
        hh, mm = map(int, t.split(":"))
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return time(hour=hh, minute=mm)
    except Exception:
        return None
    return None


def _intervals_from_activities(activities: List[OCRActivityRow]) -> List[Tuple[int, Optional[time], Optional[time]]]:
    intervals = []
    for row in activities:
        idx = row.row_index
        start = _parse_time_str(row.from_time.parsed_value or row.from_time.value)
        end = _parse_time_str(row.to_time.parsed_value or row.to_time.value)
        intervals.append((idx, start, end))
    return intervals


def _overlaps(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    # If any endpoint is None, conservatively treat as no proven overlap
    if a_start is None or a_end is None or b_start is None or b_end is None:
        return False
    # normalize comparisons
    a_s = datetime.combine(datetime.min, a_start)
    a_e = datetime.combine(datetime.min, a_end)
    b_s = datetime.combine(datetime.min, b_start)
    b_e = datetime.combine(datetime.min, b_end)
    return max(a_s, b_s) < min(a_e, b_e)


def validate_checklist(ocr_output: OCROutput) -> ValidationReport:
    """Validate an OCROutput checklist.

    Returns a ValidationReport with discovered errors. Callers must decide
    whether to halt processing based on severity.
    """
    report = ValidationReport()

    activities = ocr_output.activities or []
    if not activities:
        report.errors.append(ValidationErrorEntry(
            message="No activity rows found",
            severity="critical",
            affected_rows=[],
        ))
        report.needs_review = True
        return report

    # Check required fields and time format
    for row in activities:
        missing = []
        # activity code
        code_val = row.activity_code.parsed_value or row.activity_code.value
        if not code_val:
            missing.append("activity_code")
        # times
        from_raw = row.from_time.parsed_value or row.from_time.value
        to_raw = row.to_time.parsed_value or row.to_time.value
        start_t = _parse_time_str(from_raw)
        end_t = _parse_time_str(to_raw)
        if not start_t:
            report.errors.append(ValidationErrorEntry(
                message=f"Invalid or missing start time in row {row.row_index}",
                severity="critical",
                affected_rows=[row.row_index],
                meta={"from_time_raw": from_raw}
            ))
        if not end_t:
            report.errors.append(ValidationErrorEntry(
                message=f"Invalid or missing end time in row {row.row_index}",
                severity="critical",
                affected_rows=[row.row_index],
                meta={"to_time_raw": to_raw}
            ))
        if missing:
            report.errors.append(ValidationErrorEntry(
                message=f"Missing required fields in row {row.row_index}: {', '.join(missing)}",
                severity="critical",
                affected_rows=[row.row_index],
            ))

        # chronological order within row
        if start_t and end_t:
            s_dt = datetime.combine(datetime.min, start_t)
            e_dt = datetime.combine(datetime.min, end_t)
            if e_dt < s_dt:
                report.errors.append(ValidationErrorEntry(
                    message=f"End time earlier than start time in row {row.row_index}",
                    severity="critical",
                    affected_rows=[row.row_index],
                    meta={"from": from_raw, "to": to_raw}
                ))

    # Chronological order across rows and overlap detection
    intervals = _intervals_from_activities(activities)
    # Sort by start time for sequence checks; keep None at end
    sorted_intervals = sorted(intervals, key=lambda x: (x[1] is None, x[1] or time.min))

    # Check for non-monotonic sequence: next start should be >= previous end
    prev_idx, prev_start, prev_end = None, None, None
    for idx, start, end in sorted_intervals:
        if prev_end and start:
            p_dt = datetime.combine(datetime.min, prev_end)
            s_dt = datetime.combine(datetime.min, start)
            if s_dt < p_dt:
                report.errors.append(ValidationErrorEntry(
                    message=f"Non-chronological sequence: row {idx} starts before previous row ends",
                    severity="critical",
                    affected_rows=[prev_idx, idx],
                    meta={"prev_end": prev_end.isoformat(), "start": start.isoformat()}
                ))
        prev_idx, prev_start, prev_end = idx, start, end

    # Overlap detection (pairwise)
    n = len(intervals)
    for i in range(n):
        for j in range(i + 1, n):
            idx_i, s_i, e_i = intervals[i]
            idx_j, s_j, e_j = intervals[j]
            if _overlaps(s_i, e_i, s_j, e_j):
                report.errors.append(ValidationErrorEntry(
                    message=f"Overlapping activities between rows {idx_i} and {idx_j}",
                    severity="critical",
                    affected_rows=[idx_i, idx_j],
                    meta={"row_i": (s_i.isoformat(), e_i.isoformat()), "row_j": (s_j.isoformat(), e_j.isoformat())}
                ))

    # Shift boundary checks (if header.shift present)
    hdr_shift = (ocr_output.header.shift.parsed_value or ocr_output.header.shift.value or "").lower()
    if hdr_shift in SHIFT_WINDOWS:
        shift_start, shift_end = SHIFT_WINDOWS[hdr_shift]
        for idx, start, end in intervals:
            if start and end:
                if hdr_shift == "night":
                    # Night shift spans 18:00–06:00 (crosses midnight).
                    # Three valid cases for a non-spanning activity:
                    #   1. spans midnight (end < start on clock) — always valid
                    #   2. both times >= 18:00 (evening block)
                    #   3. both times <= 06:00 (early-morning block)
                    if end < start:
                        continue  # spans midnight, valid
                    in_evening = start >= shift_start        # >= 18:00
                    in_morning = end <= shift_end             # <= 06:00
                    if not (in_evening or in_morning):
                        report.errors.append(ValidationErrorEntry(
                            message=f"Activity in row {idx} outside night shift boundaries",
                            severity="warning",
                            affected_rows=[idx],
                            meta={"start": start.isoformat(), "end": end.isoformat(), "shift": hdr_shift}
                        ))
                else:
                    if start < shift_start or end > shift_end:
                        report.errors.append(ValidationErrorEntry(
                            message=f"Activity in row {idx} outside shift boundaries ({hdr_shift})",
                            severity="warning",
                            affected_rows=[idx],
                            meta={"start": start.isoformat(), "end": end.isoformat(), "shift": hdr_shift}
                        ))

    # Finalize
    if any(e.severity == "critical" for e in report.errors):
        report.needs_review = True

    return report


if __name__ == "__main__":
    # Demo examples for execution checks
    from backend.app.models.schemas import OCRField, OCRHeader, OCROutput

    def mk_field(val: Optional[str], conf: float = 0.8):
        return OCRField(value=val, confidence=conf, classification='medium')

    # Example 1: overlapping activities
    activities = [
        OCRActivityRow(row_index=0, activity_code=mk_field('101'), from_time=mk_field('08:00'), to_time=mk_field('09:00'), location=mk_field('Pit A'), loads=mk_field('2'), remarks=mk_field('')),
        OCRActivityRow(row_index=1, activity_code=mk_field('102'), from_time=mk_field('08:30'), to_time=mk_field('09:30'), location=mk_field('Pit B'), loads=mk_field('1'), remarks=mk_field('')),
    ]
    ocr_out = OCROutput(document_id='demo_overlap', header=OCRHeader(machine_id=mk_field('LOAD-1'), operator_name=mk_field('Op'), date=mk_field('2026-05-03'), shift=mk_field('day'), engine_hours_start=mk_field('100'), engine_hours_end=mk_field('110')), activities=activities)
    rep = validate_checklist(ocr_out)
    print("Overlap demo report:")
    for err in rep.errors:
        print(f" - {err.severity.upper()}: {err.message} rows={err.affected_rows}")

    # Example 2: invalid time sequence (end < start)
    activities2 = [
        OCRActivityRow(row_index=0, activity_code=mk_field('101'), from_time=mk_field('10:00'), to_time=mk_field('09:00'), location=mk_field('Pit A'), loads=mk_field('2'), remarks=mk_field('')),
    ]
    ocr_out2 = OCROutput(document_id='demo_invalid_seq', header=OCRHeader(machine_id=mk_field('LOAD-1'), operator_name=mk_field('Op'), date=mk_field('2026-05-03'), shift=mk_field('day'), engine_hours_start=mk_field('100'), engine_hours_end=mk_field('110')), activities=activities2)
    rep2 = validate_checklist(ocr_out2)
    print("\nInvalid sequence demo report:")
    for err in rep2.errors:
        print(f" - {err.severity.upper()}: {err.message} rows={err.affected_rows}")

    # Print report structure example
    print("\nValidationReport structure:")
    print(f" needs_review: {rep.needs_review}")
    print(f" errors: {[{'msg': e.message, 'sev': e.severity, 'rows': e.affected_rows} for e in rep.errors]}")
