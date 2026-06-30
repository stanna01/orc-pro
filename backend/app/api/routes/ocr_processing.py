"""API routes for OCR processing with rule engine and analytics integration."""

import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.models.schemas import OCROutput
from backend.app.models.checklist import ChecklistForm
from backend.app.services.ocr_rule_engine_integration import (
    integrate_ocr_with_rule_engine,
    process_ocr_with_rule_engine,
    extract_timeline_shifts,
    extract_service_info,
    extract_idle_analysis,
    extract_inferred_times,
)
from backend.app.services.analytics import compute_machine_analytics
from backend.app.services.orchestrator import create_orchestrator


router = APIRouter(prefix="/api/v1/ocr", tags=["ocr"])


# Response schemas
class TimelineEventResponse(dict):
    """Response model for a single timeline event."""
    pass


class TimelineSummaryResponse:
    """Response model for timeline summary."""
    shift: str
    shift_start: str
    shift_end: str
    total_idle_minutes: float
    idle_gaps: list
    change_of_shift_detected: bool
    daily_service_detected: bool
    safety_meeting_detected: bool
    machine_release_time: Optional[str]


@router.post("/process", status_code=status.HTTP_200_OK)
async def process_ocr_output(
    ocr_output: OCROutput = Body(..., description="OCR extraction output from ML pipeline"),
    reference_date: Optional[date] = Body(None, description="Optional date for shift window anchoring"),
    persist: bool = Body(False, description="Whether to persist results to database"),
    checklist_id: Optional[int] = Body(None, description="Optional checklist form ID to link results"),
    db: Session = Depends(get_session),
) -> dict:
    """Process OCR output through rule engine for timeline event extraction.
    
    Applies business logic:
    - Shift detection (day/night)
    - Time inference for missing end times
    - Event classification (production, breakdown, service, delay, safety, idle)
    - Daily service rule application
    - Idle time computation and gap analysis
    
    Args:
        ocr_output: OCR extraction output
        reference_date: Optional reference date for shift anchoring (defaults to today)
        persist: Whether to save results to database
        checklist_id: Optional checklist form ID to associate events with
        db: Database session
        
    Returns:
        Timeline processing result with events and summary metrics
    """
    if reference_date is None:
        reference_date = date.today()
    
    # Get checklist form if ID provided
    checklist_form = None
    if persist and checklist_id:
        checklist_form = db.query(ChecklistForm).filter_by(id=checklist_id).first()
        if not checklist_form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Checklist form with ID {checklist_id} not found"
            )
    
    # Process OCR through rule engine
    try:
        result = integrate_ocr_with_rule_engine(
            db=db,
            ocr_output=ocr_output,
            checklist_form=checklist_form if persist else None,
            reference_date=reference_date,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rule engine processing failed: {str(e)}"
        )
    
    return {
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": result,
    }


@router.post("/analyze", status_code=status.HTTP_200_OK)
async def analyze_ocr_output(
    ocr_output: OCROutput = Body(...),
    reference_date: Optional[date] = Body(None),
) -> dict:
    """Analyze OCR output with computed analytics without persisting to database.
    
    Computes machine performance metrics including availability, utilization,
    downtime, and idle time, useful for quick analysis and validation of OCR
    extraction quality before committing to database.
    
    Args:
        ocr_output: OCR extraction output
        reference_date: Optional reference date
        
    Returns:
        Timeline analysis with extracted metrics and machine analytics
    """
    if reference_date is None:
        reference_date = date.today()
    
    timeline_result = process_ocr_with_rule_engine(ocr_output, reference_date)
    events = timeline_result.get("events", [])
    summary = timeline_result.get("summary", {})
    shift = summary.get("shift", "day")
    
    # Compute analytics
    analytics = None
    analytics_error = None
    try:
        analytics = compute_machine_analytics(
            events=events,
            shift=shift,
            release_time=summary.get("machine_release_time"),
        )
    except Exception as e:
        analytics_error = str(e)
    
    return {
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "shifts": extract_timeline_shifts(timeline_result),
        "service": extract_service_info(timeline_result),
        "idle_analysis": extract_idle_analysis(timeline_result),
        "inferred_times": extract_inferred_times(timeline_result),
        "analytics": analytics,
        "analytics_error": analytics_error,
        "full_timeline": timeline_result,
    }


@router.post("/debug/shift-detection", status_code=status.HTTP_200_OK)
async def debug_shift_detection(
    ocr_output: OCROutput = Body(...),
) -> dict:
    """Debug endpoint for shift detection logic.
    
    Returns detailed information about shift detection.
    """
    timeline_result = process_ocr_with_rule_engine(ocr_output)
    shifts = extract_timeline_shifts(timeline_result)
    
    return {
        "success": True,
        "shift_detection": shifts,
        "activities_count": len(ocr_output.activities),
        "events_count": len(timeline_result.get("events", [])),
    }


@router.post("/debug/time-inference", status_code=status.HTTP_200_OK)
async def debug_time_inference(
    ocr_output: OCROutput = Body(...),
) -> dict:
    """Debug endpoint for time inference logic.
    
    Identifies which events had missing end times and were inferred.
    """
    timeline_result = process_ocr_with_rule_engine(ocr_output)
    inferred = extract_inferred_times(timeline_result)
    
    return {
        "success": True,
        "total_inferred": len(inferred),
        "inferred_times": inferred,
    }


@router.post("/debug/idle-computation", status_code=status.HTTP_200_OK)
async def debug_idle_computation(
    ocr_output: OCROutput = Body(...),
    reference_date: Optional[date] = Body(None),
) -> dict:
    """Debug endpoint for idle time computation.
    
    Shows detailed idle gaps and idle time analysis.
    """
    if reference_date is None:
        reference_date = date.today()
    
    timeline_result = process_ocr_with_rule_engine(ocr_output, reference_date)
    idle_analysis = extract_idle_analysis(timeline_result)
    
    return {
        "success": True,
        "idle_analysis": idle_analysis,
        "shift_info": extract_timeline_shifts(timeline_result),
    }


@router.post("/debug/service-detection", status_code=status.HTTP_200_OK)
async def debug_service_detection(
    ocr_output: OCROutput = Body(...),
) -> dict:
    """Debug endpoint for daily service and related logic.
    
    Shows service detection, release time computation, and event classification.
    """
    timeline_result = process_ocr_with_rule_engine(ocr_output)
    service = extract_service_info(timeline_result)
    
    return {
        "success": True,
        "service_info": service,
        "events": timeline_result.get("events", []),
    }


@router.post("/debug/analytics", status_code=status.HTTP_200_OK)
async def debug_analytics(
    ocr_output: OCROutput = Body(...),
) -> dict:
    """Debug endpoint for machine performance analytics.
    
    Computes and displays detailed analytics including:
    - Availability breakdown (production, breakdown, service, safety, idle)
    - Performance ratios (availability, utilization, downtime)
    - Engine hours validation
    """
    timeline_result = process_ocr_with_rule_engine(ocr_output)
    events = timeline_result.get("events", [])
    summary = timeline_result.get("summary", {})
    shift = summary.get("shift", "day")
    
    try:
        analytics = compute_machine_analytics(
            events=events,
            shift=shift,
            release_time=summary.get("machine_release_time"),
        )
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
    
    return {
        "success": True,
        "shift": shift,
        "availability_breakdown": analytics.get("availability_breakdown", {}),
        "performance_ratios": analytics.get("performance_ratios", {}),
        "engine_hours_metrics": analytics.get("engine_hours_metrics", {}),
        "summary": {
            "total_events": len(events),
            "shift_start": summary.get("shift_start"),
            "shift_end": summary.get("shift_end"),
            "release_time": summary.get("machine_release_time"),
        },
    }


@router.post("/upload-pdf", status_code=status.HTTP_200_OK)
async def process_checklist_pdf(
    file: UploadFile = File(..., description="PDF checklist file to process"),
    reference_date: Optional[date] = Body(None, description="Optional reference date for shift anchoring"),
    db: Session = Depends(get_session),
) -> dict:
    """Upload and process a scanned checklist PDF end-to-end.
    
    Orchestrates complete pipeline:
    1. PDF extraction (convert to images)
    2. Preprocessing (enhance image quality)
    3. OCR extraction (run TrOCR)
    4. Parsing (structure extracted text)
    5. Rule engine (apply business logic)
    6. Analytics (compute metrics)
    7. Database (persist results)
    
    Args:
        file: PDF file upload
        reference_date: Optional reference date (defaults to today)
        db: Database session
        
    Returns:
        Complete processing result with extracted data, timeline, and analytics
    """
    if reference_date is None:
        reference_date = date.today()
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a PDF"
        )
    
    # Save uploaded file temporarily
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            contents = await file.read()
            tmp.write(contents)
            temp_file = tmp.name
        
        # Process PDF through orchestrator
        orchestrator = create_orchestrator(db=db)
        result = orchestrator.process_pdf(
            pdf_path=temp_file,
            reference_date=reference_date,
            persist=True
        )
        
        return {
            "success": result["success"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "filename": file.filename,
            "document_id": result.get("document_id"),
            "pages_processed": result.get("pages_processed", 0),
            "activities_extracted": result.get("activities_extracted", 0),
            "timeline_events": result.get("timeline_events", []),
            "timeline_summary": result.get("timeline_summary"),
            "analytics": result.get("analytics"),
            "persisted": result.get("persisted"),
            "processing_log": result.get("processing_log", []),
            "error": result.get("error"),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF processing failed: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if temp_file and Path(temp_file).exists():
            Path(temp_file).unlink()


@router.get("/checklist/{checklist_id}", status_code=status.HTTP_200_OK)
async def get_checklist(
    checklist_id: int,
    db: Session = Depends(get_session),
) -> dict:
    """Retrieve complete checklist with timeline events and metadata.
    
    Args:
        checklist_id: Checklist form ID
        db: Database session
        
    Returns:
        Checklist with all related data (timeline events, analytics metadata)
    """
    checklist_form = db.query(ChecklistForm).filter_by(id=checklist_id).first()
    
    if not checklist_form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checklist with ID {checklist_id} not found"
        )
    
    # Get related timeline events
    from backend.app.models.checklist import CleanedActivityEvent
    events = db.query(CleanedActivityEvent).filter_by(
        checklist_form_id=checklist_id
    ).all()
    
    # Get related analytics
    from backend.app.models.checklist import ChecklistAnalytics
    analytics = db.query(ChecklistAnalytics).filter_by(
        checklist_form_id=checklist_id
    ).first()
    
    # Format timeline events
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
        })
    
    # Format analytics if available
    analytics_data = None
    if analytics:
        analytics_data = {
            "id": analytics.id,
            "total_shift_minutes": analytics.total_shift_minutes,
            "production_duration_minutes": analytics.production_duration_minutes,
            "breakdown_duration_minutes": analytics.breakdown_duration_minutes,
            "idle_duration_minutes": analytics.idle_duration_minutes,
            "daily_service_duration_minutes": analytics.daily_service_duration_minutes,
            "availability_minutes": analytics.availability_minutes,
            "utilization_ratio": analytics.utilization_ratio,
            "downtime_ratio": analytics.downtime_ratio,
            "engine_hours_delta": analytics.engine_hours_delta,
            "transmission_hours_delta": analytics.transmission_hours_delta,
            "engine_hours_valid": analytics.engine_hours_valid,
            "safety_meeting_detected": analytics.safety_meeting_detected,
            "change_of_shift_detected": analytics.change_of_shift_detected,
            "unmatched_gaps_count": analytics.unmatched_gaps_count,
        }
    
    return {
        "success": True,
        "checklist": {
            "id": checklist_form.id,
            "source_filename": checklist_form.source_filename,
            "document_date": checklist_form.document_date.isoformat() if checklist_form.document_date else None,
            "shift": checklist_form.shift,
            "machine_number": checklist_form.machine_number,
            "operator_name": checklist_form.operator_name,
            "start_engine_hours": checklist_form.start_engine_hours,
            "end_engine_hours": checklist_form.end_engine_hours,
            "start_transmission_hours": checklist_form.start_transmission_hours,
            "end_transmission_hours": checklist_form.end_transmission_hours,
            "release_time": checklist_form.release_time,
            "shift_start": checklist_form.shift_start,
            "shift_end": checklist_form.shift_end,
            "created_at": checklist_form.created_at.isoformat() if checklist_form.created_at else None,
        },
        "timeline_events": timeline_events,
        "analytics": analytics_data,
        "event_count": len(timeline_events),
    }


@router.get("/analytics/{checklist_id}", status_code=status.HTTP_200_OK)
async def get_analytics(
    checklist_id: int,
    db: Session = Depends(get_session),
) -> dict:
    """Retrieve computed analytics for a checklist.
    
    Args:
        checklist_id: Checklist form ID
        db: Database session
        
    Returns:
        Detailed analytics with availability, utilization, downtime metrics
    """
    from backend.app.models.checklist import ChecklistAnalytics
    
    analytics = db.query(ChecklistAnalytics).filter_by(
        checklist_form_id=checklist_id
    ).first()
    
    if not analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analytics not found for checklist {checklist_id}"
        )
    
    # Get checklist for reference
    checklist_form = db.query(ChecklistForm).filter_by(id=checklist_id).first()
    
    return {
        "success": True,
        "analytics_id": analytics.id,
        "checklist_id": checklist_id,
        "document": {
            "filename": checklist_form.source_filename if checklist_form else None,
            "date": checklist_form.document_date.isoformat() if checklist_form and checklist_form.document_date else None,
            "shift": checklist_form.shift if checklist_form else None,
            "machine": checklist_form.machine_number if checklist_form else None,
            "operator": checklist_form.operator_name if checklist_form else None,
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
            "effectiveness_ratio": (
                (analytics.availability_minutes - analytics.idle_duration_minutes) / analytics.total_shift_minutes
                if analytics.total_shift_minutes and analytics.availability_minutes is not None and analytics.idle_duration_minutes is not None else None
            ),
        },
        "engine_metrics": {
            "engine_hours_delta": analytics.engine_hours_delta,
            "transmission_hours_delta": analytics.transmission_hours_delta,
            "valid": analytics.engine_hours_valid,
            "validation_message": analytics.engine_hours_validation_message,
        },
        "event_flags": {
            "safety_meeting_detected": analytics.safety_meeting_detected,
            "change_of_shift_detected": analytics.change_of_shift_detected,
            "unmatched_gaps_count": analytics.unmatched_gaps_count,
        },
        "created_at": analytics.created_at.isoformat() if analytics.created_at else None,
    }


@router.post("/upload-and-process", status_code=status.HTTP_200_OK)
async def upload_and_process_checklist(
    file: UploadFile = File(..., description="PDF checklist file to process"),
    reference_date: Optional[date] = Body(None, description="Optional reference date"),
    db: Session = Depends(get_session),
) -> dict:
    """Upload and process a checklist PDF - returns complete results.
    
    Alias for /upload-pdf endpoint with slightly different response structure.
    Processes PDF end-to-end and returns timeline + analytics.
    
    Args:
        file: PDF file upload
        reference_date: Optional reference date (defaults to today)
        db: Database session
        
    Returns:
        Complete processing result with checklist ID, timeline events, and analytics
    """
    if reference_date is None:
        reference_date = date.today()
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a PDF"
        )
    
    # Save uploaded file temporarily
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            contents = await file.read()
            tmp.write(contents)
            temp_file = tmp.name
        
        # Process PDF through orchestrator
        orchestrator = create_orchestrator(db=db)
        result = orchestrator.process_pdf(
            pdf_path=temp_file,
            reference_date=reference_date,
            persist=True
        )
        
        if result["success"]:
            # Get the persisted checklist and analytics
            checklist_id = result.get("persisted", {}).get("checklist_id")
            
            if checklist_id:
                # Fetch fresh data from database
                checklist_form = db.query(ChecklistForm).filter_by(id=checklist_id).first()
                
                from backend.app.models.checklist import CleanedActivityEvent, ChecklistAnalytics
                events = db.query(CleanedActivityEvent).filter_by(
                    checklist_form_id=checklist_id
                ).all()
                analytics = db.query(ChecklistAnalytics).filter_by(
                    checklist_form_id=checklist_id
                ).first()
                
                # Format response
                timeline_events = [
                    {
                        "id": event.id,
                        "event_type": event.event_type,
                        "activity_code": event.activity_code,
                        "start_time": event.start_time,
                        "end_time": event.end_time,
                        "duration_minutes": event.duration_minutes,
                        "is_inferred": event.is_inferred,
                    }
                    for event in events
                ]
                
                analytics_data = {
                    "utilization_ratio": analytics.utilization_ratio,
                    "downtime_ratio": analytics.downtime_ratio,
                    "production_minutes": analytics.production_duration_minutes,
                    "breakdown_minutes": analytics.breakdown_duration_minutes,
                    "idle_minutes": analytics.idle_duration_minutes,
                    "availability_minutes": analytics.availability_minutes,
                } if analytics else None
                
                return {
                    "success": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "filename": file.filename,
                    "checklist_id": checklist_id,
                    "document_id": result.get("document_id"),
                    "pages_processed": result.get("pages_processed", 0),
                    "activities_extracted": result.get("activities_extracted", 0),
                    "timeline_events": timeline_events,
                    "analytics": analytics_data,
                    "database_ids": {
                        "checklist_form_id": checklist_id,
                        "event_ids": result.get("persisted", {}).get("event_ids", []),
                        "analytics_id": result.get("persisted", {}).get("analytics_id"),
                    },
                }
        
        # Failed processing
        return {
            "success": False,
            "error": result.get("error"),
            "processing_log": result.get("processing_log", []),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF processing failed: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if temp_file and Path(temp_file).exists():
            Path(temp_file).unlink()
