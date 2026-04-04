"""SQLAlchemy models for the ORC Pro checklist domain."""

from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.app.database import Base


class ChecklistForm(Base):
    """Core checklist document entity."""

    __tablename__ = "checklist_forms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_filename = Column(String(256), nullable=True)
    document_date = Column(Date, nullable=True)
    shift = Column(String(16), nullable=False)
    machine_number = Column(String(64), nullable=True)
    operator_name = Column(String(128), nullable=True)
    mine_number = Column(String(64), nullable=True)
    permit_number = Column(String(64), nullable=True)
    start_engine_hours = Column(Float, nullable=True)
    end_engine_hours = Column(Float, nullable=True)
    start_transmission_hours = Column(Float, nullable=True)
    end_transmission_hours = Column(Float, nullable=True)
    release_time = Column(String(16), nullable=True)
    shift_start = Column(String(16), nullable=True)
    shift_end = Column(String(16), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    raw_fields = relationship("RawOCRField", back_populates="checklist_form", cascade="all, delete-orphan")
    daily_checks = relationship("DailyCheckEntry", back_populates="checklist_form", cascade="all, delete-orphan")
    activity_entries = relationship("ActivityEntry", back_populates="checklist_form", cascade="all, delete-orphan")
    cleaned_events = relationship("CleanedActivityEvent", back_populates="checklist_form", cascade="all, delete-orphan")
    analytics = relationship("ChecklistAnalytics", back_populates="checklist_form", uselist=False, cascade="all, delete-orphan")


class RawOCRField(Base):
    """Raw OCR extracted field or table cell."""

    __tablename__ = "raw_ocr_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    checklist_form_id = Column(Integer, ForeignKey("checklist_forms.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    field_name = Column(String(128), nullable=False)
    raw_text = Column(Text, nullable=False)
    normalized_text = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    bbox = Column(String(256), nullable=True)
    row_index = Column(Integer, nullable=True)
    column_name = Column(String(64), nullable=True)
    is_table_cell = Column(Boolean, nullable=False, default=False)
    is_header = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    checklist_form = relationship("ChecklistForm", back_populates="raw_fields")


class DailyCheckEntry(Base):
    """Engineering/maintenance daily check row."""

    __tablename__ = "daily_check_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    checklist_form_id = Column(Integer, ForeignKey("checklist_forms.id"), nullable=False)
    row_index = Column(Integer, nullable=True)
    check_item = Column(String(256), nullable=True)
    status = Column(String(64), nullable=True)
    raw_value = Column(Text, nullable=True)
    normalized_value = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)
    duration_minutes = Column(Float, nullable=True)
    is_service_action = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    checklist_form = relationship("ChecklistForm", back_populates="daily_checks")


class ActivityEntry(Base):
    """Raw activity table row from page 2."""

    __tablename__ = "activity_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    checklist_form_id = Column(Integer, ForeignKey("checklist_forms.id"), nullable=False)
    row_index = Column(Integer, nullable=True)
    activity_code_raw = Column(String(64), nullable=True)
    activity_code_normalized = Column(String(64), nullable=True)
    from_time_raw = Column(String(64), nullable=True)
    to_time_raw = Column(String(64), nullable=True)
    workplace_raw = Column(String(128), nullable=True)
    workplace_normalized = Column(String(128), nullable=True)
    ore_waste_raw = Column(String(64), nullable=True)
    ore_waste_normalized = Column(String(64), nullable=True)
    loads_raw = Column(String(64), nullable=True)
    loads_normalized = Column(String(64), nullable=True)
    remarks_raw = Column(Text, nullable=True)
    remarks_normalized = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    raw_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    checklist_form = relationship("ChecklistForm", back_populates="activity_entries")
    cleaned_event = relationship("CleanedActivityEvent", back_populates="activity_entry", uselist=False)


class CleanedActivityEvent(Base):
    """Interpreted checklist event after cleanup and inference."""

    __tablename__ = "cleaned_activity_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    checklist_form_id = Column(Integer, ForeignKey("checklist_forms.id"), nullable=False)
    activity_entry_id = Column(Integer, ForeignKey("activity_entries.id"), nullable=True)
    event_type = Column(String(64), nullable=False)
    activity_code = Column(String(64), nullable=True)
    start_time = Column(String(16), nullable=True)
    end_time = Column(String(16), nullable=True)
    duration_minutes = Column(Float, nullable=True)
    workplace = Column(String(128), nullable=True)
    ore_waste = Column(String(64), nullable=True)
    loads = Column(String(64), nullable=True)
    remarks = Column(Text, nullable=True)
    inference_reason = Column(String(128), nullable=True)
    is_inferred = Column(Boolean, default=False)
    is_ambiguous = Column(Boolean, default=False)
    confidence = Column(Float, nullable=True)
    source_page = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    checklist_form = relationship("ChecklistForm", back_populates="cleaned_events")
    activity_entry = relationship("ActivityEntry", back_populates="cleaned_event")


class ChecklistAnalytics(Base):
    """Computed operational analytics for a checklist."""

    __tablename__ = "checklist_analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    checklist_form_id = Column(Integer, ForeignKey("checklist_forms.id"), nullable=False, unique=True)
    total_shift_minutes = Column(Float, nullable=True)
    release_time = Column(String(16), nullable=True)
    release_delay_minutes = Column(Float, nullable=True)
    daily_service_duration_minutes = Column(Float, nullable=True)
    production_duration_minutes = Column(Float, nullable=True)
    breakdown_duration_minutes = Column(Float, nullable=True)
    idle_duration_minutes = Column(Float, nullable=True)
    availability_minutes = Column(Float, nullable=True)
    utilization_ratio = Column(Float, nullable=True)
    downtime_ratio = Column(Float, nullable=True)
    engine_hours_delta = Column(Float, nullable=True)
    engine_hours_valid = Column(Boolean, nullable=True)
    engine_hours_validation_message = Column(String(256), nullable=True)
    transmission_hours_delta = Column(Float, nullable=True)
    safety_meeting_detected = Column(Boolean, nullable=True)
    change_of_shift_detected = Column(Boolean, nullable=True)
    unmatched_gaps_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    checklist_form = relationship("ChecklistForm", back_populates="analytics")
