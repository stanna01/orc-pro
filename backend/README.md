# ORC Pro Backend

## Overview
This backend implements the ORC Pro checklist extraction system using FastAPI, SQLAlchemy, and Pydantic.

## Implemented Features
- Checklist persistence model for page 1 and page 2 fields
- Activity entry normalization with raw OCR text support
- Timeline inference rules for missing `to_time` values
- Breakdown and equipment alert detection in extracted activity entries
- Rule engine for event classification and timeline processing
- Machine analytics module for performance metrics computation
- REST API routes for checklist creation, retrieval, update, delete, and OCR text extraction
- Unit tests covering checklist extraction and timeline inference logic

## Key Files
- `app/main.py` - FastAPI app startup and route registration
- `app/database.py` - SQLAlchemy engine and session management
- `app/models/checklist.py` - ORM models for checklists and activity entries
- `app/models/schemas.py` - Pydantic request/response schemas
- `app/services/checklist_service.py` - CRUD operations for checklists
- `app/services/checklist_extraction.py` - OCR text parsing and payload construction
- `app/services/timeline.py` - Timeline inference and analytics rules
- `app/services/rule_engine.py` - Event classification, shift reconstruction, safety detection
- `app/services/analytics.py` - Machine performance metrics computation
- `app/services/analytics_examples.py` - Usage examples and interpretation guide
- `app/ocr/pipeline.py` - Raw page text extraction helpers
- `app/routes/checklist.py` - Checklist API routes

## Change Log
- Added rule engine module (`app/services/rule_engine.py`):
  - Event classification into production, delay, breakdown, idle, service, safety_meeting
  - Change of shift detection
  - Safety meeting detection
  - Daily service and machine release time identification
  - Daily service max duration rule (service > 60 min → breakdown)
- Added machine analytics module (`app/services/analytics.py`):
  - Engine hours validation and delta computation
  - Availability breakdown: total, released, available, production, breakdown, service, safety, idle time
  - Performance ratios: availability, utilization, downtime, production, breakdown, idle, safety, effective availability
  - Per-shift window computation for night (18:00–06:00) and day (06:00–18:00) shifts
- Added analytics examples and interpretation guide
- Added raw OCR text extraction endpoint: `POST /checklists/extract`
- Implemented page 1 field extraction from raw OCR text
- Implemented activity entry parsing for the checklist timeline table
- Built `ChecklistFormCreate` payload assembly from OCR text
- Added timeline inference utilities for missing times and breakdown detection
- Added tests:
  - `backend/tests/test_checklist_extraction.py`
  - `backend/tests/test_timeline.py`

## How to Use
1. Start the app from `backend/`:
   ```bash
   uvicorn app.main:app --reload
   ```
2. Use the endpoint:
   - `POST /checklists/extract` with raw OCR text payload
   - `POST /checklists/` to save a checklist payload
   - `GET /checklists/{checklist_id}` to retrieve saved checklist data

## Notes
- This backend currently expects raw OCR text from scanned checklist forms.
- Time inference and normalization are designed for the two-page mining checklist form.
- The system is prepared for future extension to image OCR and advanced ML validation.
- See [ANALYTICS_FORMULAS.md](ANALYTICS_FORMULAS.md) for detailed performance metrics documentation.
- Run `python -m backend.app.services.analytics_examples` to see example analytics computations.
