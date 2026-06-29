# OCR Rule Engine Integration

## Overview

The OCR Rule Engine Integration service bridges the OCR extraction pipeline with business logic processing. It converts parsed checklist data (after postprocessing and validation) into structured timeline events with automated inference and classification.

## Architecture

```
OCR Pipeline (TrOCR)
        ↓
OCROutput (Pydantic schema)
        ↓
postprocessing.py  — character correction, code validation, time normalisation
        ↓
validator.py       — time ordering, shift boundaries, overlap detection
        ↓
ocr_rule_engine_integration.py
        ↓
rule_engine.py
        ↓
Timeline Events + Summary Metrics
        ↓
CleanedActivityEvent (Database)
ChecklistAnalytics (Database)
```

## Key Features

### 1. Shift Detection ✓
Automatically detects day vs. night shifts based on:
- Header shift field
- Activity times (if header shift is ambiguous)
- Time windows: Day (6:00-18:00), Night (18:00-6:00)

### 2. Time Inference ✓
Infers missing end times using:
- Next event's start time (primary strategy)
- Shift end time (fallback)
- Marks events as ambiguous if inference fails

### 3. Daily Service Logic ✓
- Detects service activities (activity code 300)
- Applies rule: If service duration > 60 minutes, classify as breakdown
- Computes machine release time from latest service end time

### 4. Event Classification ✓
Classifies events into types using a scoring system (see Processing Rules below):
- **production**: Standard work activities
- **service**: Maintenance/daily checks
- **breakdown**: Equipment failures or extended service
- **delay**: Waiting/queue/standby
- **safety_meeting**: Pre-shift meetings
- **idle**: Calendar gaps within the shift window (inserted by rule engine, not a raw event type)

### 5. Idle Time Computation ✓
Calculates idle gaps as calendar gaps within the shift window (`_compute_idle_gaps`):
- Gaps are computed from shift_start to shift_end using `_anchor_datetime`
- Returns gap start/end times and duration in minutes

## API Endpoints

### Primary Endpoint
```
POST /api/v1/ocr/process
```
- **Description**: Process OCR output through rule engine with optional database persistence
- **Parameters**:
  - `ocr_output` (OCROutput): OCR extraction result
  - `reference_date` (date, optional): Shift window anchor date
  - `persist` (bool, optional): Save results to database
  - `checklist_id` (int, optional): Link to existing checklist form
- **Returns**: Timeline events, summary metrics, database IDs if persisted

**Example Request**:
```json
{
  "ocr_output": {
    "document_id": "checklist_2026_04_04_001",
    "header": {
      "shift": {"value": "night", "confidence": 0.90},
      ...
    },
    "activities": [...]
  },
  "reference_date": "2026-04-04",
  "persist": true,
  "checklist_id": 42
}
```

### Analysis Endpoint
```
POST /api/v1/ocr/analyze
```
- **Description**: Analyze OCR without persisting (read-only)
- **Returns**: Timeline events + extracted metrics (shifts, service, idle, inferred times)

### Debug Endpoints
```
POST /api/v1/ocr/debug/shift-detection
POST /api/v1/ocr/debug/time-inference
POST /api/v1/ocr/debug/idle-computation
POST /api/v1/ocr/debug/service-detection
```
- Isolated testing of specific logic components

## Integration Flow

### Step 1: Convert OCR Format
```python
# Input: OCRField objects with confidence scores
ocr_output = OCROutput(
    header=OCRHeader(
        shift=OCRField(value="night", confidence=0.90),
        ...
    ),
    activities=[
        OCRActivityRow(
            from_time=OCRField(value="18:00", confidence=0.95),
            to_time=OCRField(value="", confidence=0.0),  # Missing!
            ...
        ),
        ...
    ]
)

# Step 1: Convert to rule_engine format
rule_engine_input = {
    "header": {"shift": {"value": "night"}},
    "activities": [
        {
            "from_time": {"value": "18:00"},
            "to_time": None,  # Will be inferred
            ...
        },
        ...
    ]
}
```

### Step 2: Process Through Rule Engine
```python
timeline_result = process_checklist_timeline(
    rule_engine_input,
    reference_date=date(2026, 4, 4)
)

# Returns:
{
    "events": [
        {
            "activity_code": "101",
            "event_type": "production",
            "start_time": "18:00",
            "end_time": "18:30",
            "duration_minutes": 30.0,
            "is_inferred_end_time": false,
            ...
        },
        {
            "activity_code": "101",
            "event_type": "production",
            "start_time": "18:45",
            "end_time": "22:00",  # INFERRED
            "duration_minutes": 195.0,
            "is_inferred_end_time": true,
            "inference_reasons": ["inferred_from_next_event"],
            ...
        },
        ...
    ],
    "summary": {
        "shift": "night",
        "shift_start": "18:00",
        "shift_end": "06:00",
        "total_idle_minutes": 390.0,
        "idle_gaps": [
            {
                "start_time": "23:30",
                "end_time": "06:00",
                "duration_minutes": 390.0
            }
        ],
        "change_of_shift_detected": false,
        "daily_service_detected": false,
        "safety_meeting_detected": false,
        "machine_release_time": null,
        "event_counts": {
            "production": 3,
            "breakdown": 3,
            "service": 0,
            "delay": 0,
            "safety_meeting": 0,
            "idle": 0
        }
    }
}
```

### Step 3: Persist Results (Optional)
```python
# Only if checklist_form is provided
if checklist_form:
    # Save each event
    for event in timeline_result["events"]:
        cleaned_event = CleanedActivityEvent(
            checklist_form_id=checklist_form.id,
            event_type=event["event_type"],
            start_time=event["start_time"],
            end_time=event["end_time"],
            is_inferred=event["is_inferred_end_time"],
            ...
        )
        db.add(cleaned_event)
    
    # Save summary
    analytics = ChecklistAnalytics(
        checklist_form_id=checklist_form.id,
        release_time=summary["machine_release_time"],
        idle_duration_minutes=summary["total_idle_minutes"],
        safety_meeting_detected=summary["safety_meeting_detected"],
        change_of_shift_detected=summary["change_of_shift_detected"],
        ...
    )
    db.add(analytics)
    db.commit()
```

## Database Schema

### CleanedActivityEvent Table
Stores individual timeline events with inference metadata:
- `event_type` (production, breakdown, service, delay, safety_meeting, idle)
- `start_time`, `end_time` (HH:MM format)
- `duration_minutes` (computed)
- `is_inferred` (boolean)
- `is_ambiguous` (boolean)
- `inference_reason` (text, for debugging)
- `activity_code`, `location`, `loads`, `remarks` (activity details)

### ChecklistAnalytics Table
Stores high-level timeline summary:
- `release_time` (machine release time from service events)
- `idle_duration_minutes` (total idle time in shift)
- `production_duration_minutes` (computed from production events)
- `breakdown_duration_minutes` (computed from breakdown events)
- `safety_meeting_detected` (boolean)
- `change_of_shift_detected` (boolean)
- `unmatched_gaps_count` (number of idle gaps)

## Processing Rules

### Shift Detection Rules
1. If header contains explicit shift (day/night) → use it
2. Else if activities contain times in 18:00-06:00 range → night
3. Else → day (default)

### Time Inference Rules
1. If end_time is missing and next event exists → infer end_time = next_start_time
2. Else if end_time is missing and event < shift_end → infer end_time = shift_end
3. Else → mark as ambiguous (unresolvable)

### Event Classification Rules
Classification uses a scoring system that combines activity code patterns and remarks keywords. Both contribute to the score; the highest-scoring event type wins.

- **safety_meeting**: Code 1XX + remarks with "safety", "briefing", "toolbox", etc.
- **breakdown**: Code 3XX (primary signal) OR remarks with "breakdown", "failure", "repair", etc.
- **service**: Code 2XX + remarks with "service", "maintenance", "lube", "check", etc.
- **delay**: Code 4XX/5XX/6XX — these ranges have no code patterns so rely entirely on remarks keywords ("delay", "waiting", "standby", "queue", etc.)
- **idle**: Inserted by `_compute_idle_gaps` for calendar gaps within the shift window with no recorded activity
- **production**: Default when no other type scores higher

Note: 3XX maps to "breakdown" in the rule engine even though the parser's `activity_codes` dict labels code 300 as "Service". This is a known inconsistency.

### Daily Service Logic
- Event type = "service" AND duration > 60 minutes → reclassify as "breakdown"
- Track machine release time from latest successful service event

### Idle Computation
1. Sort all non-idle events by start_time
2. Identify gaps between:
   - Shift start → first event start
   - Event end → next event start
   - Last event end → shift end
3. Return gaps with durations in minutes

## Testing

```bash
# From the project root, with venv active:
python -m pytest backend/tests/ --ignore=backend/tests/test_checklist.py -v
```

153 tests pass across all pipeline components. End-to-end tests in `test_pipeline_e2e.py` cover both day and night shifts, OCR noise, code/time ambiguity, and postprocessing→rule engine interactions without loading the TrOCR model.

## Key Components

### ocr_rule_engine_integration.py
- `convert_ocr_to_rule_engine_format()`: Format conversion
- `process_ocr_with_rule_engine()`: Main processing pipeline
- `integrate_ocr_with_rule_engine()`: End-to-end with database persistence
- `extract_timeline_shifts()`: Extract shift information
- `extract_service_info()`: Extract service/release time info
- `extract_idle_analysis()`: Extract idle gaps and metrics
- `extract_inferred_times()`: Extract events with inferred times
- `persist_timeline_events()`: Save events to database
- `persist_timeline_summary()`: Save summary to database

### API Routes (api/routes/ocr_processing.py)
- `POST /api/v1/ocr/process`: Primary processing endpoint
- `POST /api/v1/ocr/analyze`: Analysis without persistence
- `POST /api/v1/ocr/debug/*`: Debug endpoints for specific logic

## Error Handling

- Invalid OCR input (missing required fields) → HTTPException 422
- Rule engine processing errors → HTTPException 500 with error details
- Database persistence errors → Transaction rollback, HTTPException 500
- All errors logged with traceback for debugging

## Performance Notes

- OCR format conversion: < 1ms (minimal overhead)
- Rule engine processing: 10-50ms per checklist (depends on activity count)
- Database persistence: 100-500ms (depends on number of events)
- Total end-to-end: Typically < 1 second per checklist

---
