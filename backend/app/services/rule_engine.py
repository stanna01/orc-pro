"""Rule engine for OCR checklist timeline processing.

This module converts OCR-extracted checklist data into a structured timeline of
mining events, infers missing end times, detects safety and shift events, and
computes idle gaps inside day/night shifts.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

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

SAFETY_KEYWORDS = [
    r"safety meeting",
    r"safety briefing",
    r"toolbox talk",
    r"pre-shift meeting",
    r"safety talk",
]

SERVICE_KEYWORDS = [
    r"daily service",
    r"service",
    r"maintenance",
    r"check",
    r"inspection",
]

DELAY_KEYWORDS = [
    r"delay",
    r"waiting",
    r"queue",
    r"standby",
    r"hold",
    r"break",
]

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
            if next_row and next_row.get("_from_dt"):
                candidate_end = next_row["_from_dt"]
                if candidate_end > row["_from_dt"]:
                    row["_to_dt"] = candidate_end
                    row["inferred_to_time"] = True
                    row["inference_reason"] = "inferred_from_next_event"
                else:
                    row["inference_reason"] = "ambiguous_next_event"
                    row["ambiguous"] = True
            elif row["_from_dt"] < end_dt:
                row["_to_dt"] = end_dt
                row["inferred_to_time"] = True
                row["inference_reason"] = "inferred_from_shift_end"
            else:
                row["inference_reason"] = "missing_end_time"
                row["ambiguous"] = True

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


def _classify_event(raw_row: ActivityRow) -> str:
    remarks = raw_row.get("remarks") or ""
    activity_code = raw_row.get("activity_code") or ""

    if _is_match(remarks, SAFETY_KEYWORDS):
        return "safety_meeting"
    if _is_match(remarks, BREAKDOWN_KEYWORDS) or re.match(r"^3\d{2,}$", activity_code):
        return "breakdown"
    if _is_match(remarks, SERVICE_KEYWORDS):
        return "service"
    if _is_match(remarks, DELAY_KEYWORDS):
        return "delay"
    if not activity_code and not remarks:
        return "idle"
    return "production"


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
    event_type = _classify_event(row)
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
    events = [_build_timeline_event(row, shift) for row in enriched_rows]
    idle_gaps = _compute_idle_gaps(events, shift, reference_date)
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


def detect_safety_meeting(ocr_output: OCRChecklist) -> bool:
    for row in ocr_output.get("activities", []):
        if _is_match(_get_value(row.get("remarks")), SAFETY_KEYWORDS):
            return True
    return False
