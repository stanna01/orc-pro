# ORC Pro Backend

## Overview

FastAPI backend for the ORC Pro mining checklist digitization system. Scanned PDF checklists are processed through TrOCR OCR extraction, a tolerant parser, a business-logic rule engine, and a machine analytics module. All results are persisted to a SQLite database (configurable to PostgreSQL for production).

## Architecture

```
PDF Upload
    ↓
PDF Processor  (pdf_processor.py)        — image extraction, CLAHE, binarization
    ↓
TrOCR Extractor (ocr_extractor.py)       — handwriting OCR, simulated fallback
    ↓
Checklist Parser (checklist_parser.py)   — tolerant OCR text → OCROutput schema
    ↓
Postprocessing (ml/postprocessing.py)    — character correction, code validation, time normalisation
    ↓
Validator (validator.py)                 — time ordering, shift boundaries, overlap detection
    ↓
Rule Engine (rule_engine.py)             — event classification, time inference, idle gap computation
    ↓
Analytics (analytics.py)                 — availability, utilisation, engine hours metrics
    ↓
Database (models/checklist.py)           — SQLAlchemy ORM persistence
```

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app startup, lifespan, route registration |
| `app/database.py` | SQLAlchemy engine, session management, pool settings |
| `app/config.py` | Settings loaded from environment |
| `app/models/checklist.py` | ORM models: ChecklistForm, CleanedActivityEvent, ChecklistAnalytics |
| `app/models/schemas.py` | Pydantic schemas: OCROutput, OCRField, OCRHeader, OCRActivityRow |
| `app/services/checklist_parser.py` | Tolerant OCR text parser with fuzzy matching |
| `app/services/checklist_extraction.py` | OCR output validation and checklist payload builder |
| `app/services/validator.py` | Data quality checks (times, overlaps, shift boundaries) |
| `app/services/rule_engine.py` | Event classification, time inference, idle computation |
| `app/services/analytics.py` | Machine performance metrics computation |
| `app/services/ocr_rule_engine_integration.py` | Bridges OCR output to rule engine; handles DB persistence |
| `app/services/orchestrator.py` | Coordinates full pipeline end-to-end |
| `app/services/ocr_extractor.py` | TrOCR model wrapper; SimulatedOCRExtractor fallback |
| `app/services/pdf_processor.py` | PDF→image extraction, OpenCV preprocessing |
| `app/ml/postprocessing.py` | Character normalisation, code validation, time format normalisation |
| `app/ml/ocr/pipeline.py` | Raw page text extraction helpers |
| `app/api/routes/checklists.py` | GET /checklists — list, retrieve, analytics, timeline |
| `app/api/routes/ocr_processing.py` | POST /ocr — upload PDF, analyze OCR output |
| `app/api/routes/health.py` | Health, readiness, liveness endpoints |
| `app/api/routes/uploads.py` | File upload validation |

## Running the Backend

```powershell
# From the project root, with venv active:
cd backend
uvicorn app.main:app --reload
```

API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Running Tests

```powershell
# From the project root:
python -m pytest backend/tests/ --ignore=backend/tests/test_checklist.py -v
```

153 tests pass. `test_checklist.py` requires the full TrOCR model loaded in memory — skip it on machines with less than 16 GB RAM.

## Key Design Decisions

- **Transaction ownership**: the orchestrator calls `db.commit()`; service layers do not commit independently
- **Confidence handling**: `OCRField.confidence` is `Optional[float]`; all consumers use `(field.confidence or 0.0)` to handle unknown confidence
- **Available minutes**: computed as `total_shift_minutes - breakdown_minutes`; `release_delay_minutes` is tracked as a separate metric and is not deducted from available minutes
- **Idle gaps**: computed by `_compute_idle_gaps` as calendar gaps between events within the shift window, not as a sum of event durations
- **Plain-string parser input**: when the parser receives a plain string (no OCR metadata), `row_conf = None` so values are never suppressed by a confidence threshold

## Reference Documents

- [ANALYTICS_FORMULAS.md](ANALYTICS_FORMULAS.md) — availability and performance ratio definitions
- [PHASE2_endpoint_trace.md](PHASE2_endpoint_trace.md) — endpoint-to-handler mapping
- [../API_ROUTES_DOCUMENTATION.md](../API_ROUTES_DOCUMENTATION.md) — full REST API reference
- [../PIPELINE_DOCUMENTATION.md](../PIPELINE_DOCUMENTATION.md) — pipeline architecture
- [../OCR_RULE_ENGINE_INTEGRATION.md](../OCR_RULE_ENGINE_INTEGRATION.md) — integration layer detail
- [../STRICT_VERIFICATION_AUDIT.md](../STRICT_VERIFICATION_AUDIT.md) — bug history and current readiness rating
