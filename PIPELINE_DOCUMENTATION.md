
# Checklist Processing Pipeline - Architecture & Implementation

## Overview

Complete end-to-end pipeline for processing scanned mining checklists:

```
PDF Upload → Preprocessing → OCR → Parsing → RuleEngine → Analytics → Database
```

## Architecture

### 1. PDF Processor Service (`pdf_processor.py`)
**Purpose**: Extract and enhance PDF images for OCR

**Key Functions**:
- `extract_pages_from_pdf(pdf_path)` - Convert PDF to image array (300 DPI)
- `preprocess_image(image)` - Apply CLAHE, denoise, binarization
- `detect_table_regions(image)` - Find form/table regions via contour detection
- `extract_region(image, bbox)` - Crop specific regions
- `scale_image(image, factor)` - Upscale for better OCR on small text

**Dependencies**: PyMuPDF (fitz), OpenCV, NumPy, PIL

### 2. OCR Extractor Service (`ocr_extractor.py`)
**Purpose**: Extract handwritten text using TrOCR model

**Key Features**:
- `TrOCRExtractor` class - Wraps Microsoft TrOCR model
- GPU/CPU auto-detection
- Batch text extraction from regions
- Lazy loading for performance

**Model**: `microsoft/trocr-large-handwritten`
**Framework**: Transformers + PyTorch

### 3. Checklist Parser Service (`checklist_parser.py`)
**Purpose**: Convert raw OCR text to structured OCROutput

**Key Functions**:
- `parse_header(raw_text)` - Extract header info (date, operator, machine, shift)
- `parse_activity_row(raw_text, row_index)` - Parse activity row
- `parse_checklist(header_text, activity_texts)` - Full checklist parsing
- Regex-based field extraction (times, codes, loads, location)

**Output**: `OCROutput` Pydantic schema with header and activities

### 4. Orchestrator Service (`orchestrator.py`)
**Purpose**: Coordinate full pipeline from PDF to database

**Class**: `ChecklistProcessingOrchestrator`
- Single orchestrator orchestrates all stages
- Error handling and logging at each stage
- Optional database persistence
- Batch processing support

**Pipeline Stages**:
1. PDF Extraction - Extract pages as images
2. Preprocessing - Enhance for OCR
3. Region Detection - Find table areas
4. OCR Extraction - Run TrOCR on regions
5. Text Parsing - Structure extracted text
6. Rule Engine - Apply business logic
7. Analytics - Compute metrics
8. Database - Persist results

**Key Methods**:
- `process_pdf(pdf_path, reference_date, persist)` - Process single PDF
- `process_multiple_pdfs(directory, pattern, limit)` - Batch processing
- `log_step(stage, message, status)` - Track pipeline execution

### 5. API Endpoint (`ocr_processing.py`)
**Purpose**: Expose PDF processing via REST API

**Endpoint**: `POST /api/v1/ocr/upload-pdf`

**Request**:
```json
{
  "file": <PDF file>,
  "reference_date": "2026-04-04" (optional)
}
```

**Response**:
```json
{
  "success": true,
  "document_id": "April_4th_Night",
  "pages_processed": 1,
  "activities_extracted": 6,
  "timeline_events": [...],
  "timeline_summary": {...},
  "analytics": {...},
  "persisted": {
    "checklist_id": 123,
    "event_ids": [1,2,3,4,5,6],
    "analytics_id": 456
  },
  "processing_log": [...]
}
```

## Data Flow

### Input: Scanned PDF
```
Sample PDF: "April 4th Night.pdf"
- Image of mining checklist with handwritten entries
- Contains header (date, operator, machine, shift)
- Contains activity table (times, codes, locations, remarks)
```

### Processing Stages

**Stage 1: PDF Extraction**
- Input: PDF file
- Process: Extract pages at 300 DPI
- Output: List of numpy arrays (images)

**Stage 2: Preprocessing**
- Input: Raw images
- Process: 
  - Convert to grayscale
  - Apply CLAHE (contrast enhancement)
  - Denoise (FastNLMeans)
  - Binarize (Otsu threshold)
- Output: Enhanced binary images

**Stage 3: Region Detection**
- Input: Preprocessed images
- Process: Find contours, filter by size/aspect ratio
- Output: List of (x, y, w, h) bounding boxes

**Stage 4: OCR Extraction**
- Input: Image regions
- Process: Run TrOCR on each region
- Output: List of extracted text strings

**Stage 5: Text Parsing**
- Input: Raw OCR text (header + activities)
- Process: Extract fields using regex patterns
- Output: OCROutput schema (Pydantic)

**Stage 6: Rule Engine**
- Input: OCROutput
- Process:
  - Shift detection (day/night)
  - Time inference
  - Event classification
- Output: Timeline events + summary

**Stage 7: Analytics**
- Input: Timeline events
- Process: Compute metrics
- Output: Availability, utilization, downtime ratios

**Stage 8: Database**
- Input: Analytics results
- Process: Create records if checklist_form provided
- Output: Persisted IDs

## Error Handling

Each stage includes error handling:

```python
try:
    # Stage operation
    result = operation()
    log_step(stage, "Success message")
except Exception as e:
    log_step(stage, f"Error: {e}", status="error")
    db.rollback()
    return {"success": False, "error": str(e)}
```

Processing log captures all stages:
```python
processing_log = [
    {"stage": "PDF_EXTRACTION", "message": "Extracted 1 pages", "status": "info"},
    {"stage": "PREPROCESSING", "message": "Image enhancement complete", "status": "info"},
    {"stage": "OCR_EXTRACTION", "message": "Extracted text from 8 regions", "status": "info"},
    ...
]
```

## Performance Characteristics

**Single PDF Processing**:
- PDF Extraction: 100-500ms
- Preprocessing: 100-300ms
- OCR Extraction: 2-5 seconds (TrOCR is ML-heavy)
- Parsing: 10-50ms
- Rule Engine: 50-100ms
- Analytics: 20-50ms
- Database: 100-500ms (with persistence)

**Total**: ~3-7 seconds per PDF (first run slower due to model loading)

**Batch Processing** (10 PDFs):
- Model loaded once (~30-60 seconds on first batch)
- Each PDF: ~3-5 seconds
- Total: ~50-70 seconds

## Usage Examples

### Single PDF Processing (No Database)
```python
from backend.app.services.orchestrator import create_orchestrator

orchestrator = create_orchestrator(db=None)
result = orchestrator.process_pdf("checklist.pdf", persist=False)

if result['success']:
    print(f"Extracted {result['activities_extracted']} activities")
    print(f"Timeline: {len(result['timeline_events'])} events")
    print(f"Utilization: {result['analytics']['performance_ratios']['utilization_ratio']:.1%}")
```

### Batch Processing (10 Files)
```python
results = orchestrator.process_multiple_pdfs(
    pdf_directory="./sample/April",
    pattern="*.pdf",
    limit=10
)

for result in results:
    if result['success']:
        print(f"{result['document_id']}: {result['activities_extracted']} activities")
```

### API Upload
```bash
curl -X POST "http://localhost:8000/api/v1/ocr/upload-pdf" \
  -F "file=@April_4th_Night.pdf" \
  -F "reference_date=2026-04-04"
```

### With Database Persistence
```python
from backend.app.database import SessionLocal

db = SessionLocal()
orchestrator = create_orchestrator(db=db)

result = orchestrator.process_pdf(
    "checklist.pdf",
    reference_date=date(2026, 4, 4),
    persist=True  # Save to database
)

# Result includes:
# - Checklist form ID
# - Timeline event IDs
# - Analytics record ID
```

## Dependencies

**Core**:
- fastapi==0.104.1
- sqlalchemy==2.0.23
- pydantic==2.5.0

**PDF Processing**:
- PyMuPDF==1.24.0 (fitz) - PDF to image
- opencv-python==4.8.1.78 - Image processing

**OCR**:
- torch==2.1.1
- transformers==4.35.2
- PIL==10.1.0

**Image Processing**:
- numpy
- scikit-image

**Database**:
- psycopg2-binary==2.9.9

## Testing

**Unit Tests**:
```bash
pytest test_analytics_integration.py  # Validates analytics computation
pytest test_ocr_rule_engine_integration.py  # Validates rule engine logic
```

**Integration Tests**:
```bash
python test_pipeline_e2e.py  # Full pipeline with sample PDFs
```

**Manual Testing**:
1. Upload PDF via `/api/v1/ocr/upload-pdf`
2. Check response for extracted data
3. Verify timeline events in response
4. Verify analytics computed
5. Check database for persisted records

## Deployment Notes

**Production Considerations**:

1. **GPU Acceleration**: TrOCR runs on GPU if available (CUDA)
   - Set `CUDA_VISIBLE_DEVICES=0` for specific GPU
   - Falls back to CPU automatically

2. **Model Caching**: TrOCR model cached in `~/.cache/huggingface/`
   - Download size: ~1.5GB
   - Load time: ~30-60 seconds first run, ~2-3 seconds subsequent

3. **Temporary Files**: Uses Python's `tempfile` module
   - Automatic cleanup on completion
   - Safe for concurrent uploads

4. **Error Recovery**: On failure, transaction rolled back
   - No partial records in database
   - Processing log captured for debugging

5. **Concurrency**: FastAPI handles concurrent uploads
   - Each request gets new orchestrator instance
   - Database session per request (dependency injection)

## Future Enhancements

- [ ] Async PDF processing (Celery + Redis)
- [ ] Webhook notifications for long-running processes
- [ ] Confidence thresholding for manual review queue
- [ ] Parallel TrOCR processing (multiple regions simultaneously)
- [ ] Caching of parsed checklists
- [ ] Analytics visualization dashboards
- [ ] Batch import from directory
