# Route Implementation Details

## File Structure

```
backend/app/api/routes/
├── __init__.py (UPDATED)
│   ├── checklist
│   ├── checklists (NEW)
│   ├── health
│   ├── uploads
│   └── ocr_processing (ENHANCED)
│
├── checklists.py (NEW - 346 lines)
│   ├── GET /api/v1/checklists/{checklist_id}
│   ├── GET /api/v1/checklists/{checklist_id}/analytics
│   ├── GET /api/v1/checklists/{checklist_id}/timeline
│   └── GET /api/v1/checklists
│
└── ocr_processing.py (ENHANCED)
    ├── POST /api/v1/ocr/upload-pdf (existing)
    ├── POST /api/v1/ocr/analyze (existing, enhanced)
    ├── POST /api/v1/ocr/upload-and-process (NEW)
    └── ...
```

---

## Endpoint Implementation Details

### 1. GET /api/v1/checklists/{checklist_id}

**Location**: [checklists.py](backend/app/api/routes/checklists.py#L15)

**Function Signature**:
```python
@router.get("/{checklist_id}", status_code=status.HTTP_200_OK)
async def get_checklist(
    checklist_id: int,
    include_events: bool = True,
    include_analytics: bool = True,
    db: Session = Depends(get_session),
) -> dict:
```

**Query Parameters**:
```python
checklist_id    : int     (path parameter)
include_events  : bool    (query, default=True)
include_analytics : bool  (query, default=True)
```

**Logic Flow**:
1. Query `ChecklistForm` by ID
2. Return 404 if not found
3. If `include_events`: Query `CleanedActivityEvent` by checklist_id
4. If `include_analytics`: Query `ChecklistAnalytics` by checklist_id
5. Format all data into response structure
6. Calculate event_count summary
7. Return complete response

**Database Queries**:
```python
db.query(ChecklistForm).filter_by(id=checklist_id).first()
db.query(CleanedActivityEvent).filter_by(checklist_form_id=checklist_id).all()
db.query(ChecklistAnalytics).filter_by(checklist_form_id=checklist_id).first()
```

**Response Fields** (minimal set):
- checklist: id, source_filename, document_date, shift, machine_number, operator_name, etc.
- timeline_events: id, event_type, activity_code, start_time, end_time, duration_minutes, etc.
- analytics: id, total_shift_minutes, availability breakdown, ratios, engine metrics, flags
- event_count: integer

---

### 2. GET /api/v1/checklists/{checklist_id}/analytics

**Location**: [checklists.py](backend/app/api/routes/checklists.py#L113)

**Function Signature**:
```python
@router.get("/{checklist_id}/analytics", status_code=status.HTTP_200_OK)
async def get_checklist_analytics(
    checklist_id: int,
    db: Session = Depends(get_session),
) -> dict:
```

**Logic Flow**:
1. Query `ChecklistForm` by ID (validation)
2. Return 404 if checklist not found
3. Query `ChecklistAnalytics` by checklist_form_id
4. Return 404 if analytics not found
5. Format detailed analytics response with breakdown and metrics
6. Include document reference information

**Response Structure**:
```python
{
  "success": True,
  "analytics_id": int,
  "checklist_id": int,
  "document": { filename, date, shift, machine, operator },
  "availability_breakdown": { minutes by type },
  "performance_ratios": { utilization, downtime, effective_availability },
  "engine_metrics": { start_hours, end_hours, delta, valid, transmission },
  "event_flags": { safety_meeting, shift_change, gaps },
  "release_time": string,
  "release_delay_minutes": float,
  "created_at": ISO datetime
}
```

---

### 3. GET /api/v1/checklists/{checklist_id}/timeline

**Location**: [checklists.py](backend/app/api/routes/checklists.py#L165)

**Function Signature**:
```python
@router.get("/{checklist_id}/timeline", status_code=status.HTTP_200_OK)
async def get_checklist_timeline(
    checklist_id: int,
    only_inferred: bool = False,
    db: Session = Depends(get_session),
) -> dict:
```

**Query Parameters**:
```python
checklist_id   : int   (path parameter)
only_inferred  : bool  (query, default=False)
```

**Logic Flow**:
1. Query `ChecklistForm` by ID (validation)
2. Return 404 if not found
3. Query `CleanedActivityEvent` by checklist_form_id
4. If `only_inferred`: Filter where is_inferred=True
5. Format timeline events
6. Calculate statistics (total_duration, event_type breakdown)
7. Return events + summary

**Database Queries**:
```python
db.query(CleanedActivityEvent).filter_by(checklist_form_id=checklist_id)
  .filter_by(is_inferred=True)  # if only_inferred
  .all()
```

**Response Structure**:
```python
{
  "success": True,
  "checklist_id": int,
  "timeline_events": [
    {
      "id": int,
      "event_type": string,
      "activity_code": string,
      "start_time": string,
      "end_time": string,
      "duration_minutes": float,
      "workplace": string,
      "ore_waste": string,
      "loads": string,
      "remarks": string,
      "is_inferred": bool,
      "is_ambiguous": bool,
      "inference_reason": string,
      "confidence": float,
      "created_at": ISO datetime
    }
  ],
  "summary": {
    "total_events": int,
    "inferred_count": int,
    "ambiguous_count": int,
    "total_duration_minutes": float,
    "event_types": { "PRODUCTION": count, "BREAKDOWN": count, ... }
  }
}
```

---

### 4. GET /api/v1/checklists

**Location**: [checklists.py](backend/app/api/routes/checklists.py#L237)

**Function Signature**:
```python
@router.get("", status_code=status.HTTP_200_OK)
async def list_checklists(
    limit: int = 50,
    offset: int = 0,
    shift: Optional[str] = None,
    machine_number: Optional[str] = None,
    operator_name: Optional[str] = None,
    db: Session = Depends(get_session),
) -> dict:
```

**Query Parameters**:
```python
limit           : int (default=50)
offset          : int (default=0)
shift           : string (optional)
machine_number  : string (optional)
operator_name   : string (optional)
```

**Logic Flow**:
1. Build query: `db.query(ChecklistForm)`
2. Apply filters if provided:
   - `shift == value`
   - `machine_number == value`
   - `operator_name ILIKE %value%` (case-insensitive)
3. Get total count before pagination
4. Order by created_at DESC
5. Apply offset and limit
6. For each checklist, query associated ChecklistAnalytics
7. Format and return paginated list

**Database Queries**:
```python
query = db.query(ChecklistForm)
query.filter_by(shift=shift)
query.filter_by(machine_number=machine_number)
query.filter(ChecklistForm.operator_name.ilike(f"%{operator_name}%"))
total_count = query.count()
checklists = query.order_by(ChecklistForm.created_at.desc()).offset(offset).limit(limit).all()

# For each checklist:
db.query(ChecklistAnalytics).filter_by(checklist_form_id=form.id).first()
```

**Response Structure**:
```python
{
  "success": True,
  "total_count": int,
  "offset": int,
  "limit": int,
  "returned": int,
  "checklists": [
    {
      "id": int,
      "source_filename": string,
      "document_date": ISO date,
      "shift": string,
      "machine_number": string,
      "operator_name": string,
      "has_analytics": bool,
      "utilization_ratio": float,
      "created_at": ISO datetime
    }
  ]
}
```

---

## Enhanced Endpoints (ocr_processing.py)

### POST /api/v1/ocr/upload-and-process (NEW)

**Location**: [ocr_processing.py](backend/app/api/routes/ocr_processing.py#L370)

**Function Signature**:
```python
@router.post("/upload-and-process", status_code=status.HTTP_200_OK)
async def upload_and_process_checklist(
    file: UploadFile = File(...),
    reference_date: Optional[date] = Body(None),
    db: Session = Depends(get_session),
) -> dict:
```

**Request Format**:
```
Content-Type: multipart/form-data
{
  "file": <PDF binary>,
  "reference_date": "2024-01-15" (optional)
}
```

**Logic Flow**:
1. Set reference_date to today if not provided
2. Validate file extension (.pdf only)
3. Save uploaded file to temp directory
4. Create orchestrator: `create_orchestrator(db=db)`
5. Call: `orchestrator.process_pdf(temp_file, reference_date, persist=True)`
6. Check success flag
7. If successful:
   - Extract checklist_id from result
   - Query fresh `ChecklistForm` from database
   - Query fresh `CleanedActivityEvent` list
   - Query fresh `ChecklistAnalytics`
   - Format timeline_events and analytics
   - Build response with all data
8. Clean up temp file in finally block
9. Return structured response

**Database Queries** (after processing):
```python
checklist_form = db.query(ChecklistForm).filter_by(id=checklist_id).first()
events = db.query(CleanedActivityEvent).filter_by(checklist_form_id=checklist_id).all()
analytics = db.query(ChecklistAnalytics).filter_by(checklist_form_id=checklist_id).first()
```

**Response Structure**:
```python
{
  "success": True,
  "timestamp": ISO datetime,
  "filename": string,
  "checklist_id": int,
  "document_id": string,
  "pages_processed": int,
  "activities_extracted": int,
  "timeline_events": [
    {
      "id": int,
      "event_type": string,
      "activity_code": string,
      "start_time": string,
      "end_time": string,
      "duration_minutes": float,
      "is_inferred": bool
    }
  ],
  "analytics": {
    "utilization_ratio": float,
    "downtime_ratio": float,
    "production_minutes": float,
    "breakdown_minutes": float,
    "idle_minutes": float,
    "availability_minutes": float
  },
  "database_ids": {
    "checklist_form_id": int,
    "event_ids": [int, ...],
    "analytics_id": int
  }
}
```

**Error Responses**:
- **400**: File must be PDF
- **500**: Processing failed with error message

---

## Data Access Patterns

### 1. Checklist Retrieval (with relationships)
```python
# Efficient query pattern using relationships
checklist = db.query(ChecklistForm).filter_by(id=42).first()

# Access related data via loaded relationships
timeline_events = checklist.cleaned_events  # From relationship
analytics = checklist.analytics            # From relationship
```

### 2. Event Timeline Filtering
```python
# Filter by event type, inference status, etc.
events = db.query(CleanedActivityEvent)\
    .filter_by(checklist_form_id=42)\
    .filter_by(is_inferred=False)\
    .all()

# Calculate statistics
total_duration = sum(e.duration_minutes for e in events)
by_type = {}
for e in events:
    by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
```

### 3. Analytics Aggregation
```python
# Combine metrics for response
response = {
    "availability": {
        "production": analytics.production_duration_minutes,
        "breakdown": analytics.breakdown_duration_minutes,
        "service": analytics.daily_service_duration_minutes,
        "idle": analytics.idle_duration_minutes,
        "available": analytics.availability_minutes
    },
    "ratios": {
        "utilization": analytics.utilization_ratio,
        "downtime": analytics.downtime_ratio,
        "effective": (analytics.availability_minutes - analytics.idle_duration_minutes) / analytics.total_shift_minutes
    }
}
```

---

## Error Handling

### 404 Not Found Pattern
```python
resource = db.query(Model).filter_by(id=id).first()
if not resource:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{Model.__name__} with ID {id} not found"
    )
```

### 400 Bad Request Pattern
```python
if not file.filename.lower().endswith('.pdf'):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="File must be a PDF"
    )
```

### 500 Processing Error Pattern
```python
try:
    result = process(...)
    return success_response
except Exception as e:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Processing failed: {str(e)}"
    )
```

---

## Dependencies

### Python Imports
```python
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Body
from sqlalchemy.orm import Session
```

### Database Dependencies
```python
from backend.app.database import get_session
from backend.app.models.checklist import ChecklistForm, CleanedActivityEvent, ChecklistAnalytics
```

### Service Dependencies
```python
from backend.app.services.orchestrator import create_orchestrator
```

---

## Performance Considerations

### Query Optimization
- Use `.first()` for single record retrieval
- Use `.all()` for lists only when needed
- Filter at database level before loading
- Use `.count()` for pagination

### Response Formatting
- Loop through results once to build response
- Calculate summary statistics during loop
- Format dates to ISO format strings
- Handle None/null values gracefully

### File Handling
- Use `tempfile` for secure temp storage
- Always cleanup in `finally` block
- Validate file size limits (if needed)
- Close file handles properly

### Database Sessions
- Use FastAPI dependency injection (`Depends(get_session)`)
- Sessions auto-commit on success
- Rollback on exception
- No manual session management needed

---

## Testing Checklist

- [ ] GET /checklists/1 returns 200 with checklist data
- [ ] GET /checklists/1 with include_events=false skips events
- [ ] GET /checklists/1 with include_analytics=false skips analytics
- [ ] GET /checklists/999 returns 404
- [ ] GET /checklists/1/analytics returns 200 with detailed metrics
- [ ] GET /checklists/1/analytics for missing analytics returns 404
- [ ] GET /checklists/1/timeline returns 200 with events
- [ ] GET /checklists/1/timeline?only_inferred=true filters correctly
- [ ] GET /checklists returns paginated list
- [ ] GET /checklists?machine_number=M-2847 filters by machine
- [ ] GET /checklists?operator_name=John filters by operator
- [ ] POST /upload-pdf with valid PDF processes successfully
- [ ] POST /upload-pdf with non-PDF returns 400
- [ ] POST /upload-pdf returns checklist_id in response
- [ ] POST /upload-pdf returns timeline_events in response
- [ ] POST /upload-pdf returns analytics in response
- [ ] POST /upload-and-process alias works identically
- [ ] All responses have success=true/false field
- [ ] All responses are valid JSON
- [ ] Error responses include detail field

---

## Deployment Checklist

- [ ] Routes registered in main.py
- [ ] __init__.py exports all routers
- [ ] Database session dependency working
- [ ] All imports resolve without errors
- [ ] OCR model cached or accessible
- [ ] Temp directory writable
- [ ] Database tables created
- [ ] CORS configured if needed
- [ ] API documentation auto-generated at /docs
- [ ] Health check endpoint working
