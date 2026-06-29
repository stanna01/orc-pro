"""Integration service between OCR output and rule engine processing.

This module converts OCR-extracted data into rule engine input, processes the
data through the rule engine pipeline (shift detection, service logic, idle time
computation, time inference), and persists the structured timeline events to the
database.
"""

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.models.schemas import OCROutput, OCRActivityRow, OCRField
from backend.app.models.checklist import (
    ChecklistForm,
    CleanedActivityEvent,
    ChecklistAnalytics,
)
from backend.app.models.checklist import RawOCRField
from backend.app.services.rule_engine import (
    process_checklist_timeline,
    TimelineEvent,
)
from backend.app.services.analytics import compute_machine_analytics


def convert_ocr_to_rule_engine_format(ocr_output: OCROutput) -> Dict[str, Any]:
    """Convert OCR output schema to rule_engine input format.
    
    Transforms OCROutput into the dictionary format expected by
    process_checklist_timeline().
    
    Args:
        ocr_output: OCROutput pydantic model from ML pipeline
        
    Returns:
        Dictionary matching rule_engine expected format with header and activities
    """
    # Convert OCRField objects to rule_engine format (dict with "value" key)
    header_data = {}
    if ocr_output.header:
        header = ocr_output.header
        # include full metadata (value, confidence, classification, bbox)
        def _field_to_dict(f):
            if not f:
                return None
            return {
                "value": f.value,
                "confidence": getattr(f, "confidence", None),
                "classification": getattr(f, "classification", None),
                "bbox": getattr(f, "bbox", None),
            }

        header_data = {
            "machine_id": _field_to_dict(header.machine_id) if header.machine_id else None,
            "operator_name": _field_to_dict(header.operator_name) if header.operator_name else None,
            "date": _field_to_dict(header.date) if header.date else None,
            "shift": _field_to_dict(header.shift) if header.shift else None,
            "engine_hours_start": _field_to_dict(header.engine_hours_start) if header.engine_hours_start else None,
            "engine_hours_end": _field_to_dict(header.engine_hours_end) if header.engine_hours_end else None,
        }

    activities_data = []
    for row in ocr_output.activities:
        def _f_to_dict(f):
            if not f:
                return None
            return {
                "value": f.value,
                "confidence": getattr(f, "confidence", None),
                "classification": getattr(f, "classification", None),
                "bbox": getattr(f, "bbox", None),
            }

        activity_row = {
            "row_index": row.row_index,
            "activity_code": _f_to_dict(row.activity_code),
            "from_time": _f_to_dict(row.from_time),
            "to_time": _f_to_dict(row.to_time),
            "location": _f_to_dict(row.location),
            "loads": _f_to_dict(row.loads),
            "remarks": _f_to_dict(row.remarks),
        }
        activities_data.append(activity_row)

    return {
        "header": header_data,
        "activities": activities_data,
    }


def process_ocr_with_rule_engine(
    ocr_output: OCROutput,
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Process OCR output through rule engine pipeline.
    
    Applies business logic including:
    - Shift detection (day vs night)
    - Daily service rule application
    - Idle time computation
    - Missing time inference
    - Event classification and refinement
    
    Args:
        ocr_output: OCR-extracted checklist data
        reference_date: Optional date for shift window anchoring (defaults to today)
        
    Returns:
        Dictionary with structured timeline events and summary metrics
    """
    if reference_date is None:
        reference_date = date.today()

    # Convert OCR format to rule_engine format
    rule_engine_input = convert_ocr_to_rule_engine_format(ocr_output)

    # Process through rule engine
    timeline_result = process_checklist_timeline(rule_engine_input, reference_date)

    return timeline_result


def persist_timeline_events(
    db: Session,
    checklist_form_id: int,
    timeline_events: List[Dict[str, Any]],
) -> List[CleanedActivityEvent]:
    """Persist timeline events to database.
    
    Args:
        db: SQLAlchemy session
        checklist_form_id: ID of parent checklist form
        timeline_events: List of processed timeline event dictionaries
        
    Returns:
        List of persisted CleanedActivityEvent records
    """
    persisted = []
    
    for event_dict in timeline_events:
        cleaned_event = CleanedActivityEvent(
            checklist_form_id=checklist_form_id,
            activity_entry_id=event_dict.get("row_index"),
            event_type=event_dict.get("event_type"),
            activity_code=event_dict.get("activity_code"),
            start_time=event_dict.get("start_time"),
            end_time=event_dict.get("end_time"),
            duration_minutes=event_dict.get("duration_minutes"),
            workplace=event_dict.get("location"),
            loads=event_dict.get("loads"),
            remarks=event_dict.get("remarks"),
            inference_reason=event_dict.get("inference_reasons")[0] if event_dict.get("inference_reasons") else None,
            is_inferred=event_dict.get("is_inferred_end_time", False),
            is_ambiguous=event_dict.get("is_ambiguous", False),
            confidence=event_dict.get("confidence"),
        )
        db.add(cleaned_event)
        persisted.append(cleaned_event)
    
    return persisted


def persist_timeline_summary(
    db: Session,
    checklist_form_id: int,
    summary: Dict[str, Any],
    events: List[Dict[str, Any]],
    shift: str,
    checklist_form: Optional[ChecklistForm] = None,
    machine_analytics: Optional[Dict[str, Any]] = None,
) -> ChecklistAnalytics:
    """Persist timeline summary and machine performance analytics to database.

    Args:
        db: SQLAlchemy session
        checklist_form_id: ID of parent checklist form
        summary: Summary dictionary from rule_engine
        events: Timeline events for analytics computation
        shift: "day" or "night"
        checklist_form: Optional checklist form for access to engine hours
        machine_analytics: Pre-computed analytics dict; recomputed if not supplied

    Returns:
        Persisted ChecklistAnalytics record with computed analytics
    """
    if machine_analytics is None:
        # Fallback: compute from scratch (caller should prefer passing pre-computed)
        start_engine_hours = checklist_form.start_engine_hours if checklist_form else None
        end_engine_hours = checklist_form.end_engine_hours if checklist_form else None
        start_transmission_hours = checklist_form.start_transmission_hours if checklist_form else None
        end_transmission_hours = checklist_form.end_transmission_hours if checklist_form else None
        machine_analytics = compute_machine_analytics(
            events=events,
            shift=shift,
            release_time=summary.get("machine_release_time"),
            start_engine_hours=start_engine_hours,
            end_engine_hours=end_engine_hours,
            start_transmission_hours=start_transmission_hours,
            end_transmission_hours=end_transmission_hours,
        )
    
    # Get existing analytics or create new
    analytics = db.query(ChecklistAnalytics).filter_by(
        checklist_form_id=checklist_form_id
    ).first()
    
    if not analytics:
        analytics = ChecklistAnalytics(checklist_form_id=checklist_form_id)
    
    # Extract and persist availability breakdown
    availability = machine_analytics.get("availability_breakdown", {})
    analytics.total_shift_minutes = availability.get("total_shift_minutes")
    analytics.release_time = availability.get("release_time")
    analytics.release_delay_minutes = availability.get("release_delay_minutes")
    analytics.production_duration_minutes = availability.get("production_minutes")
    analytics.breakdown_duration_minutes = availability.get("breakdown_minutes")
    analytics.idle_duration_minutes = availability.get("idle_minutes")
    analytics.daily_service_duration_minutes = availability.get("service_minutes")
    
    # Calculate total shift minutes
    total_shift_minutes = (
        availability.get("production_minutes", 0) +
        availability.get("breakdown_minutes", 0) +
        availability.get("service_minutes", 0) +
        availability.get("safety_minutes", 0) +
        availability.get("idle_minutes", 0)
    )
    analytics.total_shift_minutes = total_shift_minutes if total_shift_minutes > 0 else None
    
    # Extract and persist performance ratios (availability, utilization, downtime)
    ratios = machine_analytics.get("performance_ratios", {})
    # Convert availability_ratio to minutes
    if total_shift_minutes > 0:
        analytics.availability_minutes = (
            availability.get("production_minutes", 0) +
            availability.get("breakdown_minutes", 0) +
            availability.get("service_minutes", 0) +
            availability.get("safety_minutes", 0)
        )
    analytics.utilization_ratio = ratios.get("utilization_ratio")
    analytics.downtime_ratio = ratios.get("downtime_ratio")
    
    # Extract and persist engine hours metrics
    engine_metrics = machine_analytics.get("engine_hours_metrics", {})
    analytics.engine_hours_delta = engine_metrics.get("engine_hours_delta")
    analytics.engine_hours_valid = engine_metrics.get("engine_hours_valid")
    analytics.engine_hours_validation_message = engine_metrics.get("validation_message")
    analytics.transmission_hours_delta = engine_metrics.get("transmission_hours_delta")
    
    # Extract and persist event flags
    analytics.safety_meeting_detected = summary.get("safety_meeting_detected", False)
    analytics.change_of_shift_detected = summary.get("change_of_shift_detected", False)
    
    # Persist idle gaps
    idle_gaps = summary.get("idle_gaps", [])
    analytics.unmatched_gaps_count = len(idle_gaps)
    
    db.add(analytics)
    return analytics


def persist_raw_ocr_fields(db: Session, checklist_form: ChecklistForm, ocr_output: OCROutput, page_number: int = 0) -> None:
    """Persist raw OCR-extracted fields into RawOCRField table.

    Args:
        db: SQLAlchemy session
        checklist_form: ChecklistForm instance to link raw fields
        ocr_output: OCROutput model
        page_number: page number where fields were extracted (default 0)
    """
    if not checklist_form:
        return

    # Header fields
    header = ocr_output.header
    header_map = {
        "machine_id": getattr(header, "machine_id", None),
        "operator_name": getattr(header, "operator_name", None),
        "date": getattr(header, "date", None),
        "shift": getattr(header, "shift", None),
        "engine_hours_start": getattr(header, "engine_hours_start", None),
        "engine_hours_end": getattr(header, "engine_hours_end", None),
    }

    for fname, f in header_map.items():
        if not f:
            continue
        raw = RawOCRField(
            checklist_form_id=checklist_form.id,
            page_number=page_number,
            field_name=f"header.{fname}",
            raw_text=str(getattr(f, "value", "") or ""),
            normalized_text=None,
            confidence=getattr(f, "confidence", None),
            bbox=str(getattr(f, "bbox", None)) if getattr(f, "bbox", None) else None,
            row_index=None,
            column_name=None,
            is_table_cell=False,
            is_header=True,
        )
        db.add(raw)

    # Activity cells
    for activity in ocr_output.activities:
        row_idx = getattr(activity, "row_index", None)
        for col in ["activity_code", "from_time", "to_time", "location", "loads", "remarks"]:
            cell = getattr(activity, col, None)
            if not cell:
                continue
            raw = RawOCRField(
                checklist_form_id=checklist_form.id,
                page_number=page_number,
                field_name=f"activity.{col}",
                raw_text=str(getattr(cell, "value", "") or ""),
                normalized_text=None,
                confidence=getattr(cell, "confidence", None),
                bbox=str(getattr(cell, "bbox", None)) if getattr(cell, "bbox", None) else None,
                row_index=row_idx,
                column_name=col,
                is_table_cell=True,
                is_header=False,
            )
            db.add(raw)



def integrate_ocr_with_rule_engine(
    db: Session,
    ocr_output: OCROutput,
    checklist_form: Optional[ChecklistForm] = None,
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    """End-to-end integration of OCR output with rule engine and analytics.
    
    Orchestrates the complete pipeline:
    1. Convert OCR output to rule_engine format
    2. Process through rule engine (shift detection, time inference, classification)
    3. Compute machine analytics (availability, utilization, downtime, idle time)
    4. Persist timeline events to database
    5. Persist analytics summary to database
    6. Return complete results
    
    Args:
        db: SQLAlchemy database session
        ocr_output: OCR-extracted checklist data
        checklist_form: Optional existing checklist form to link events to
        reference_date: Optional date for shift window anchoring
        
    Returns:
        Dictionary with:
        - events: List of processed timeline events
        - summary: Timeline summary with metrics
        - analytics: Computed machine performance analytics
        - persisted_events: List of saved CleanedActivityEvent IDs (if persisted)
        - persisted_analytics: Saved ChecklistAnalytics ID (if persisted)
        - checklist_id: Associated checklist form ID (if persisted)
    """
    if reference_date is None:
        reference_date = date.today()

    # Step 1: Process OCR through rule engine
    timeline_result = process_ocr_with_rule_engine(ocr_output, reference_date)
    events = timeline_result.get("events", [])
    summary = timeline_result.get("summary", {})
    shift = summary.get("shift", "day")

    result = {
        "events": events,
        "summary": summary,
        "analytics": None,
        "persisted_events": [],
        "persisted_analytics": None,
        "checklist_id": None,
    }

    # Step 2: Compute analytics (always compute, even if not persisting)
    try:
        analytics_result = compute_machine_analytics(
            events=events,
            shift=shift,
            release_time=summary.get("machine_release_time"),
            start_engine_hours=checklist_form.start_engine_hours if checklist_form else None,
            end_engine_hours=checklist_form.end_engine_hours if checklist_form else None,
            start_transmission_hours=checklist_form.start_transmission_hours if checklist_form else None,
            end_transmission_hours=checklist_form.end_transmission_hours if checklist_form else None,
        )
        result["analytics"] = analytics_result
    except Exception as e:
        result["analytics_error"] = str(e)

    # Steps 3-5: Persist to database if checklist_form provided
    if checklist_form:
        result["checklist_id"] = checklist_form.id
        # Persist raw OCR fields first (so we keep original extraction data)
        try:
            persist_raw_ocr_fields(db, checklist_form, ocr_output)
        except Exception:
            # Do not fail the pipeline if raw persistence fails; record flag
            result["raw_persist_error"] = True
        
        # Persist timeline events
        persisted_events = persist_timeline_events(
            db, checklist_form.id, events
        )
        result["persisted_events"] = [e.id for e in persisted_events]

        # Persist summary/analytics — reuse already-computed analytics to avoid double computation
        persisted_analytics = persist_timeline_summary(
            db, checklist_form.id, summary, events, shift, checklist_form,
            machine_analytics=result.get("analytics"),
        )
        result["persisted_analytics"] = persisted_analytics.id
        # Note: caller (orchestrator) owns the commit; do not commit here

    return result


def extract_timeline_shifts(
    timeline_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract shift information from timeline result.
    
    Returns:
        Dictionary with shift, start time, end time, and change of shift flag
    """
    summary = timeline_result.get("summary", {})
    return {
        "shift": summary.get("shift"),
        "shift_start": summary.get("shift_start"),
        "shift_end": summary.get("shift_end"),
        "change_of_shift_detected": summary.get("change_of_shift_detected"),
    }


def extract_service_info(timeline_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract service and daily maintenance information from timeline.
    
    Returns:
        Dictionary with release time and service detection flags
    """
    summary = timeline_result.get("summary", {})
    return {
        "machine_release_time": summary.get("machine_release_time"),
        "daily_service_detected": summary.get("daily_service_detected"),
        "safety_meeting_detected": summary.get("safety_meeting_detected"),
    }


def extract_idle_analysis(timeline_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract idle time and gap analysis from timeline.
    
    Returns:
        Dictionary with total idle minutes and detailed idle gaps
    """
    summary = timeline_result.get("summary", {})
    return {
        "total_idle_minutes": summary.get("total_idle_minutes"),
        "idle_gaps": summary.get("idle_gaps", []),
        "idle_gap_count": len(summary.get("idle_gaps", [])),
    }


def extract_inferred_times(timeline_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract events where end times were inferred.
    
    Returns:
        List of events with inferred end times
    """
    events = timeline_result.get("events", [])
    return [
        {
            "row_index": e.get("row_index"),
            "activity_code": e.get("activity_code"),
            "start_time": e.get("start_time"),
            "end_time": e.get("end_time"),
            "inference_reasons": e.get("inference_reasons"),
        }
        for e in events
        if e.get("is_inferred_end_time")
    ]
