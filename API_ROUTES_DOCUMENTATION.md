# API Routes Documentation

## Overview

Complete REST API for ORC Pro checklist processing system. Endpoints handle PDF upload, checklist retrieval, analytics queries, and timeline visualization.

---

## Base URL
```
/api/v1
```

---

## Endpoints

### 1. Upload and Process Checklist

#### POST `/ocr/upload-pdf`
**Alias:** `/ocr/upload-and-process`

Upload PDF checklist for autonomous processing through complete pipeline.

**Request:**
```
Content-Type: multipart/form-data

{
  "file": <PDF binary>,
  "reference_date": "2024-01-15" (optional, defaults to today)
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "timestamp": "2024-01-15T10:30:45.123456",
  "filename": "checklist_april_15.pdf",
  "checklist_id": 42,
  "document_id": "DOC-20240115-001",
  "pages_processed": 3,
  "activities_extracted": 28,
  "timeline_events": [
    {
      "id": 101,
      "event_type": "PRODUCTION",
      "activity_code": "10",
      "start_time": "07:30",
      "end_time": "09:15",
      "duration_minutes": 105,
      "is_inferred": false
    }
  ],
  "analytics": {
    "utilization_ratio": 0.67,
    "downtime_ratio": 0.15,
    "production_minutes": 480,
    "breakdown_minutes": 90,
    "idle_minutes": 30,
    "availability_minutes": 600
  },
  "database_ids": {
    "checklist_form_id": 42,
    "event_ids": [101, 102, 103],
    "analytics_id": 67
  }
}
```

**Error Response (400 Bad Request):**
```json
{
  "success": false,
  "error": "File must be a PDF"
}
```

**Error Response (500 Internal Server Error):**
```json
{
  "success": false,
  "error": "PDF processing failed: [error details]",
  "processing_log": [...]
}
```

**Processing Pipeline:**
1. PDF extraction (pages → images)
2. Image preprocessing (CLAHE, denoise, binarize)
3. Region detection (table location)
4. OCR extraction (TrOCR on regions)
5. Checklist parsing (regex field extraction)
6. Rule engine integration (business logic)
7. Analytics computation (availability, utilization)
8. Database persistence

---

### 2. Retrieve Checklist with Timeline

#### GET `/checklists/{checklist_id}`

Retrieve complete checklist metadata with optional timeline events and analytics.

**Query Parameters:**
- `include_events`: boolean (default: true) - Include timeline events
- `include_analytics`: boolean (default: true) - Include analytics data

**Response (200 OK):**
```json
{
  "success": true,
  "checklist": {
    "id": 42,
    "source_filename": "checklist_april_15.pdf",
    "document_date": "2024-04-15",
    "shift": "day",
    "machine_number": "M-2847",
    "operator_name": "John Smith",
    "mine_number": "MINE-001",
    "permit_number": "PERMIT-2024-042",
    "start_engine_hours": 1234.5,
    "end_engine_hours": 1244.8,
    "start_transmission_hours": 5678.2,
    "end_transmission_hours": 5688.5,
    "release_time": "18:00",
    "shift_start": "06:00",
    "shift_end": "18:00",
    "created_at": "2024-01-15T10:30:45.123456",
    "updated_at": "2024-01-15T10:35:22.654321"
  },
  "timeline_events": [
    {
      "id": 101,
      "event_type": "PRODUCTION",
      "activity_code": "10",
      "start_time": "07:30",
      "end_time": "09:15",
      "duration_minutes": 105,
      "workplace": "Pit Zone A",
      "ore_waste": "Ore",
      "loads": "42",
      "remarks": "Continuous operation",
      "is_inferred": false,
      "is_ambiguous": false,
      "inference_reason": null,
      "confidence": 0.95
    },
    {
      "id": 102,
      "event_type": "BREAKDOWN",
      "activity_code": "30",
      "start_time": "09:15",
      "end_time": "10:00",
      "duration_minutes": 45,
      "workplace": "Equipment",
      "ore_waste": null,
      "loads": null,
      "remarks": "Hydraulic repair",
      "is_inferred": false,
      "is_ambiguous": false,
      "inference_reason": null,
      "confidence": 0.88
    }
  ],
  "event_count": 28,
  "analytics": {
    "id": 67,
    "total_shift_minutes": 720,
    "availability": {
      "production_minutes": 480,
      "breakdown_minutes": 90,
      "service_minutes": 30,
      "idle_minutes": 60,
      "available_minutes": 600
    },
    "ratios": {
      "utilization_ratio": 0.667,
      "downtime_ratio": 0.125
    },
    "engine": {
      "hours_delta": 10.3,
      "hours_valid": true,
      "transmission_hours_delta": 10.3
    },
    "flags": {
      "safety_meeting_detected": true,
      "change_of_shift_detected": false,
      "unmatched_gaps_count": 0
    },
    "created_at": "2024-01-15T10:31:12.456789"
  }
}
```

**Error Response (404 Not Found):**
```json
{
  "detail": "Checklist with ID 999 not found"
}
```

---

### 3. Retrieve Analytics for Checklist

#### GET `/checklists/{checklist_id}/analytics`

Retrieve detailed performance analytics for a specific checklist.

**Response (200 OK):**
```json
{
  "success": true,
  "analytics_id": 67,
  "checklist_id": 42,
  "document": {
    "filename": "checklist_april_15.pdf",
    "date": "2024-04-15",
    "shift": "day",
    "machine": "M-2847",
    "operator": "John Smith"
  },
  "availability_breakdown": {
    "total_shift_minutes": 720,
    "production_minutes": 480,
    "breakdown_minutes": 90,
    "service_minutes": 30,
    "idle_minutes": 60,
    "available_minutes": 600
  },
  "performance_ratios": {
    "utilization_ratio": 0.667,
    "downtime_ratio": 0.125,
    "effective_availability": 0.750
  },
  "engine_metrics": {
    "start_hours": 1234.5,
    "end_hours": 1244.8,
    "delta": 10.3,
    "valid": true,
    "validation_message": "Engine hours consistent with recorded duration",
    "transmission_hours_delta": 10.3
  },
  "event_flags": {
    "safety_meeting_detected": true,
    "change_of_shift_detected": false,
    "unmatched_gaps_count": 0
  },
  "release_time": "18:00",
  "release_delay_minutes": 0,
  "created_at": "2024-01-15T10:31:12.456789"
}
```

**Error Response (404 Not Found):**
```json
{
  "detail": "Analytics not found for checklist 999"
}
```

---

### 4. Retrieve Timeline Events

#### GET `/checklists/{checklist_id}/timeline`

Retrieve detailed timeline events with optional filtering.

**Query Parameters:**
- `only_inferred`: boolean (default: false) - Return only inferred events

**Response (200 OK):**
```json
{
  "success": true,
  "checklist_id": 42,
  "timeline_events": [
    {
      "id": 101,
      "event_type": "PRODUCTION",
      "activity_code": "10",
      "start_time": "07:30",
      "end_time": "09:15",
      "duration_minutes": 105,
      "workplace": "Pit Zone A",
      "ore_waste": "Ore",
      "loads": "42",
      "remarks": "Continuous operation",
      "is_inferred": false,
      "is_ambiguous": false,
      "inference_reason": null,
      "confidence": 0.95,
      "created_at": "2024-01-15T10:30:45.123456"
    }
  ],
  "summary": {
    "total_events": 28,
    "inferred_count": 3,
    "ambiguous_count": 1,
    "total_duration_minutes": 720,
    "event_types": {
      "PRODUCTION": 18,
      "BREAKDOWN": 5,
      "IDLE": 4,
      "SERVICE": 1
    }
  }
}
```

---

### 5. List All Checklists

#### GET `/checklists`

List all checklists with pagination and optional filtering.

**Query Parameters:**
- `limit`: integer (default: 50) - Maximum results per page
- `offset`: integer (default: 0) - Results to skip
- `shift`: string (optional) - Filter by shift (day/night)
- `machine_number`: string (optional) - Filter by machine
- `operator_name`: string (optional) - Filter by operator name

**Response (200 OK):**
```json
{
  "success": true,
  "total_count": 342,
  "offset": 0,
  "limit": 50,
  "returned": 50,
  "checklists": [
    {
      "id": 42,
      "source_filename": "checklist_april_15.pdf",
      "document_date": "2024-04-15",
      "shift": "day",
      "machine_number": "M-2847",
      "operator_name": "John Smith",
      "has_analytics": true,
      "utilization_ratio": 0.667,
      "created_at": "2024-01-15T10:30:45.123456"
    },
    {
      "id": 41,
      "source_filename": "checklist_april_14.pdf",
      "document_date": "2024-04-14",
      "shift": "night",
      "machine_number": "M-2847",
      "operator_name": "Jane Doe",
      "has_analytics": true,
      "utilization_ratio": 0.721,
      "created_at": "2024-01-14T18:15:22.654321"
    }
  ]
}
```

---

## Data Models

### ChecklistForm
Represents a processed checklist document.

```
{
  "id": integer,
  "source_filename": string,
  "document_date": date,
  "shift": string (day|night),
  "machine_number": string,
  "operator_name": string,
  "mine_number": string,
  "permit_number": string,
  "start_engine_hours": float,
  "end_engine_hours": float,
  "start_transmission_hours": float,
  "end_transmission_hours": float,
  "release_time": string (HH:MM),
  "shift_start": string (HH:MM),
  "shift_end": string (HH:MM),
  "created_at": ISO 8601 datetime,
  "updated_at": ISO 8601 datetime
}
```

### CleanedActivityEvent
Represents a parsed activity from the checklist timeline.

```
{
  "id": integer,
  "event_type": string (PRODUCTION|BREAKDOWN|IDLE|SERVICE),
  "activity_code": string,
  "start_time": string (HH:MM),
  "end_time": string (HH:MM),
  "duration_minutes": float,
  "workplace": string,
  "ore_waste": string,
  "loads": string,
  "remarks": string,
  "is_inferred": boolean,
  "is_ambiguous": boolean,
  "inference_reason": string,
  "confidence": float (0.0-1.0),
  "created_at": ISO 8601 datetime
}
```

### ChecklistAnalytics
Represents computed performance metrics.

```
{
  "id": integer,
  "checklist_id": integer,
  "total_shift_minutes": float,
  "production_minutes": float,
  "breakdown_minutes": float,
  "service_minutes": float,
  "idle_minutes": float,
  "available_minutes": float,
  "utilization_ratio": float (0.0-1.0),
  "downtime_ratio": float (0.0-1.0),
  "engine_hours_delta": float,
  "engine_hours_valid": boolean,
  "transmission_hours_delta": float,
  "safety_meeting_detected": boolean,
  "change_of_shift_detected": boolean,
  "unmatched_gaps_count": integer,
  "created_at": ISO 8601 datetime
}
```

---

## Common Response Codes

- **200 OK**: Request successful
- **400 Bad Request**: Invalid input (e.g., non-PDF file)
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Processing failed (see error message)

---

## Error Handling

All endpoints return errors in standardized format:

```json
{
  "detail": "Error message describing the issue"
}
```

Or for processing endpoints:

```json
{
  "success": false,
  "error": "Error message",
  "processing_log": ["step 1", "step 2 - ERROR occurred"]
}
```

---

## Usage Examples

### Example 1: Upload and Process PDF
```bash
curl -X POST http://localhost:8000/api/v1/ocr/upload-pdf \
  -F "file=@checklist.pdf" \
  -F "reference_date=2024-01-15"
```

### Example 2: Get Checklist with Timeline
```bash
curl http://localhost:8000/api/v1/checklists/42?include_events=true&include_analytics=true
```

### Example 3: Get Analytics Only
```bash
curl http://localhost:8000/api/v1/checklists/42/analytics
```

### Example 4: List Checklists by Machine
```bash
curl "http://localhost:8000/api/v1/checklists?machine_number=M-2847&limit=25"
```

### Example 5: Get Inferred Events Only
```bash
curl "http://localhost:8000/api/v1/checklists/42/timeline?only_inferred=true"
```

---

## Files

### Route Files
- `backend/app/api/routes/ocr_processing.py` - PDF upload and processing endpoints
- `backend/app/api/routes/checklists.py` - Checklist retrieval and analytics endpoints

### Updated Files
- `backend/app/main.py` - Router registration and app configuration
- `backend/app/api/routes/__init__.py` - Route module exports

### Supporting Services
- `backend/app/services/orchestrator.py` - End-to-end processing orchestration
- `backend/app/services/ocr_rule_engine_integration.py` - Analytics computation
- Database models in `backend/app/models/checklist.py`

---

## Architecture

```
Upload PDF
    ↓
PDF Processor (extract pages, preprocess images)
    ↓
Region Detector (find table regions)
    ↓
OCR Extractor (TrOCR handwriting recognition)
    ↓
Checklist Parser (regex field extraction)
    ↓
Rule Engine (business logic, event classification)
    ↓
Analytics (compute availability, utilization, downtime)
    ↓
Database Persistence
    ↓
Retrieve via API (GET /checklists/{id})
```

---

## Performance Notes

- PDF upload: 100-500ms (varies by file size)
- Image preprocessing: 100-300ms per page
- OCR extraction: 2-5 seconds per page (TrOCR GPU intensive)
- Total E2E processing: 10-30 seconds for typical 3-page checklist
- First OCR model load: 30-60 seconds (subsequent loads 2-3 seconds via cache)

---

## Database Requirements

- PostgreSQL 14+
- Tables: checklist_forms, cleaned_activity_events, checklist_analytics
- Relationships: Checklist ← → Events, Checklist ← → Analytics

---

## Future Enhancements

- Async batch processing queue for high-volume uploads
- Real-time processing status websocket
- PDF template detection for form-specific parsing
- Performance caching for frequently accessed analytics
- Bulk export (CSV/Excel) of timeline and analytics
- Advanced filtering and search across checklist repository
