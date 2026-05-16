"""Pydantic schemas for checklist request and response models."""

from datetime import date, datetime
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict


class DailyCheckEntryCreate(BaseModel):
    """Schema for creating a daily check row."""

    row_index: Optional[int] = Field(default=None)
    check_item: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    raw_value: Optional[str] = Field(default=None)
    normalized_value: Optional[str] = Field(default=None)
    remarks: Optional[str] = Field(default=None)
    duration_minutes: Optional[float] = Field(default=None)
    is_service_action: Optional[bool] = Field(default=False)


class ActivityEntryCreate(BaseModel):
    """Schema for creating a raw activity row."""

    row_index: Optional[int] = Field(default=None)
    activity_code_raw: Optional[str] = Field(default=None)
    activity_code_normalized: Optional[str] = Field(default=None)
    from_time_raw: Optional[str] = Field(default=None)
    to_time_raw: Optional[str] = Field(default=None)
    workplace_raw: Optional[str] = Field(default=None)
    workplace_normalized: Optional[str] = Field(default=None)
    ore_waste_raw: Optional[str] = Field(default=None)
    ore_waste_normalized: Optional[str] = Field(default=None)
    loads_raw: Optional[str] = Field(default=None)
    loads_normalized: Optional[str] = Field(default=None)
    remarks_raw: Optional[str] = Field(default=None)
    remarks_normalized: Optional[str] = Field(default=None)
    confidence: Optional[float] = Field(default=None)
    raw_text: Optional[str] = Field(default=None)


class ChecklistFormCreate(BaseModel):
    """Schema for creating a checklist form record."""

    source_filename: Optional[str] = Field(default=None)
    document_date: Optional[date] = Field(default=None)
    shift: str = Field(..., description="Shift value must be 'day' or 'night'.")
    machine_number: Optional[str] = Field(default=None)
    operator_name: Optional[str] = Field(default=None)
    mine_number: Optional[str] = Field(default=None)
    permit_number: Optional[str] = Field(default=None)
    start_engine_hours: Optional[float] = Field(default=None)
    end_engine_hours: Optional[float] = Field(default=None)
    start_transmission_hours: Optional[float] = Field(default=None)
    end_transmission_hours: Optional[float] = Field(default=None)
    release_time: Optional[str] = Field(default=None)
    daily_checks: List[DailyCheckEntryCreate] = Field(default_factory=list)
    activity_entries: List[ActivityEntryCreate] = Field(default_factory=list)


class DailyCheckEntryResponse(DailyCheckEntryCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ActivityEntryResponse(ActivityEntryCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ChecklistFormResponse(BaseModel):
    """Schema returned for a checklist form."""

    id: int
    source_filename: Optional[str]
    document_date: Optional[date]
    shift: str
    machine_number: Optional[str]
    operator_name: Optional[str]
    mine_number: Optional[str]
    permit_number: Optional[str]
    start_engine_hours: Optional[float]
    end_engine_hours: Optional[float]
    start_transmission_hours: Optional[float]
    end_transmission_hours: Optional[float]
    release_time: Optional[str]
    shift_start: Optional[str]
    shift_end: Optional[str]
    daily_checks: List[DailyCheckEntryResponse] = Field(default_factory=list)
    activity_entries: List[ActivityEntryResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# OCR Output Schemas

class OCRField(BaseModel):
    """Base schema for OCR-extracted fields with confidence scoring."""
    value: Optional[str] = Field(default=None, description="Extracted text value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="OCR confidence score (0.0-1.0)")
    classification: Optional[str] = Field(default=None, description="Confidence classification: high|medium|low|unreadable")
    bbox: Optional[Tuple[int, int, int, int]] = Field(default=None, description="Bounding box (x,y,w,h) if available")
    # Parsing results
    original_value: Optional[str] = Field(default=None, description="Original OCR text before normalization")
    parsed_value: Optional[str] = Field(default=None, description="Parser-normalized value (if parsed)")
    confidence_adjusted_score: Optional[float] = Field(default=None, description="Adjusted confidence combining OCR and parsing confidence (0.0-1.0)")
    is_valid: Optional[bool] = Field(default=None, description="Whether the parsed value is considered valid by parser")


class OCRHeader(BaseModel):
    """OCR-extracted header information from checklist."""
    machine_id: OCRField = Field(..., description="Machine identifier (e.g., LOAD-001)")
    operator_name: OCRField = Field(..., description="Operator full name")
    date: OCRField = Field(..., description="Checklist date (YYYY-MM-DD format)")
    shift: OCRField = Field(..., description="Shift type (day/night)")
    engine_hours_start: OCRField = Field(..., description="Engine hours at shift start")
    engine_hours_end: OCRField = Field(..., description="Engine hours at shift end")


class OCRActivityRow(BaseModel):
    """OCR-extracted activity table row."""
    row_index: int = Field(..., ge=0, description="Row index in the activity table")
    activity_code: OCRField = Field(..., description="Activity code (e.g., 101, 300)")
    from_time: OCRField = Field(..., description="Start time (HH:MM format)")
    to_time: OCRField = Field(..., description="End time (HH:MM format)")
    location: OCRField = Field(..., description="Work location/area")
    loads: OCRField = Field(..., description="Number of loads")
    remarks: OCRField = Field(..., description="Additional remarks/notes")


class OCROutput(BaseModel):
    """Complete OCR extraction output for a checklist document."""
    document_id: str = Field(..., description="Unique document identifier")
    header: OCRHeader = Field(..., description="Extracted header information")
    activities: List[OCRActivityRow] = Field(default_factory=list, description="Extracted activity rows")
    processing_metadata: dict = Field(default_factory=dict, description="OCR processing metadata")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "checklist_2026_04_04_001",
                "header": {
                    "machine_id": {"value": "LOAD-001", "confidence": 0.95},
                    "operator_name": {"value": "Juan Perez", "confidence": 0.87},
                    "date": {"value": "2026-04-04", "confidence": 0.92},
                    "shift": {"value": "night", "confidence": 0.89},
                    "engine_hours_start": {"value": "1200.5", "confidence": 0.94},
                    "engine_hours_end": {"value": "1212.3", "confidence": 0.93}
                },
                "activities": [
                    {
                        "row_index": 0,
                        "activity_code": {"value": "101", "confidence": 0.91},
                        "from_time": {"value": "18:00", "confidence": 0.88},
                        "to_time": {"value": "19:30", "confidence": 0.85},
                        "location": {"value": "Pit A", "confidence": 0.76},
                        "loads": {"value": "3", "confidence": 0.82},
                        "remarks": {"value": "Normal", "confidence": 0.79}
                    }
                ],
                "processing_metadata": {
                    "ocr_engine": "TrOCR",
                    "processing_time_seconds": 2.3,
                    "total_confidence": 0.87
                }
            }
        }
    )
