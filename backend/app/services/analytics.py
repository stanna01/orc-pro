"""Machine performance analytics module for ORC Pro.

This module computes availability, utilization, dowtime, and production metrics
from processed timeline events and engine hours.
"""

from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class EngineHoursMetrics:
    """Engine and transmission hours metrics."""
    start_engine_hours: Optional[float]
    end_engine_hours: Optional[float]
    engine_hours_delta: Optional[float]
    start_transmission_hours: Optional[float]
    end_transmission_hours: Optional[float]
    transmission_hours_delta: Optional[float]
    engine_hours_valid: bool
    validation_message: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_engine_hours": self.start_engine_hours,
            "end_engine_hours": self.end_engine_hours,
            "engine_hours_delta": self.engine_hours_delta,
            "start_transmission_hours": self.start_transmission_hours,
            "end_transmission_hours": self.end_transmission_hours,
            "transmission_hours_delta": self.transmission_hours_delta,
            "engine_hours_valid": self.engine_hours_valid,
            "validation_message": self.validation_message,
        }


@dataclass
class AvailabilityBreakdown:
    """Shift availability composition."""
    total_shift_minutes: float
    release_time: Optional[str]
    release_delay_minutes: Optional[float]
    available_minutes: Optional[float]
    production_minutes: float
    breakdown_minutes: float
    service_minutes: float
    safety_minutes: float
    idle_minutes: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_shift_minutes": self.total_shift_minutes,
            "release_time": self.release_time,
            "release_delay_minutes": self.release_delay_minutes,
            "available_minutes": self.available_minutes,
            "production_minutes": self.production_minutes,
            "breakdown_minutes": self.breakdown_minutes,
            "service_minutes": self.service_minutes,
            "safety_minutes": self.safety_minutes,
            "idle_minutes": self.idle_minutes,
        }


@dataclass
class PerformanceMetrics:
    """Computed machine performance indicators."""
    availability_ratio: Optional[float]
    utilization_ratio: Optional[float]
    downtime_ratio: Optional[float]
    production_ratio: Optional[float]
    breakdown_ratio: Optional[float]
    idle_ratio: Optional[float]
    safety_ratio: Optional[float]
    effective_availability_ratio: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "availability_ratio": self.availability_ratio,
            "utilization_ratio": self.utilization_ratio,
            "downtime_ratio": self.downtime_ratio,
            "production_ratio": self.production_ratio,
            "breakdown_ratio": self.breakdown_ratio,
            "idle_ratio": self.idle_ratio,
            "safety_ratio": self.safety_ratio,
            "effective_availability_ratio": self.effective_availability_ratio,
        }


def _compute_shift_window_minutes(shift: str) -> float:
    """Compute total shift duration in minutes."""
    if shift == "night":
        return 12 * 60
    return 12 * 60


def _parse_time_to_minutes(time_str: Optional[str]) -> Optional[int]:
    """Parse HH:MM format to minutes since midnight."""
    if not time_str:
        return None
    try:
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        return hours * 60 + minutes
    except (ValueError, IndexError):
        return None


def _time_delta_minutes(from_time: str, to_time: str, shift: str) -> Optional[float]:
    """Compute time delta in minutes, accounting for shift boundary."""
    from_min = _parse_time_to_minutes(from_time)
    to_min = _parse_time_to_minutes(to_time)

    if from_min is None or to_min is None:
        return None

    if shift == "night":
        if to_min < from_min:
            delta = (24 * 60 - from_min) + to_min
        else:
            delta = to_min - from_min
    else:
        delta = to_min - from_min
        if delta < 0:
            delta += 24 * 60

    return float(delta) if delta >= 0 else None


def _normalize_event_times(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize event times for consistency."""
    normalized = []
    for event in events:
        event_copy = event.copy()
        if not event_copy.get("duration_minutes") and event.get("start_time") and event.get("end_time"):
            duration = _time_delta_minutes(event["start_time"], event["end_time"], "night")
            if duration is not None:
                event_copy["duration_minutes"] = duration
        normalized.append(event_copy)
    return normalized


def compute_engine_hours_metrics(
    start_engine_hours: Optional[float],
    end_engine_hours: Optional[float],
    start_transmission_hours: Optional[float],
    end_transmission_hours: Optional[float],
    production_minutes: Optional[float] = None,
) -> EngineHoursMetrics:
    """Validate engine hours and compute deltas.

    Rules:
    - Engine hours should increase if production occurred
    - If production_minutes > 0, end_engine_hours should be > start_engine_hours
    - Negative deltas are invalid
    - Large deltas may indicate meter rollover or malfunction

    Args:
        start_engine_hours: Engine hours at shift start
        end_engine_hours: Engine hours at shift end
        start_transmission_hours: Transmission hours at shift start
        end_transmission_hours: Transmission hours at shift end
        production_minutes: Total production time in minutes (optional for validation)

    Returns:
        EngineHoursMetrics with validation results
    """
    engine_delta = None
    trans_delta = None
    message = None
    valid = True

    if start_engine_hours is not None and end_engine_hours is not None:
        engine_delta = end_engine_hours - start_engine_hours
        if engine_delta < 0:
            message = "Engine hours decreased (meter rollover or invalid data)"
            valid = False
        elif production_minutes and production_minutes > 60 and engine_delta == 0:
            message = "Engine hours unchanged despite significant production time"
            valid = False
        elif engine_delta > 20:
            message = "Engine hours delta exceeded 20 hours (possible rollover)"
    
    if start_transmission_hours is not None and end_transmission_hours is not None:
        trans_delta = end_transmission_hours - start_transmission_hours
        if trans_delta < 0:
            if message:
                message += "; Transmission hours also decreased"
            else:
                message = "Transmission hours decreased (meter rollover or invalid data)"
            valid = False

    return EngineHoursMetrics(
        start_engine_hours=start_engine_hours,
        end_engine_hours=end_engine_hours,
        engine_hours_delta=engine_delta,
        start_transmission_hours=start_transmission_hours,
        end_transmission_hours=end_transmission_hours,
        transmission_hours_delta=trans_delta,
        engine_hours_valid=valid,
        validation_message=message,
    )


def compute_availability_breakdown(
    events: List[Dict[str, Any]],
    shift: str,
    release_time: Optional[str] = None,
) -> AvailabilityBreakdown:
    """Compute shift availability and breakdown of time allocation.

    Formula:
    - total_shift_minutes: 12 hours (720 min for day or night)
    - release_delay_minutes: minutes from end of last service to shift end
    - available_minutes: shift_end - release_time - breakdown_minutes
    - production_minutes: sum of production event durations
    - breakdown_minutes: sum of breakdown event durations
    - service_minutes: sum of service event durations
    - safety_minutes: sum of safety_meeting event durations
    - idle_minutes: gaps between events

    Args:
        events: List of processed timeline events
        shift: "day" or "night"
        release_time: Optional machine release time (HH:MM format)

    Returns:
        AvailabilityBreakdown object
    """
    total_shift_minutes = _compute_shift_window_minutes(shift)
    normalized_events = _normalize_event_times(events)

    production_minutes = sum(
        e.get("duration_minutes", 0) or 0
        for e in normalized_events
        if e.get("event_type") == "production" and e.get("duration_minutes")
    )

    breakdown_minutes = sum(
        e.get("duration_minutes", 0) or 0
        for e in normalized_events
        if e.get("event_type") == "breakdown" and e.get("duration_minutes")
    )

    service_minutes = sum(
        e.get("duration_minutes", 0) or 0
        for e in normalized_events
        if e.get("event_type") == "service" and e.get("duration_minutes")
    )

    safety_minutes = sum(
        e.get("duration_minutes", 0) or 0
        for e in normalized_events
        if e.get("event_type") == "safety_meeting" and e.get("duration_minutes")
    )

    idle_minutes = sum(
        e.get("duration_minutes", 0) or 0
        for e in normalized_events
        if e.get("event_type") == "idle" and e.get("duration_minutes")
    )

    release_delay_minutes = None
    available_minutes = None

    if release_time:
        release_min = _parse_time_to_minutes(release_time)
        shift_end_min = 18 * 60 if shift == "day" else 6 * 60
        if release_min is not None:
            if shift == "night" and shift_end_min < release_min:
                release_delay_minutes = (24 * 60 - release_min) + shift_end_min
            else:
                release_delay_minutes = shift_end_min - release_min
            available_minutes = max(0, (available_minutes or total_shift_minutes) - breakdown_minutes)

    if available_minutes is None:
        available_minutes = total_shift_minutes - breakdown_minutes

    return AvailabilityBreakdown(
        total_shift_minutes=total_shift_minutes,
        release_time=release_time,
        release_delay_minutes=release_delay_minutes,
        available_minutes=available_minutes,
        production_minutes=production_minutes,
        breakdown_minutes=breakdown_minutes,
        service_minutes=service_minutes,
        safety_minutes=safety_minutes,
        idle_minutes=idle_minutes,
    )


def compute_performance_ratios(
    availability_breakdown: AvailabilityBreakdown,
    engine_hours_metrics: Optional[EngineHoursMetrics] = None,
) -> PerformanceMetrics:
    """Compute derived performance ratios.

    Formulas:
    - availability_ratio = available_minutes / total_shift_minutes
    - utilization_ratio = production_minutes / available_minutes
    - downtime_ratio = breakdown_minutes / available_minutes
    - production_ratio = production_minutes / total_shift_minutes
    - breakdown_ratio = breakdown_minutes / total_shift_minutes
    - idle_ratio = idle_minutes / total_shift_minutes
    - safety_ratio = safety_minutes / total_shift_minutes
    - effective_availability = (available_minutes - idle_minutes) / total_shift_minutes

    Args:
        availability_breakdown: Computed availability breakdown
        engine_hours_metrics: Optional engine hours validation

    Returns:
        PerformanceMetrics with all computed ratios
    """
    total = availability_breakdown.total_shift_minutes or 1
    available = availability_breakdown.available_minutes or 1

    availability_ratio = availability_breakdown.available_minutes / total if total > 0 else None
    utilization_ratio = availability_breakdown.production_minutes / available if available > 0 else None
    downtime_ratio = availability_breakdown.breakdown_minutes / available if available > 0 else None
    production_ratio = availability_breakdown.production_minutes / total if total > 0 else None
    breakdown_ratio = availability_breakdown.breakdown_minutes / total if total > 0 else None
    idle_ratio = availability_breakdown.idle_minutes / total if total > 0 else None
    safety_ratio = availability_breakdown.safety_minutes / total if total > 0 else None

    effective_available = (availability_breakdown.available_minutes or 0) - (availability_breakdown.idle_minutes or 0)
    effective_availability_ratio = effective_available / total if total > 0 else None

    return PerformanceMetrics(
        availability_ratio=availability_ratio,
        utilization_ratio=utilization_ratio,
        downtime_ratio=downtime_ratio,
        production_ratio=production_ratio,
        breakdown_ratio=breakdown_ratio,
        idle_ratio=idle_ratio,
        safety_ratio=safety_ratio,
        effective_availability_ratio=effective_availability_ratio,
    )


def compute_machine_analytics(
    events: List[Dict[str, Any]],
    shift: str,
    release_time: Optional[str] = None,
    start_engine_hours: Optional[float] = None,
    end_engine_hours: Optional[float] = None,
    start_transmission_hours: Optional[float] = None,
    end_transmission_hours: Optional[float] = None,
) -> Dict[str, Any]:
    """Compute complete machine performance analytics.

    Args:
        events: Processed timeline events
        shift: "day" or "night"
        release_time: Machine release time (HH:MM)
        start_engine_hours: Starting engine hours
        end_engine_hours: Ending engine hours
        start_transmission_hours: Starting transmission hours
        end_transmission_hours: Ending transmission hours

    Returns:
        Dict containing availability_breakdown, engine_metrics, and performance_ratios
    """
    production_minutes = sum(
        e.get("duration_minutes", 0) or 0
        for e in events
        if e.get("event_type") == "production"
    )

    availability = compute_availability_breakdown(events, shift, release_time)
    engine_metrics = compute_engine_hours_metrics(
        start_engine_hours,
        end_engine_hours,
        start_transmission_hours,
        end_transmission_hours,
        production_minutes,
    )
    performance = compute_performance_ratios(availability, engine_metrics)

    return {
        "availability_breakdown": availability.to_dict(),
        "engine_hours_metrics": engine_metrics.to_dict(),
        "performance_ratios": performance.to_dict(),
    }
