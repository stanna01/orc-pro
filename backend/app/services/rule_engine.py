"""Rule engine for OCR checklist timeline processing.

This module converts OCR-extracted checklist data into a structured timeline of
mining events, infers missing end times, detects safety and shift events, and
computes idle gaps inside day/night shifts.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class EventType(str, Enum):
    PRODUCTION = "production"
    BREAKDOWN = "breakdown"
    SERVICE = "service"
    SAFETY_MEETING = "safety_meeting"
    DELAY = "delay"
    IDLE = "idle"

FieldValue = Dict[str, Any]
ActivityRow = Dict[str, Any]
OCRChecklist = Dict[str, Any]

SHIFT_WINDOWS = {
    "day": (time(hour=6, minute=0), time(hour=18, minute=0)),
    "night": (time(hour=18, minute=0), time(hour=6, minute=0)),
}

BREAKDOWN_KEYWORDS = [
    r"breakdown",
    r"hydraulic",
    r"fault",
    r"stuck",
    r"repair",
    r"engine failure",
    r"trouble",
    r"not moving",
]

# Expanded mining-specific terms
BREAKDOWN_KEYWORDS += [
    r"bogged", r"winch", r"blocked", r"jammed", r"seized", r"overheated",
    r"engine fire", r"transmission failure", r"stall",
]

SAFETY_KEYWORDS = [
    r"safety meeting",
    r"safety briefing",
    r"toolbox talk",
    r"pre-shift meeting",
    r"safety talk",
]

SAFETY_KEYWORDS += [r"evacuation", r"first aid", r"incident", r"near miss"]

SERVICE_KEYWORDS = [
    r"daily service",
    r"service",
    r"maintenance",
    r"check",
    r"inspection",
]

SERVICE_KEYWORDS += [r"grease", r"lubrication", r"refuel", r"scheduled maintenance", r"unscheduled maintenance"]

DELAY_KEYWORDS = [
    r"delay",
    r"waiting",
    r"queue",
    r"standby",
    r"hold",
    r"break",
]

DELAY_KEYWORDS += [r"waiting on truck", r"waiting for service", r"blocked by", r"traffic", r"haul road"]

MINING_OPS_KEYWORDS = [r"loading", r"dumping", r"hauling", r"shovel", r"bench", r"blast", r"blast hole", r"drill"]

SHIFT_CHANGE_KEYWORDS = [
    r"shift change",
    r"handover",
    r"shift handover",
    r"shift changeover",
]


@dataclass
class TimelineEvent:
    row_index: Optional[int]
    activity_code: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    duration_minutes: Optional[float]
    location: Optional[str]
    loads: Optional[str]
    remarks: Optional[str]
    event_type: str
    is_inferred_end_time: bool = False
    is_ambiguous: bool = False
    inference_reasons: List[str] = field(default_factory=list)
    is_change_of_shift: bool = False
    is_safety_meeting: bool = False
    is_daily_service: bool = False
    is_breakdown: bool = False
    is_delay: bool = False
    is_idle: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_index": self.row_index,
            "activity_code": self.activity_code,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_minutes": self.duration_minutes,
            "location": self.location,
            "loads": self.loads,
            "remarks": self.remarks,
            "event_type": self.event_type,
            "is_inferred_end_time": self.is_inferred_end_time,
            "is_ambiguous": self.is_ambiguous,
            "inference_reasons": self.inference_reasons,
            "is_change_of_shift": self.is_change_of_shift,
            "is_safety_meeting": self.is_safety_meeting,
            "is_daily_service": self.is_daily_service,
            "is_breakdown": self.is_breakdown,
            "is_delay": self.is_delay,
            "is_idle": self.is_idle,
        }


@dataclass
class IdleGap:
    start_time: str
    end_time: str
    duration_minutes: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_minutes": self.duration_minutes,
        }


def _get_value(field: Optional[FieldValue]) -> Optional[str]:
    if not field:
        return None
    raw = field.get("value")
    if raw is None:
        return None
    return str(raw).strip() if str(raw).strip() else None


def _normalize_shift(shift_value: Optional[str], activities: List[ActivityRow]) -> str:
    if shift_value:
        value = shift_value.strip().lower()
        if value in ("day", "night"):
            return value
        if "night" in value:
            return "night"
        if "day" in value:
            return "day"
    for activity in activities:
        from_time = _get_value(activity.get("from_time"))
        if from_time:
            parsed = _parse_time_string(from_time)
            if parsed and (parsed.hour >= 18 or parsed.hour < 6):
                return "night"
    return "day"


def _parse_time_string(value: Optional[str]) -> Optional[time]:
    if not value:
        return None
    raw = value.strip().lower().replace(".", ":").replace(" ", "")
    patterns = [r"^(2[0-3]|[01]?[0-9]):([0-5][0-9])$", r"^(1[0-2]|0?[1-9])([0-5][0-9])?(am|pm)$"]
    for pattern in patterns:
        match = re.match(pattern, raw)
        if not match:
            continue
        if "am" in raw or "pm" in raw:
            hour = int(match.group(1))
            minute = int(match.group(2) or "00")
            suffix = raw[-2:]
            if suffix == "pm" and hour != 12:
                hour += 12
            if suffix == "am" and hour == 12:
                hour = 0
            return time(hour=hour, minute=minute)
        hour = int(match.group(1))
        minute = int(match.group(2))
        return time(hour=hour, minute=minute)
    return None


def _anchor_datetime(event_time: time, shift: str, reference_date: date) -> datetime:
    start_time, end_time = SHIFT_WINDOWS[shift]
    if shift == "night":
        if event_time >= start_time:
            return datetime.combine(reference_date, event_time)
        return datetime.combine(reference_date + timedelta(days=1), event_time)
    return datetime.combine(reference_date, event_time)


def _compute_shift_window(shift: str, reference_date: Optional[date] = None) -> Tuple[datetime, datetime]:
    if reference_date is None:
        reference_date = date.today()
    start_time, end_time = SHIFT_WINDOWS[shift]
    start_dt = datetime.combine(reference_date, start_time)
    if shift == "night":
        end_dt = datetime.combine(reference_date + timedelta(days=1), end_time)
    else:
        end_dt = datetime.combine(reference_date, end_time)
    return start_dt, end_dt


def _standardize_activity_row(raw_row: ActivityRow) -> ActivityRow:
    return {
        "row_index": raw_row.get("row_index"),
        "activity_code": _get_value(raw_row.get("activity_code")),
        "from_time": _get_value(raw_row.get("from_time")),
        "to_time": _get_value(raw_row.get("to_time")),
        "location": _get_value(raw_row.get("location")),
        "loads": _get_value(raw_row.get("loads")),
        "remarks": _get_value(raw_row.get("remarks")),
    }


def _infer_end_times(activities: List[ActivityRow], shift: str, reference_date: Optional[date] = None) -> List[ActivityRow]:
    if reference_date is None:
        reference_date = date.today()
    start_dt, end_dt = _compute_shift_window(shift, reference_date)
    parsed_rows: List[Dict[str, Any]] = []

    for row in activities:
        from_t = _parse_time_string(row.get("from_time"))
        to_t = _parse_time_string(row.get("to_time"))
        parsed_rows.append({
            **row,
            "_from_dt": _anchor_datetime(from_t, shift, reference_date) if from_t else None,
            "_to_dt": _anchor_datetime(to_t, shift, reference_date) if to_t else None,
        })

    for index, row in enumerate(parsed_rows):
        if row["_to_dt"] is None and row["_from_dt"] is not None:
            next_row = parsed_rows[index + 1] if index + 1 < len(parsed_rows) else None
            # Prefer next event's start if it is strictly after this start
            if next_row and next_row.get("_from_dt"):
                candidate_end = next_row["_from_dt"]
                if candidate_end > row["_from_dt"]:
                    row["_to_dt"] = candidate_end
                    row["inferred_to_time"] = True
                    row["inference_reason"] = "inferred_from_next_event"
                else:
                    # Candidate end not after start -> ambiguous or invalid wrap
                    # For night shifts allow wrap if candidate is logically next day and within shift window
                    if shift == "night":
                        wrapped = candidate_end
                        if wrapped <= row["_from_dt"]:
                            wrapped = candidate_end + timedelta(days=1)
                        if wrapped > row["_from_dt"] and wrapped <= end_dt:
                            row["_to_dt"] = wrapped
                            row["inferred_to_time"] = True
                            row["inference_reason"] = "inferred_from_next_event_wrapped"
                        else:
                            row["inference_reason"] = "ambiguous_next_event"
                            row["ambiguous"] = True
                    else:
                        row["inference_reason"] = "ambiguous_next_event"
                        row["ambiguous"] = True
            elif row["_from_dt"] < end_dt:
                # No next event — use shift end as fallback
                row["_to_dt"] = end_dt
                row["inferred_to_time"] = True
                row["inference_reason"] = "inferred_from_shift_end"
            else:
                row["inference_reason"] = "missing_end_time"
                row["ambiguous"] = True

    # Post-process: ensure no negative durations; attempt safe wrap for night shift
    for row in parsed_rows:
        f = row.get("_from_dt")
        t = row.get("_to_dt")
        if f and t:
            if t <= f:
                # Try one-day wrap only for night shift
                if shift == "night":
                    wrapped = t + timedelta(days=1)
                    if wrapped > f and wrapped - f <= (end_dt - start_dt):
                        row["_to_dt"] = wrapped
                        row["inference_reason"] = (row.get("inference_reason") or "") + ";wrapped_midnight"
                        row["inferred_to_time"] = True
                    else:
                        row["ambiguous"] = True
                        row["inference_reason"] = (row.get("inference_reason") or "") + ";negative_duration_rejected"
                else:
                    row["ambiguous"] = True
                    row["inference_reason"] = (row.get("inference_reason") or "") + ";negative_duration_rejected"

    return [{
        "row_index": row.get("row_index"),
        "activity_code": row.get("activity_code"),
        "from_time": row.get("from_time"),
        "to_time": row.get("to_time") or (row.get("_to_dt").strftime("%H:%M") if row.get("_to_dt") else None),
        "location": row.get("location"),
        "loads": row.get("loads"),
        "remarks": row.get("remarks"),
        "_from_dt": row.get("_from_dt"),
        "_to_dt": row.get("_to_dt"),
        "is_inferred_end_time": bool(row.get("inferred_to_time")),
        "is_ambiguous": bool(row.get("ambiguous")),
        "inference_reasons": [row.get("inference_reason")] if row.get("inference_reason") else [],
    } for row in parsed_rows]


def _is_match(text: Optional[str], patterns: List[str]) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(re.search(pattern, lower) for pattern in patterns)


def _classify_event(raw_row: ActivityRow) -> Tuple[str, bool, List[str]]:
    """Context-aware classification.

    Returns (classification, is_ambiguous, reasons).
    Classification chosen by scoring multiple signals (remarks keywords,
    activity_code patterns, duration, and mining-ops hints). If no strong
    signal exists, event is marked ambiguous rather than defaulting to
    production.
    """
    remarks = (raw_row.get("remarks") or "")
    activity_code = (raw_row.get("activity_code") or "")
    reasons: List[str] = []

    # Compute duration if available
    duration_minutes = None
    if raw_row.get("_from_dt") and raw_row.get("_to_dt"):
        duration_minutes = (raw_row["_to_dt"] - raw_row["_from_dt"]).total_seconds() / 60.0
    # Signals
    scores = {
        "breakdown": 0.0,
        "service": 0.0,
        "delay": 0.0,
        "safety_meeting": 0.0,
        "idle": 0.0,
        "production": 0.0,
    }

    # Remark keyword matches are strong signals
    if _is_match(remarks, BREAKDOWN_KEYWORDS):
        scores["breakdown"] += 0.7
        reasons.append("remark_breakdown")
    if _is_match(remarks, SERVICE_KEYWORDS):
        scores["service"] += 0.7
        reasons.append("remark_service")
    if _is_match(remarks, DELAY_KEYWORDS):
        scores["delay"] += 0.6
        reasons.append("remark_delay")
    if _is_match(remarks, SAFETY_KEYWORDS):
        scores["safety_meeting"] += 0.8
        reasons.append("remark_safety")

    # Mining ops suggests production unless overridden
    if _is_match(remarks, MINING_OPS_KEYWORDS) or _is_match(activity_code, [r"1\d{2}"]):
        scores["production"] += 0.5
        reasons.append("mining_ops_hint")

    # Activity code patterns
    if re.match(r"^3\d{2,}$", activity_code):
        scores["breakdown"] += 0.6
        reasons.append("code_breakdown")
    if re.match(r"^2\d{2,}$", activity_code):
        scores["service"] += 0.5
        reasons.append("code_service")

    # Duration-based heuristics
    if duration_minutes is not None:
        if duration_minutes >= 120:
            # long events often point to breakdowns or extensive service
            scores["breakdown"] += 0.3
            scores["service"] += 0.2
            reasons.append("long_duration_hint")
        elif duration_minutes <= 5:
            # very short events likely delays or quick loads
            scores["delay"] += 0.3
            reasons.append("short_duration_hint")

    # Loads==0 could indicate idle/delay
    loads = raw_row.get("loads")
    if loads is not None:
        try:
            if int(str(loads)) == 0:
                scores["idle"] += 0.4
                scores["delay"] += 0.2
                reasons.append("zero_loads_hint")
        except Exception:
            pass

    # Final selection
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_label, top_score = sorted_scores[0]
    second_score = sorted_scores[1][1]

    is_ambiguous = False
    # Ambiguity if top score low or close to second-best
    if top_score < 0.55 or (top_score - second_score) < 0.15:
        is_ambiguous = True
        reasons.append("low_confidence_or_close_scores")

    # Never default silently to production when ambiguous
    if top_label == "production" and is_ambiguous:
        # force ambiguous classification but still return production as label
        reasons.append("ambiguous_production")

    return top_label, is_ambiguous, reasons


def _apply_daily_service_rule(event: TimelineEvent) -> None:
    if event.event_type == "service" and event.duration_minutes is not None and event.duration_minutes > 60:
        event.inference_reasons.append("service_duration_exceeded_60_minutes")
        event.event_type = "breakdown"
        event.is_breakdown = True
        event.is_daily_service = False


def _build_timeline_event(row: ActivityRow, shift: str) -> TimelineEvent:
    start = row.get("_from_dt")
    end = row.get("_to_dt")
    duration = None
    if start and end:
        duration = (end - start).total_seconds() / 60.0
        if duration < 0:
            duration += 24 * 60
    event_type, is_ambig, class_reasons = _classify_event(row)
    event = TimelineEvent(
        row_index=row.get("row_index"),
        activity_code=row.get("activity_code"),
        start_time=start.strftime("%H:%M") if start else None,
        end_time=end.strftime("%H:%M") if end else None,
        duration_minutes=duration,
        location=row.get("location"),
        loads=row.get("loads"),
        remarks=row.get("remarks"),
        event_type=event_type,
        is_inferred_end_time=row.get("is_inferred_end_time", False),
        is_ambiguous=row.get("is_ambiguous", False),
        inference_reasons=row.get("inference_reasons", []),
    )
    # attach classification ambiguity and reasons
    if is_ambig:
        event.is_ambiguous = True
        event.inference_reasons = (event.inference_reasons or []) + ["classification_ambiguous"] + class_reasons
    else:
        event.inference_reasons = (event.inference_reasons or []) + class_reasons
    event.is_safety_meeting = event_type == "safety_meeting"
    event.is_daily_service = event_type == "service"
    event.is_breakdown = event_type == "breakdown"
    event.is_delay = event_type == "delay"
    event.is_idle = event_type == "idle"

    if _is_match(event.remarks, SHIFT_CHANGE_KEYWORDS):
        event.is_change_of_shift = True
        event.inference_reasons.append("shift_change_detected_in_remarks")

    _apply_daily_service_rule(event)
    return event


def _compute_idle_gaps(events: List[TimelineEvent], shift: str, reference_date: Optional[date] = None) -> List[IdleGap]:
    if reference_date is None:
        reference_date = date.today()
    shift_start, shift_end = _compute_shift_window(shift, reference_date)
    periods: List[Tuple[datetime, datetime]] = []

    for event in events:
        if event.start_time and event.end_time and event.event_type != "idle":
            start_dt = _anchor_datetime(_parse_time_string(event.start_time), shift, reference_date)
            end_dt = _anchor_datetime(_parse_time_string(event.end_time), shift, reference_date)
            if start_dt and end_dt:
                if end_dt < start_dt:
                    end_dt += timedelta(days=1)
                periods.append((start_dt, end_dt))

    periods.sort(key=lambda p: p[0])
    gaps: List[IdleGap] = []
    cursor = shift_start

    for start_dt, end_dt in periods:
        if start_dt > cursor:
            gap_minutes = (start_dt - cursor).total_seconds() / 60.0
            gaps.append(IdleGap(start_time=cursor.strftime("%H:%M"), end_time=start_dt.strftime("%H:%M"), duration_minutes=gap_minutes))
            cursor = end_dt if end_dt > cursor else cursor
        elif end_dt > cursor:
            cursor = end_dt

    if shift_end > cursor:
        gap_minutes = (shift_end - cursor).total_seconds() / 60.0
        gaps.append(IdleGap(start_time=cursor.strftime("%H:%M"), end_time=shift_end.strftime("%H:%M"), duration_minutes=gap_minutes))

    return gaps


def process_checklist_timeline(ocr_output: OCRChecklist, reference_date: Optional[date] = None) -> Dict[str, Any]:
    """Process OCR checklist output into structured timeline events.

    Args:
        ocr_output: OCR-extracted data including header and activities.
        reference_date: Optional date used to anchor shift windows.

    Returns:
        dict: timeline events, idle gaps, and summary metrics.
    """
    header = ocr_output.get("header", {})
    raw_activities = [row for row in ocr_output.get("activities", []) if isinstance(row, dict)]
    standardized_activities = [_standardize_activity_row(row) for row in raw_activities]
    shift = _normalize_shift(_get_value(header.get("shift")), standardized_activities)
    if reference_date is None:
        reference_date = date.today()

    enriched_rows = _infer_end_times(standardized_activities, shift, reference_date)

    # Resolve overlaps: if overlap exists and previous row end was inferred, tighten it to next start (log reason).
    # Otherwise mark overlapping rows as ambiguous.
    # Build list of rows with anchored datetimes
    rows_with_dt = [row for row in enriched_rows]
    # Sort by from_dt (None values go last)
    def _sort_key(r):
        dt = r.get("_from_dt")
        return (dt is None, dt or datetime.min)

    rows_with_dt.sort(key=_sort_key)
    for i in range(len(rows_with_dt) - 1):
        cur = rows_with_dt[i]
        nxt = rows_with_dt[i + 1]
        cur_start = cur.get("_from_dt")
        cur_end = cur.get("_to_dt")
        next_start = nxt.get("_from_dt")
        # Only consider definite datetimes
        if cur_start and cur_end and next_start:
            if cur_end > next_start:
                # overlap detected
                if cur.get("is_inferred_end_time"):
                    # tighten current end to next start if it reduces overlap and keeps positive duration
                    if next_start > cur_start:
                        cur["_to_dt"] = next_start
                        cur["inference_reasons"] = (cur.get("inference_reasons") or []) + ["adjusted_end_to_prevent_overlap"]
                        cur["is_inferred_end_time"] = True
                    else:
                        cur["is_ambiguous"] = True
                        cur["inference_reasons"] = (cur.get("inference_reasons") or []) + ["overlap_ambiguous"]
                elif nxt.get("is_inferred_end_time"):
                    # try to adjust next end if it was inferred and reducing overlap helps
                    if nxt.get("_to_dt") and nxt.get("_to_dt") > next_start and nxt.get("_to_dt") > cur_end:
                        # nothing safe to do here — mark both ambiguous
                        cur["is_ambiguous"] = True
                        nxt["is_ambiguous"] = True
                        cur["inference_reasons"] = (cur.get("inference_reasons") or []) + ["overlap_with_next"]
                        nxt["inference_reasons"] = (nxt.get("inference_reasons") or []) + ["overlap_with_prev"]
                    else:
                        cur["is_ambiguous"] = True
                        nxt["is_ambiguous"] = True
                        cur["inference_reasons"] = (cur.get("inference_reasons") or []) + ["overlap_with_next"]
                        nxt["inference_reasons"] = (nxt.get("inference_reasons") or []) + ["overlap_with_prev"]
                else:
                    # neither is inferred — cannot auto-correct safely
                    cur["is_ambiguous"] = True
                    nxt["is_ambiguous"] = True
                    cur["inference_reasons"] = (cur.get("inference_reasons") or []) + ["overlap_detected"]
                    nxt["inference_reasons"] = (nxt.get("inference_reasons") or []) + ["overlap_detected"]

    events = [_build_timeline_event(row, shift) for row in enriched_rows]
    # Enforce consistency on built events
    consistency_report = enforce_consistency(events, shift, reference_date)
    if not consistency_report.get("valid", True):
        summary = {
            "shift": shift,
            "shift_start": _compute_shift_window(shift, reference_date)[0].strftime("%H:%M"),
            "shift_end": _compute_shift_window(shift, reference_date)[1].strftime("%H:%M"),
            "consistency": consistency_report,
        }
        return {"events": [event.to_dict() for event in events], "summary": summary}

    idle_gaps = _compute_idle_gaps(events, shift, reference_date)
    # Run system-wide consistency checks (engine-hours vs timeline, counts, large gaps)
    system_checks = system_consistency_checks(events, shift, ocr_output.get("header", {}), reference_date)

    summary = {
        "shift": shift,
        "shift_start": _compute_shift_window(shift, reference_date)[0].strftime("%H:%M"),
        "shift_end": _compute_shift_window(shift, reference_date)[1].strftime("%H:%M"),
        "change_of_shift_detected": any(event.is_change_of_shift for event in events),
        "safety_meeting_detected": any(event.is_safety_meeting for event in events),
        "daily_service_detected": any(event.is_daily_service for event in events),
        "machine_release_time": next(
            (event.end_time for event in reversed(events) if event.is_daily_service and event.end_time),
            None,
        ),
        "total_idle_minutes": sum(g.duration_minutes for g in idle_gaps),
        "idle_gaps": [gap.to_dict() for gap in idle_gaps],
        "event_counts": {
            "production": sum(1 for event in events if event.event_type == "production"),
            "delay": sum(1 for event in events if event.event_type == "delay"),
            "breakdown": sum(1 for event in events if event.event_type == "breakdown"),
            "service": sum(1 for event in events if event.event_type == "service"),
            "safety_meeting": sum(1 for event in events if event.event_type == "safety_meeting"),
            "idle": sum(1 for event in events if event.event_type == "idle"),
        },
        "anomalies_detected": bool(system_checks.get("anomalies")),
        "system_consistency": system_checks,
    }

    return {
        "events": [event.to_dict() for event in events],
        "summary": summary,
    }


def is_change_of_shift_detected(ocr_output: OCRChecklist) -> bool:
    header = ocr_output.get("header", {})
    if _is_match(_get_value(header.get("shift")), SHIFT_CHANGE_KEYWORDS):
        return True
    for row in ocr_output.get("activities", []):
        if _is_match(_get_value(row.get("remarks")), SHIFT_CHANGE_KEYWORDS):
            return True
    return False


# Additional utility functions from timeline.py

def parse_time(value: Optional[str]) -> Optional[datetime]:
    """Parse a time string into a datetime object anchored to 1900-01-01."""
    if not value:
        return None
    clean = value.strip().lower().replace(".", ":")
    formats = ["%H:%M", "%H%M", "%I:%M %p", "%I%M %p"]
    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue
    return None


def format_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def infer_to_times(raw_events: List[Dict[str, Optional[str]]]) -> List[Dict[str, Optional[str]]]:
    """Fill missing end times using the next event's start time when appropriate."""
    enriched = []
    parsed = []
    for row in raw_events:
        parsed.append({**row, "_start_dt": parse_time(row.get("from_time_raw")), "_end_dt": parse_time(row.get("to_time_raw"))})

    for index, row in enumerate(parsed):
        if row["_end_dt"] is None and row["_start_dt"] is not None:
            next_row = parsed[index + 1] if index + 1 < len(parsed) else None
            if next_row and next_row["_start_dt"]:
                if next_row["_start_dt"] > row["_start_dt"]:
                    row["_end_dt"] = next_row["_start_dt"]
                    row["inference_reason"] = "inferred_from_next_event"
                    row["is_inferred"] = True
                else:
                    row["inference_reason"] = "ambiguous_gap"
                    row["is_ambiguous"] = True
            else:
                row["inference_reason"] = "missing_end_time"
                row["is_ambiguous"] = True
        enriched.append(row)
    return enriched


def compute_release_time(events: List[TimelineEvent], shift: str) -> Optional[str]:
    """Compute release time using service events and the checklist rules."""
    service_events = [event for event in events if event.event_type == "service" and event.end_time]
    if not service_events:
        return None
    latest = max(service_events, key=lambda event: event.end_time)
    return latest.end_time


def compute_idle_time(events: List[TimelineEvent], shift: str, reference_date: Optional[date] = None) -> float:
    """Compute idle time as gaps between events inside the shift."""
    gaps = _compute_idle_gaps(events, shift, reference_date)
    return sum(g.duration_minutes for g in gaps)


def compute_metrics(events: List[TimelineEvent], shift: str, document_date: Optional[date] = None) -> Dict[str, Optional[float]]:
    """Compute analytics for the interpreted timeline."""
    if document_date is None:
        document_date = date.today()
    shift_start_dt, shift_end_dt = _compute_shift_window(shift, document_date)
    total_shift_minutes = (shift_end_dt - shift_start_dt).total_seconds() / 60.0

    # Build anchored event periods clipped to shift window
    periods = []  # list of (start_dt, end_dt, event_type)
    for ev in events:
        if not ev.start_time or not ev.end_time:
            continue
        s = parse_time(ev.start_time)
        e = parse_time(ev.end_time)
        if not s or not e:
            continue
        # Anchor to document_date and handle night wrap
        s_dt = _anchor_datetime(s.time() if hasattr(s, 'time') else s, shift, document_date)
        e_dt = _anchor_datetime(e.time() if hasattr(e, 'time') else e, shift, document_date)
        if shift == "night" and e_dt <= s_dt:
            e_dt += timedelta(days=1)
        # Clip to shift window
        if e_dt <= shift_start_dt or s_dt >= shift_end_dt:
            continue
        s_dt_clipped = max(s_dt, shift_start_dt)
        e_dt_clipped = min(e_dt, shift_end_dt)
        if e_dt_clipped <= s_dt_clipped:
            continue
        periods.append((s_dt_clipped, e_dt_clipped, ev.event_type))

    # Validate classifications present
    known_types = {"production", "breakdown", "service", "safety_meeting", "delay", "idle"}
    for _, _, t in periods:
        if t not in known_types:
            raise ValueError(f"Unknown event type in metrics computation: {t}")

    # Build timeline segments to avoid double counting
    points = {shift_start_dt, shift_end_dt}
    for s, e, _ in periods:
        points.add(s)
        points.add(e)
    pts = sorted(points)

    totals = {"production": 0.0, "breakdown": 0.0, "service": 0.0, "safety_meeting": 0.0, "delay": 0.0, "idle": 0.0}

    conflicts = []
    for i in range(len(pts) - 1):
        seg_start = pts[i]
        seg_end = pts[i + 1]
        seg_minutes = (seg_end - seg_start).total_seconds() / 60.0
        active = [t for s, e, t in periods if s <= seg_start and e >= seg_end]
        if len(active) == 0:
            totals["idle"] += seg_minutes
        elif len(set(active)) == 1:
            totals[active[0]] += seg_minutes
        else:
            # overlapping different typed events -> cannot safely compute without resolution
            conflicts.append({"segment": (seg_start, seg_end), "types": list(set(active))})

    if conflicts:
        raise ValueError(f"Conflicting overlapping events detected during metrics computation: {conflicts}")

    # Ensure safety_minutes included
    safety_minutes = totals.get("safety_meeting", 0.0)

    production_minutes = totals.get("production", 0.0)
    breakdown_minutes = totals.get("breakdown", 0.0)
    service_minutes = totals.get("service", 0.0)
    delay_minutes = totals.get("delay", 0.0)
    idle_minutes = totals.get("idle", 0.0)

    # Reconciliation check
    sum_all = production_minutes + breakdown_minutes + service_minutes + safety_minutes + delay_minutes + idle_minutes
    # allow 1 second tolerance
    if abs(sum_all - total_shift_minutes) > 0.1:
        raise ValueError(f"Metrics reconciliation failed: sum categories {sum_all} != shift duration {total_shift_minutes}")

    # Release-based availability: time after release to shift end minus breakdown
    release_time = compute_release_time(events, shift)
    availability_minutes = None
    if release_time:
        r = parse_time(release_time)
        if r:
            r_dt = _anchor_datetime(r.time() if hasattr(r, 'time') else r, shift, document_date)
            if shift == "night" and r_dt < shift_start_dt:
                r_dt += timedelta(days=1)
            availability_minutes = max(0.0, (shift_end_dt - r_dt).total_seconds() / 60.0 - breakdown_minutes)

    # Utilization: production / available (if available defined)
    utilization_ratio = None
    if availability_minutes is not None and availability_minutes > 0:
        utilization_ratio = production_minutes / availability_minutes

    # Engine hours validation: if header values provided on events' context (not available here), caller should validate separately.

    return {
        "total_shift_minutes": total_shift_minutes,
        "production_duration_minutes": production_minutes,
        "breakdown_duration_minutes": breakdown_minutes,
        "service_duration_minutes": service_minutes,
        "safety_meeting_minutes": safety_minutes,
        "delay_minutes": delay_minutes,
        "idle_duration_minutes": idle_minutes,
        "availability_minutes": availability_minutes,
        "utilization_ratio": utilization_ratio,
        "release_time": release_time,
    }


def detect_safety_meeting(ocr_output: OCRChecklist) -> bool:
    for row in ocr_output.get("activities", []):
        if _is_match(_get_value(row.get("remarks")), SAFETY_KEYWORDS):
            return True
    return False


def enforce_consistency(events: List[TimelineEvent], shift: str, reference_date: Optional[date] = None) -> Dict[str, Any]:
    """Detect and attempt to resolve timeline inconsistencies.

    Returns a report with fields:
      - valid: bool
      - consistency_score: float (0-100)
      - actions: list of adjustments performed
      - errors: list of unresolved critical conflicts
    """
    if reference_date is None:
        reference_date = date.today()

    # Build anchored datetimes for events
    anchored = []
    for ev in events:
        s = parse_time(ev.start_time) if ev.start_time else None
        e = parse_time(ev.end_time) if ev.end_time else None
        if s:
            s_dt = _anchor_datetime(s.time() if hasattr(s, 'time') else s, shift, reference_date)
        else:
            s_dt = None
        if e:
            e_dt = _anchor_datetime(e.time() if hasattr(e, 'time') else e, shift, reference_date)
            if shift == "night" and e_dt <= s_dt:
                e_dt += timedelta(days=1)
        else:
            e_dt = None
        anchored.append({"event": ev, "start": s_dt, "end": e_dt, "inferred": ev.is_inferred_end_time})

    # Build segments
    shift_start, shift_end = _compute_shift_window(shift, reference_date)
    points = {shift_start, shift_end}
    for a in anchored:
        if a["start"]:
            points.add(a["start"])
        if a["end"]:
            points.add(a["end"])
    pts = sorted(points)

    total_conflict_minutes = 0.0
    actions = []
    errors = []

    for i in range(len(pts) - 1):
        seg_s = pts[i]
        seg_e = pts[i + 1]
        seg_min = (seg_e - seg_s).total_seconds() / 60.0
        # find active events covering full segment
        active = [a for a in anchored if a["start"] and a["end"] and a["start"] <= seg_s and a["end"] >= seg_e]
        types = list({a["event"].event_type for a in active})
        if len(types) <= 1:
            continue
        # conflict detected
        total_conflict_minutes += seg_min

        # Attempt resolution: prefer adjusting inferred end time to seg_s
        inferred_candidates = [a for a in active if a.get("inferred")]
        if len(inferred_candidates) == 1:
            cand = inferred_candidates[0]
            ev = cand["event"]
            old_end = cand["end"]
            if seg_s > cand["start"]:
                # adjust end to seg_s
                new_end = seg_s
                cand["end"] = new_end
                ev.end_time = new_end.strftime("%H:%M")
                ev.duration_minutes = (new_end - cand["start"]).total_seconds() / 60.0
                ev.is_inferred_end_time = True
                ev.inference_reasons = (ev.inference_reasons or []) + ["adjusted_end_to_resolve_overlap"]
                actions.append({"action": "adjusted_end", "row_index": ev.row_index, "old_end": old_end.strftime("%H:%M") if old_end else None, "new_end": new_end.strftime("%H:%M")})
                continue
        # If duplicates (exact same start/end) mark as duplicate warning
        starts_ends = {(a["start"], a["end"]) for a in active}
        if len(starts_ends) == 1:
            for a in active:
                a["event"].is_ambiguous = True
                a["event"].inference_reasons = (a["event"].inference_reasons or []) + ["duplicate_time_range"]
            actions.append({"action": "flag_duplicates", "rows": [a["event"].row_index for a in active]})
            continue
        # otherwise unresolved
        errors.append({"segment": (seg_s, seg_e), "types": types, "rows": [a["event"].row_index for a in active]})

    shift_minutes = (shift_end - shift_start).total_seconds() / 60.0
    consistency_score = max(0.0, 100.0 * (1.0 - (total_conflict_minutes / shift_minutes)))

    valid = len(errors) == 0

    report = {
        "valid": valid,
        "consistency_score": round(consistency_score, 2),
        "actions": actions,
        "errors": errors,
    }
    return report


def system_consistency_checks(events: List[TimelineEvent], shift: str, header: Dict[str, Any], reference_date: Optional[date] = None, thresholds: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run system-wide consistency checks.

    Checks implemented:
      - engine hours (from header) vs timeline computed engine minutes
      - activity count vs header counts
      - missing/large unexplained gaps
      - unrealistic durations per event

    Returns a dict with keys: anomalies (list), metrics, thresholds_used
    """
    if reference_date is None:
        reference_date = date.today()

    # Default thresholds
    default_thresholds = {
        "engine_hours_tolerance_pct": 0.15,  # 15%
        "large_gap_minutes": 120,  # 2 hours
        "max_reasonable_event_minutes": 12 * 60,  # 12 hours
        "min_activity_duration_minutes": 1,  # minimum meaningful activity
    }
    if thresholds:
        default_thresholds.update(thresholds)

    # Compute total timeline minutes (non-idle excluding safety meetings?) We'll take all events except idle
    total_timeline_minutes = sum(ev.duration_minutes or 0.0 for ev in events if ev.event_type != "idle")

    anomalies = []

    # 1) Engine hours vs timeline
    engine_hours_raw = header.get("engine_hours") or header.get("machine_hours") or header.get("engine_hours_total")
    engine_hours_value = None
    if engine_hours_raw:
        try:
            engine_hours_value = float(str(engine_hours_raw).strip())
        except Exception:
            engine_hours_value = None

    if engine_hours_value is not None:
        engine_minutes_header = engine_hours_value * 60.0
        diff = abs(engine_minutes_header - total_timeline_minutes)
        pct = diff / engine_minutes_header if engine_minutes_header > 0 else 1.0
        if pct > default_thresholds["engine_hours_tolerance_pct"]:
            anomalies.append({
                "type": "engine_hours_mismatch",
                "header_engine_hours": engine_hours_value,
                "timeline_minutes": total_timeline_minutes,
                "difference_minutes": diff,
                "difference_pct": round(pct, 3),
            })

    # 2) Activity count vs duration
    header_activity_count = None
    try:
        header_activity_count = int(str(header.get("activity_count") or header.get("rows") or header.get("activities_count") or "").strip())
    except Exception:
        header_activity_count = None

    non_idle_events = [ev for ev in events if ev.event_type != "idle"]
    computed_activity_count = len(non_idle_events)
    if header_activity_count is not None:
        if header_activity_count != computed_activity_count:
            anomalies.append({
                "type": "activity_count_mismatch",
                "header_count": header_activity_count,
                "computed_count": computed_activity_count,
            })

    # 3) Missing gaps / large unexplained gaps
    idle_gaps = _compute_idle_gaps(events, shift, reference_date)
    large_gaps = [g for g in idle_gaps if g.duration_minutes >= default_thresholds["large_gap_minutes"]]
    for g in large_gaps:
        anomalies.append({
            "type": "large_unexplained_gap",
            "start_time": g.start_time,
            "end_time": g.end_time,
            "duration_minutes": g.duration_minutes,
        })

    # 4) Unrealistic durations: events longer than reasonable maximum or shorter than min
    for ev in events:
        if ev.duration_minutes is None:
            continue
        if ev.duration_minutes >= default_thresholds["max_reasonable_event_minutes"]:
            anomalies.append({
                "type": "unrealistic_long_duration",
                "row_index": ev.row_index,
                "duration_minutes": ev.duration_minutes,
                "event_type": ev.event_type,
            })
        if ev.duration_minutes < default_thresholds["min_activity_duration_minutes"] and ev.event_type != "idle":
            anomalies.append({
                "type": "unrealistic_short_duration",
                "row_index": ev.row_index,
                "duration_minutes": ev.duration_minutes,
                "event_type": ev.event_type,
            })

    # Additional heuristic: many short events totalling large time -> suspicious
    short_events = [ev for ev in events if ev.duration_minutes and ev.duration_minutes < 5]
    if len(short_events) >= max(5, int(len(events) * 0.3)) and sum(ev.duration_minutes for ev in short_events) > 60:
        anomalies.append({"type": "many_short_events", "count": len(short_events), "total_minutes": sum(ev.duration_minutes for ev in short_events)})

    report = {
        "metrics": {
            "total_timeline_minutes": total_timeline_minutes,
            "computed_activity_count": computed_activity_count,
            "header_engine_hours": engine_hours_value,
            "header_activity_count": header_activity_count,
        },
        "thresholds_used": default_thresholds,
        "anomalies": anomalies,
    }
    return report
