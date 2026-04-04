"""Pydantic schemas for checklist request and response models."""

from datetime import date, datetime
from typing import List, Optional
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
