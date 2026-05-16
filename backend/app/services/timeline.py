"""Timeline inference and analytics for checklist events."""

import re
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Tuple

from backend.app.ml.ocr.pipeline import is_breakdown


@dataclass
class TimelineEvent:
    row_index: Optional[int]
    event_type: str
    activity_code: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    duration_minutes: Optional[float]
    workplace: Optional[str]
    ore_waste: Optional[str]
    loads: Optional[str]
    remarks: Optional[str]
    inference_reason: Optional[str]
    is_inferred: bool
    is_ambiguous: bool
    confidence: Optional[float]


SHIFT_WINDOWS = {
    "day": (time(hour=6, minute=0), time(hour=18, minute=0)),
    "night": (time(hour=18, minute=0), time(hour=6, minute=0)),
}


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


def get_event_type(activity_code: Optional[str], remarks: Optional[str]) -> str:
    """Classify the event type using rules and remarks."""
    if is_breakdown(activity_code, remarks):
        return "breakdown"
    if remarks:
        lower = remarks.lower()
        if re.search(r"safety\s*meeting|safety meeting|safety\s*briefing", lower):
            return "safety_meeting"
        if re.search(r"daily\s*service|service|maintenance|check", lower):
            return "service"
    return "production"


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


def normalize_activity_rows(raw_events: List[Dict[str, Optional[str]]]) -> List[TimelineEvent]:
    """Normalize raw activity rows into timeline events."""
    normalized = []
    enriched = infer_to_times(raw_events)
    for index, row in enumerate(enriched):
        start_dt = row.get("_start_dt")
        end_dt = row.get("_end_dt")
        duration = None
        if start_dt and end_dt:
            diff = end_dt - start_dt
            if diff.total_seconds() >= 0:
                duration = diff.total_seconds() / 60.0
            else:
                duration = abs(diff.total_seconds()) / 60.0

        event_type = get_event_type(row.get("activity_code_normalized") or row.get("activity_code_raw"), row.get("remarks_raw"))
        if event_type == "service" and duration is not None and duration > 60:
            event_type = "breakdown"
            row["inference_reason"] = "service_exceeded_60_minutes"
            row["is_inferred"] = True

        normalized.append(
            TimelineEvent(
                row_index=row.get("row_index"),
                event_type=event_type,
                activity_code=(row.get("activity_code_normalized") or row.get("activity_code_raw")),
                start_time=format_time(start_dt) if start_dt else None,
                end_time=format_time(end_dt) if end_dt else None,
                duration_minutes=duration,
                workplace=row.get("workplace_normalized") or row.get("workplace_raw"),
                ore_waste=row.get("ore_waste_normalized") or row.get("ore_waste_raw"),
                loads=row.get("loads_normalized") or row.get("loads_raw"),
                remarks=row.get("remarks_normalized") or row.get("remarks_raw"),
                inference_reason=row.get("inference_reason"),
                is_inferred=bool(row.get("is_inferred")),
                is_ambiguous=bool(row.get("is_ambiguous")),
                confidence=row.get("confidence"),
            )
        )
    return normalized


def shift_window(shift: str, reference_date: Optional[date] = None) -> Tuple[datetime, datetime]:
    """Compute the shift start and end datetimes for a given shift."""
    if reference_date is None:
        reference_date = date.today()
    start_time, end_time = SHIFT_WINDOWS.get(shift, SHIFT_WINDOWS["day"])
    start_dt = datetime.combine(reference_date, start_time)
    if shift == "night":
        end_dt = datetime.combine(reference_date + timedelta(days=1), end_time)
    else:
        end_dt = datetime.combine(reference_date, end_time)
    return start_dt, end_dt


def compute_release_time(events: List[TimelineEvent], shift: str) -> Optional[str]:
    """Compute release time using service events and the checklist rules."""
    service_events = [event for event in events if event.event_type == "service" and event.end_time]
    if not service_events:
        return None
    latest = max(service_events, key=lambda event: event.end_time)
    return latest.end_time


def compute_idle_time(events: List[TimelineEvent], shift: str, reference_date: Optional[date] = None) -> float:
    """Compute idle time as gaps between events inside the shift."""
    start_dt, end_dt = shift_window(shift, reference_date)
    event_periods = []
    for event in events:
        if event.start_time and event.end_time:
            start = parse_time(event.start_time)
            end = parse_time(event.end_time)
            if start and end:
                if shift == "night" and end < start:
                    end += timedelta(days=1)
                event_periods.append((start, end))
    event_periods.sort(key=lambda pair: pair[0])

    idle_minutes = 0.0
    cursor = start_dt
    for start, end in event_periods:
        if start > cursor:
            idle_minutes += (start - cursor).total_seconds() / 60.0
        if end > cursor:
            cursor = end
    if end_dt > cursor:
        idle_minutes += (end_dt - cursor).total_seconds() / 60.0
    return idle_minutes


def compute_metrics(events: List[TimelineEvent], shift: str, document_date: Optional[date] = None) -> Dict[str, Optional[float]]:
    """Compute analytics for the interpreted timeline."""
    if document_date is None:
        document_date = date.today()
    shift_start_dt, shift_end_dt = shift_window(shift, document_date)
    total_shift_minutes = (shift_end_dt - shift_start_dt).total_seconds() / 60.0

    production_minutes = sum(event.duration_minutes or 0.0 for event in events if event.event_type == "production")
    breakdown_minutes = sum(event.duration_minutes or 0.0 for event in events if event.event_type == "breakdown")
    service_minutes = sum(event.duration_minutes or 0.0 for event in events if event.event_type == "service")
    safety_minutes = sum(event.duration_minutes or 0.0 for event in events if event.event_type == "safety_meeting")
    idle_minutes = compute_idle_time(events, shift, document_date)

    release_time = compute_release_time(events, shift)
    availability_minutes = None
    if release_time:
        release_dt = parse_time(release_time)
        if release_dt:
            if shift == "night" and release_dt.hour < 12:
                release_dt += timedelta(days=1)
            availability_minutes = (shift_end_dt - release_dt).total_seconds() / 60.0 - breakdown_minutes
            if availability_minutes < 0:
                availability_minutes = 0.0

    utilization_ratio = None
    if availability_minutes is not None and availability_minutes > 0:
        utilization_ratio = production_minutes / availability_minutes

    return {
        "total_shift_minutes": total_shift_minutes,
        "production_duration_minutes": production_minutes,
        "breakdown_duration_minutes": breakdown_minutes,
        "service_duration_minutes": service_minutes,
        "safety_meeting_minutes": safety_minutes,
        "idle_duration_minutes": idle_minutes,
        "availability_minutes": availability_minutes,
        "utilization_ratio": utilization_ratio,
        "release_time": release_time,
    }
