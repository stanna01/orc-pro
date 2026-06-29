"""API routes for checklist management and retrieval."""

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.models.checklist import ChecklistAnalytics, ChecklistForm, CleanedActivityEvent
from backend.app.models.schemas import ChecklistFormCreate, ChecklistFormResponse, OCROutput
from backend.app.services.checklist_extraction import build_checklist_payload
from backend.app.services.checklist_service import (
    create_checklist_form,
    get_checklist_form,
    list_checklist_forms,
)

router = APIRouter(prefix="/api/v1/checklists", tags=["checklists"])


# ---------------------------------------------------------------------------
# Write endpoints
# ---------------------------------------------------------------------------

@router.post("/", response_model=ChecklistFormResponse, status_code=status.HTTP_201_CREATED)
def create_checklist(
    checklist: ChecklistFormCreate,
    db: Session = Depends(get_session),
) -> ChecklistFormResponse:
    """Create a new checklist form."""
    return create_checklist_form(db=db, payload=checklist)


@router.post("/extract", response_model=ChecklistFormCreate, status_code=status.HTTP_200_OK)
def extract_checklist(
    ocr_data: OCROutput = Body(..., description="OCR extraction output for the checklist document."),
) -> ChecklistFormCreate:
    """Parse OCR output into a structured checklist payload."""
    try:
        return build_checklist_payload(ocr_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

@router.get("/{checklist_id}", status_code=status.HTTP_200_OK)
async def get_checklist(
    checklist_id: int,
    include_events: bool = True,
    include_analytics: bool = True,
    db: Session = Depends(get_session),
) -> dict:
    """Retrieve complete checklist with optional timeline events and analytics.
    
    Args:
        checklist_id: Checklist form ID
        include_events: Include timeline events in response (default: true)
        include_analytics: Include analytics in response (default: true)
        db: Database session
        
    Returns:
        Checklist with related data (timeline events, analytics)
    """
    # Get checklist
    checklist_form = db.query(ChecklistForm).filter_by(id=checklist_id).first()
    
    if not checklist_form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checklist with ID {checklist_id} not found"
        )
    
    # Prepare base response
    response = {
        "success": True,
        "checklist": {
            "id": checklist_form.id,
            "source_filename": checklist_form.source_filename,
            "document_date": checklist_form.document_date.isoformat() if checklist_form.document_date else None,
            "shift": checklist_form.shift,
            "machine_number": checklist_form.machine_number,
            "operator_name": checklist_form.operator_name,
            "mine_number": checklist_form.mine_number,
            "permit_number": checklist_form.permit_number,
            "start_engine_hours": checklist_form.start_engine_hours,
            "end_engine_hours": checklist_form.end_engine_hours,
            "start_transmission_hours": checklist_form.start_transmission_hours,
            "end_transmission_hours": checklist_form.end_transmission_hours,
            "release_time": checklist_form.release_time,
            "shift_start": checklist_form.shift_start,
            "shift_end": checklist_form.shift_end,
            "created_at": checklist_form.created_at.isoformat() if checklist_form.created_at else None,
            "updated_at": checklist_form.updated_at.isoformat() if checklist_form.updated_at else None,
        },
    }
    
    # Add timeline events if requested
    if include_events:
        events = db.query(CleanedActivityEvent).filter_by(
            checklist_form_id=checklist_id
        ).all()
        
        timeline_events = []
        for event in events:
            timeline_events.append({
                "id": event.id,
                "event_type": event.event_type,
                "activity_code": event.activity_code,
                "start_time": event.start_time,
                "end_time": event.end_time,
                "duration_minutes": event.duration_minutes,
                "workplace": event.workplace,
                "ore_waste": event.ore_waste,
                "loads": event.loads,
                "remarks": event.remarks,
                "is_inferred": event.is_inferred,
                "is_ambiguous": event.is_ambiguous,
                "inference_reason": event.inference_reason,
                "confidence": event.confidence,
            })
        
        response["timeline_events"] = timeline_events
        response["event_count"] = len(timeline_events)
    
    # Add analytics if requested
    if include_analytics:
        analytics = db.query(ChecklistAnalytics).filter_by(
            checklist_form_id=checklist_id
        ).first()
        
        if analytics:
            response["analytics"] = {
                "id": analytics.id,
                "total_shift_minutes": analytics.total_shift_minutes,
                "availability": {
                    "production_minutes": analytics.production_duration_minutes,
                    "breakdown_minutes": analytics.breakdown_duration_minutes,
                    "service_minutes": analytics.daily_service_duration_minutes,
                    "idle_minutes": analytics.idle_duration_minutes,
                    "available_minutes": analytics.availability_minutes,
                },
                "ratios": {
                    "utilization_ratio": analytics.utilization_ratio,
                    "downtime_ratio": analytics.downtime_ratio,
                },
                "engine": {
                    "hours_delta": analytics.engine_hours_delta,
                    "hours_valid": analytics.engine_hours_valid,
                    "transmission_hours_delta": analytics.transmission_hours_delta,
                },
                "flags": {
                    "safety_meeting_detected": analytics.safety_meeting_detected,
                    "change_of_shift_detected": analytics.change_of_shift_detected,
                    "unmatched_gaps_count": analytics.unmatched_gaps_count,
                },
                "created_at": analytics.created_at.isoformat() if analytics.created_at else None,
            }
        else:
            response["analytics"] = None
    
    return response


@router.get("/{checklist_id}/analytics", status_code=status.HTTP_200_OK)
async def get_checklist_analytics(
    checklist_id: int,
    db: Session = Depends(get_session),
) -> dict:
    """Retrieve detailed analytics for a specific checklist.
    
    Args:
        checklist_id: Checklist form ID
        db: Database session
        
    Returns:
        Detailed analytics with availability breakdown, ratios, and flags
    """
    # Get checklist for validation
    checklist_form = db.query(ChecklistForm).filter_by(id=checklist_id).first()
    
    if not checklist_form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checklist with ID {checklist_id} not found"
        )
    
    # Get analytics
    analytics = db.query(ChecklistAnalytics).filter_by(
        checklist_form_id=checklist_id
    ).first()
    
    if not analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analytics not found for checklist {checklist_id}"
        )
    
    return {
        "success": True,
        "analytics_id": analytics.id,
        "checklist_id": checklist_id,
        "document": {
            "filename": checklist_form.source_filename,
            "date": checklist_form.document_date.isoformat() if checklist_form.document_date else None,
            "shift": checklist_form.shift,
            "machine": checklist_form.machine_number,
            "operator": checklist_form.operator_name,
        },
        "availability_breakdown": {
            "total_shift_minutes": analytics.total_shift_minutes,
            "production_minutes": analytics.production_duration_minutes,
            "breakdown_minutes": analytics.breakdown_duration_minutes,
            "service_minutes": analytics.daily_service_duration_minutes,
            "idle_minutes": analytics.idle_duration_minutes,
            "available_minutes": analytics.availability_minutes,
        },
        "performance_ratios": {
            "utilization_ratio": analytics.utilization_ratio,
            "downtime_ratio": analytics.downtime_ratio,
            "effective_availability": (
                (analytics.availability_minutes - analytics.idle_duration_minutes) / analytics.total_shift_minutes
                if analytics.total_shift_minutes and analytics.availability_minutes is not None and analytics.idle_duration_minutes is not None else None
            ),
        },
        "engine_metrics": {
            "start_hours": checklist_form.start_engine_hours,
            "end_hours": checklist_form.end_engine_hours,
            "delta": analytics.engine_hours_delta,
            "valid": analytics.engine_hours_valid,
            "validation_message": analytics.engine_hours_validation_message,
            "transmission_hours_delta": analytics.transmission_hours_delta,
        },
        "event_flags": {
            "safety_meeting_detected": analytics.safety_meeting_detected,
            "change_of_shift_detected": analytics.change_of_shift_detected,
            "unmatched_gaps_count": analytics.unmatched_gaps_count,
        },
        "release_time": analytics.release_time,
        "release_delay_minutes": analytics.release_delay_minutes,
        "created_at": analytics.created_at.isoformat() if analytics.created_at else None,
    }


@router.get("/{checklist_id}/timeline", status_code=status.HTTP_200_OK)
async def get_checklist_timeline(
    checklist_id: int,
    only_inferred: bool = False,
    db: Session = Depends(get_session),
) -> dict:
    """Retrieve timeline events for a checklist.
    
    Args:
        checklist_id: Checklist form ID
        only_inferred: Return only inferred events (default: false)
        db: Database session
        
    Returns:
        Timeline events with detailed information
    """
    # Validate checklist exists
    checklist_form = db.query(ChecklistForm).filter_by(id=checklist_id).first()
    
    if not checklist_form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checklist with ID {checklist_id} not found"
        )
    
    # Get events
    query = db.query(CleanedActivityEvent).filter_by(checklist_form_id=checklist_id)
    
    if only_inferred:
        query = query.filter_by(is_inferred=True)
    
    events = query.all()
    
    # Format events
    timeline_events = []
    for event in events:
        timeline_events.append({
            "id": event.id,
            "event_type": event.event_type,
            "activity_code": event.activity_code,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "duration_minutes": event.duration_minutes,
            "workplace": event.workplace,
            "ore_waste": event.ore_waste,
            "loads": event.loads,
            "remarks": event.remarks,
            "is_inferred": event.is_inferred,
            "is_ambiguous": event.is_ambiguous,
            "inference_reason": event.inference_reason,
            "confidence": event.confidence,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        })
    
    # Calculate statistics
    total_duration = sum(e.get("duration_minutes", 0) for e in timeline_events if e.get("duration_minutes"))
    event_types = {}
    for event in timeline_events:
        event_type = event["event_type"]
        event_types[event_type] = event_types.get(event_type, 0) + 1
    
    return {
        "success": True,
        "checklist_id": checklist_id,
        "timeline_events": timeline_events,
        "summary": {
            "total_events": len(timeline_events),
            "inferred_count": sum(1 for e in timeline_events if e["is_inferred"]),
            "ambiguous_count": sum(1 for e in timeline_events if e["is_ambiguous"]),
            "total_duration_minutes": total_duration,
            "event_types": event_types,
        },
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_checklists(
    limit: int = 50,
    offset: int = 0,
    shift: Optional[str] = None,
    machine_number: Optional[str] = None,
    operator_name: Optional[str] = None,
    db: Session = Depends(get_session),
) -> dict:
    """List all checklists with optional filtering.
    
    Args:
        limit: Maximum number of results (default: 50)
        offset: Number of results to skip (default: 0)
        shift: Filter by shift (day/night)
        machine_number: Filter by machine number
        operator_name: Filter by operator name
        db: Database session
        
    Returns:
        List of checklists with metadata
    """
    # Build query
    query = db.query(ChecklistForm)
    
    if shift:
        query = query.filter_by(shift=shift)
    if machine_number:
        query = query.filter_by(machine_number=machine_number)
    if operator_name:
        query = query.filter(ChecklistForm.operator_name.ilike(f"%{operator_name}%"))
    
    # Get total count
    total_count = query.count()
    
    # Get paginated results
    checklists = query.order_by(ChecklistForm.created_at.desc()).offset(offset).limit(limit).all()

    # Batch-load analytics to avoid N+1
    checklist_ids = [form.id for form in checklists]
    analytics_map = {
        a.checklist_form_id: a
        for a in db.query(ChecklistAnalytics).filter(
            ChecklistAnalytics.checklist_form_id.in_(checklist_ids)
        ).all()
    } if checklist_ids else {}

    # Format results
    checklist_list = []
    for form in checklists:
        analytics = analytics_map.get(form.id)
        
        checklist_list.append({
            "id": form.id,
            "source_filename": form.source_filename,
            "document_date": form.document_date.isoformat() if form.document_date else None,
            "shift": form.shift,
            "machine_number": form.machine_number,
            "operator_name": form.operator_name,
            "has_analytics": analytics is not None,
            "utilization_ratio": analytics.utilization_ratio if analytics else None,
            "created_at": form.created_at.isoformat() if form.created_at else None,
        })
    
    return {
        "success": True,
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "returned": len(checklist_list),
        "checklists": checklist_list,
    }
