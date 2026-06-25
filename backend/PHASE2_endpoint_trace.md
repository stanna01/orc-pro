# Phase 2 — Endpoint Execution Trace

This document maps each public HTTP endpoint to its handler, downstream service calls, DB model usage, and key response fields.

## Summary Legend
- Handler: file and function handling the request
- Calls: downstream functions/modules invoked (file)
- DB: models or DB actions performed (file)
- Response: main response fields returned to the client

---

## POST /api/v1/ocr/process
- Handler: backend/app/api/routes/ocr_processing.py -> `process_ocr_output`
- Calls:
  - `integrate_ocr_with_rule_engine` (backend/app/services/ocr_rule_engine_integration.py)
- DB:
  - optional `ChecklistForm` lookup when `persist=True` (backend/app/models/checklist.py)
  - `get_session()` dependency (backend/app/database.py)
- Response keys: `success`, `timestamp`, `data` (rule-engine result)

---

## POST /api/v1/ocr/analyze
- Handler: backend/app/api/routes/ocr_processing.py -> `analyze_ocr_output`
- Calls:
  - `process_ocr_with_rule_engine` (backend/app/services/ocr_rule_engine_integration.py)
  - `compute_machine_analytics` (backend/app/services/analytics.py)
  - various extract helpers: `extract_timeline_shifts`, `extract_service_info`, `extract_idle_analysis`, `extract_inferred_times`
- DB: none (analysis-only)
- Response keys: `shifts`, `service`, `idle_analysis`, `inferred_times`, `analytics`, `analytics_error`, `full_timeline`

---

## POST /api/v1/ocr/debug/shift-detection
- Handler: backend/app/api/routes/ocr_processing.py -> `debug_shift_detection`
- Calls: `process_ocr_with_rule_engine` + `extract_timeline_shifts`
- DB: none
- Response: `shift_detection`, `activities_count`, `events_count`

---

## POST /api/v1/ocr/debug/time-inference
- Handler: backend/app/api/routes/ocr_processing.py -> `debug_time_inference`
- Calls: `process_ocr_with_rule_engine` + `extract_inferred_times`
- DB: none
- Response: `total_inferred`, `inferred_times`

---

## POST /api/v1/ocr/debug/idle-computation
- Handler: backend/app/api/routes/ocr_processing.py -> `debug_idle_computation`
- Calls: `process_ocr_with_rule_engine` + `extract_idle_analysis`
- DB: none
- Response: `idle_analysis`, `shift_info`

---

## POST /api/v1/ocr/debug/service-detection
- Handler: backend/app/api/routes/ocr_processing.py -> `debug_service_detection`
- Calls: `process_ocr_with_rule_engine` + `extract_service_info`
- DB: none
- Response: `service_info`, `events`

---

## POST /api/v1/ocr/debug/analytics
- Handler: backend/app/api/routes/ocr_processing.py -> `debug_analytics`
- Calls: `process_ocr_with_rule_engine`, `compute_machine_analytics`
- DB: none
- Response: metrics and breakdowns from `compute_machine_analytics`

---

## POST /api/v1/ocr/upload-pdf  (and /upload-and-process alias)
- Handler: backend/app/api/routes/ocr_processing.py -> `process_checklist_pdf` / `upload_and_process_checklist`
- Flow & Calls:
  1. Save uploaded file to temp
  2. `create_orchestrator(db)` -> returns `ChecklistProcessingOrchestrator` (backend/app/services/orchestrator.py)
  3. `orchestrator.process_pdf(pdf_path, reference_date, persist=True)` (backend/app/services/orchestrator.py)
     - `extract_pages_from_pdf`, `preprocess_image`, `detect_table_regions` (backend/app/services/pdf_processor.py)
     - `ocr_extractor.extract_text_from_regions` (backend/app/services/ocr_extractor.py)
     - `ChecklistParser.parse_checklist` (backend/app/services/checklist_parser.py)
     - `validate_checklist` (backend/app/services/validator.py)
     - `integrate_ocr_with_rule_engine` (backend/app/services/ocr_rule_engine_integration.py)
     - analytics via `compute_machine_analytics` (backend/app/services/analytics.py) as part of integration
- DB interactions:
  - orchestrator may create `ChecklistForm` (backend/app/models/checklist.py)
  - integration persists `CleanedActivityEvent`, `ChecklistAnalytics` via `checklist_service` and models
  - DB session via dependency `get_session()` and `ChecklistProcessingOrchestrator.db`
- Response keys: `success`, `document_id`, `pages_processed`, `activities_extracted`, `timeline_events`, `timeline_summary`, `analytics`, `persisted`, `processing_log`, `error`

---

## POST /api/v1/uploads
- Handler: backend/app/api/routes/uploads.py -> `upload_checklist_image`
- Calls: local helpers `_validate_upload_extension`, `_validate_content_type`
- DB: none
- Response keys: `id`, `original_filename`, `saved_path`, `size_bytes`, `content_type`

---

## GET /api/v1/checklists/{checklist_id} and related checklist endpoints
- Handler: backend/app/api/routes/checklists.py
- Calls / DB:
  - Query `ChecklistForm` (backend/app/models/checklist.py)
  - Query `CleanedActivityEvent` and `ChecklistAnalytics` (backend/app/models/checklist.py)
- Response keys: `checklist` metadata, `timeline_events`, `analytics`, `event_count`

---

## POST /checklists/  (create via service)
- Handler: backend/app/api/routes/checklist.py -> `create_checklist`
- Calls: `create_checklist_form` (backend/app/services/checklist_service.py)
- DB: creates `ChecklistForm` and related records
- Response model: `ChecklistFormResponse` (backend/app/models/schemas.py)

---

## Health endpoints (/health, /health/ready, /health/live)
- Handler: backend/app/api/routes/health.py
- Calls: `get_settings()` (backend/app/config.py); `init_db()` registered in app lifespan in `main.py`
- DB: `init_db()` runs on startup (backend/app/database.py)
- Response: health/readiness/liveness JSON

---

### Notes / Evidence
- `main.py` registers all routers and calls `init_db()` at startup: see `backend/app/main.py`.
- `ChecklistProcessingOrchestrator` contains both `process_pdf()` and `process_from_extracted_regions()` (entrypoints for file-based and region-based flows) and enforces validation halting when `validate_checklist` reports `needs_review`.
- OCR extraction uses `TrOCRExtractor` with simulated fallback when `torch`/`transformers` are not available (backend/app/services/ocr_extractor.py).

---

If you want the next level of detail I can: for each endpoint produce exact handler line numbers and list every called function with file + approximate line range, and extract exact DB columns used for persistence. Confirm and I'll expand each endpoint to that line-level trace.