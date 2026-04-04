# QUICK START EXECUTION CHECKLIST

## PHASE 0: INITIAL SETUP (30 minutes)

### Day 1 - Environment Preparation

- [ ] **Download & Install Python 3.11**
  - Go to https://www.python.org/downloads/
  - ✅ **IMPORTANT**: Check "Add Python to PATH" during installation
  - Verify: Open PowerShell/Terminal and run: `python --version`
  - Expected: `Python 3.11.x`

- [ ] **Download & Install Git**
  - Go to https://git-scm.com/download/
  - Use default installation settings
  - Verify: `git --version`

- [ ] **Download & Install PostgreSQL 14+**
  - Go to https://www.postgresql.org/download/
  - Remember the postgres password you set
  - Default port: 5432
  - Verify: `psql --version`

- [ ] **Download & Install Node.js (LTS)**
  - Go to https://nodejs.org/
  - Install LTS version
  - Verify: `node --version` and `npm --version`

- [ ] **Download & Install Docker Desktop** (optional for production)
  - Go to https://www.docker.com/products/docker-desktop
  - For Windows: Ensure WSL2 is enabled
  - Verify: `docker --version`

- [ ] **Download & Install Visual Studio Code**
  - Go to https://code.visualstudio.com/
  - Install extensions:
    - Python (Microsoft)
    - Pylance
    - REST Client
    - Thunder Client (for API testing)

- [ ] **Download Tesseract OCR** (Windows)
  - Go to https://github.com/UB-Mannheim/tesseract/wiki
  - Install to: `C:\Program Files\Tesseract-OCR`

---

## PHASE 1: PROJECT STRUCTURE (15 minutes)

### Day 1/2 - Create Workspace

```bash
# Open PowerShell/Terminal

# 1. Navigate to Desktop
cd ~/Desktop

# 2. Create project folder
mkdir "ORC pro"
cd "ORC pro"

# 3. Initialize Git
git init
git config user.name "Your Name"
git config user.email "your.email@example.com"

# 4. Create virtual environment
python -m venv venv

# 5. Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 6. Create folders
mkdir backend frontend mobile ml data tests docs devops

# 7. Create .gitignore
```

### Create `.gitignore` file:
```
venv/
__pycache__/
*.pyc
.env
.env.local
.vscode/
node_modules/
dist/
build/
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
.DS_Store
models/
*.zip
```

---

## PHASE 2: INSTALL DEPENDENCIES (1.5 hours)

### Day 2 - Package Installation

- [ ] **Copy requirements.txt** (from SETUP_SCRIPTS.md)
  - Create file: `requirements.txt` in project root
  - Copy full content from SETUP_SCRIPTS.md

- [ ] **Install Python packages**
  ```bash
  # Ensure virtual environment is activated
  pip install --upgrade pip setuptools wheel

  # Install all packages (this takes 3-5 minutes)
  pip install -r requirements.txt

  # If you get GPU errors (torch), use CPU version:
  # pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
  ```

- [ ] **Verify installation**
  ```bash
  python verify_setup.py
  ```

- [ ] **Setup frontend (optional for now)**
  ```bash
  cd frontend
  npm init -y
  npm install react react-dom react-router-dom axios
  cd ..
  ```

---

## PHASE 3: DATABASE SETUP (20 minutes)

### Day 2 - PostgreSQL Configuration

- [ ] **Create PostgreSQL database**
  ```bash
  # Open Command Prompt as Administrator
  # Run:
  psql -U postgres

  # Then in psql shell:
  CREATE DATABASE orc_pro;
  CREATE USER orc_user WITH PASSWORD 'secure_password_change_me';
  GRANT ALL PRIVILEGES ON DATABASE orc_pro TO orc_user;
  \q
  ```

- [ ] **Test database connection**
  ```bash
  psql -U orc_user -d orc_pro -h localhost
  # If prompted for password, enter: secure_password_change_me
  # Type \q to exit
  ```

- [ ] **Create .env file** in project root
  ```
  # DATABASE
  DATABASE_URL=postgresql://orc_user:secure_password_change_me@localhost:5432/orc_pro
  SQLALCHEMY_DATABASE_URL=postgresql://orc_user:secure_password_change_me@localhost:5432/orc_pro

  # API
  API_HOST=0.0.0.0
  API_PORT=8000
  API_WORKERS=4

  # SECURITY
  SECRET_KEY=your-super-secret-key-change-in-production
  JWT_ALGORITHM=HS256

  # ML MODELS
  TROCR_MODEL=microsoft/trocr-large-handwritten
  TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe

  # ENVIRONMENT
  ENVIRONMENT=development
  DEBUG=True
  ```

---

## PHASE 4: BACKEND SETUP (PROMPT 1) - Days 3-4

### Create Project Structure

```bash
# Create backend package
mkdir -p backend/app
mkdir -p backend/tests
mkdir -p backend/migrations

# Create files:
# backend/__init__.py (empty)
# backend/app/__init__.py (empty)
# backend/app/main.py (FastAPI app)
# backend/app/config.py (settings)
# backend/app/database.py (DB connection)
```

### Prompt 1: FastAPI Backend Setup

**VIBE CODING PROMPT:**

```
Create a Python backend using FastAPI that accepts image uploads and stores them.

Requirements:
- Create a FastAPI application with a /api/v1 prefix
- Add an endpoint POST /api/v1/checklist/upload that accepts file uploads
- Files should be saved to ./uploads/ directory
- Return a JSON response with: {"status": "success", "file_path": "...", "file_size": ...}
- Add error handling for invalid file types
- Add CORS middleware to allow requests from http://localhost:3000
- Use async/await for file operations
- Add basic health check endpoint: GET /health

Use:
- FastAPI for the web framework
- python-multipart for file uploads
- pathlib for file operations
- pydantic for request/response models
- python-dotenv for environment variables

Structure:
- app/main.py - FastAPI app entry point
- app/config.py - Settings (from .env)
- app/models.py - Pydantic models
- app/routes/upload.py - Upload endpoints
```

**After getting the code:**

```bash
# Create directories for uploads
mkdir uploads
mkdir logs

# Run the backend
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Test the API
# Open browser: http://localhost:8000/docs
# You should see Swagger UI
```

---

## PHASE 5: DATABASE & ORM (PROMPT 5) - Days 5-6

### Prompt 5: PostgreSQL Schema Design

**VIBE CODING PROMPT:**

```
Design a PostgreSQL schema for storing structured checklist data including inspection items and activity logs.

Create SQLAlchemy ORM models with:

1. Checklist model:
   - id (UUID primary key)
   - form_type (truck/loader)
   - date (datetime)
   - shift (morning/afternoon/night)
   - operator_name (string)
   - machine_no (string)
   - status (approved/rejected/review)
   - created_at, updated_at (timestamps)

2. Header model:
   - checklist_id (foreign key)
   - permit_no, permit_expiry
   - start_engine_hours, end_engine_hours
   - shift

3. InspectionItem model:
   - checklist_id (foreign key)
   - section (A, B, C...)
   - item_name (string)
   - status (pass/fail/yes/no)
   - remarks (text)
   - is_no_go (boolean)

4. ActivityLog model:
   - checklist_id (foreign key)
   - activity_code (string)
   - from_time, to_time (time)
   - workplace (string)
   - remarks (text)

5. AuditLog model:
   - checklist_id (foreign key)
   - field_name (string)
   - raw_value, corrected_value
   - confidence_score (float)
   - corrected_by (user_id)
   - timestamp

Create:
- SQLAlchemy models in app/models/
- Alembic migrations
- Database initialization script
- CRUD operations in app/services/

Use:
- SQLAlchemy 2.0 with async support
- Alembic for migrations
- UUID for primary keys
- Timestamp triggers for created_at/updated_at
```

**After getting the code:**

```bash
# Initialize Alembic
alembic init migrations

# Create first migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head

# Verify schema in database
psql -U orc_user -d orc_pro -c "\dt"
```

---

## PHASE 6: IMAGE PROCESSING (PROMPT 2) - Days 7-8

### Prompt 2: OpenCV Preprocessing

**VIBE CODING PROMPT:**

```
Add OpenCV preprocessing to detect and crop table cells from structured forms.

Create a preprocessing module that:

1. Loads an image from file or numpy array
2. Converts to grayscale and applies thresholding
3. Detects grid lines using Hough transform or contour detection
4. Identifies cell boundaries and crops individual cells
5. Saves cropped cells to disk with metadata

Output:
- List of cropped cell images
- JSON metadata with cell coordinates, section names, expected field types

Functions:
- preprocess_checklist_image(image_path) -> Dict[str, Any]
  Returns: {"cells": [...], "grid_layout": {...}, "form_type": "truck|loader"}

- detect_table_cells(image) -> List[np.ndarray]
  Returns: List of cropped cell images

- extract_cell_metadata(image, cell_coordinates) -> Dict

Create:
- app/ml/preprocessing.py
- Tests in tests/test_preprocessing.py
- Example on sample checklist image

Use:
- OpenCV for image processing
- NumPy for array operations
- Pillow for image I/O
- scikit-image for advanced processing

Handle:
- Different image sizes
- Rotated forms
- Low contrast images
- Damaged/folded paper
```

**After getting the code:**

```bash
# Create sample image directory
mkdir data/samples

# Test preprocessing
python -m app.ml.preprocessing --image data/samples/truck_checklist.jpg

# Output should show cropped cells in output/ folder
```

---

## PHASE 7: OCR INTEGRATION (PROMPT 3) - Days 9-10

### Prompt 3: TrOCR Handwriting Recognition

**VIBE CODING PROMPT:**

```
Integrate TrOCR model for handwriting recognition on cropped images.

Create an OCR module that:

1. Loads pre-trained TrOCR model
2. Preprocesses cell images for OCR
3. Runs inference to extract text
4. Returns confidence scores
5. Handles multiple field types (time, codes, remarks)

Important: Train/fine-tune SEPARATE models:
- Model A: Time fields (HH:MM format)
- Model B: Numeric codes (200-999)
- Model C: Written text (descriptions, remarks)

Functions:
- load_ocr_model(model_type: str) -> Model
  - model_type: "time" | "code" | "text"

- extract_text(image, model_type) -> Dict[str, Any]
  Returns: {"text": "...", "confidence": 0.95, "raw_text": "..."}

- batch_extract(images: List[np.ndarray], model_type: str) -> List[Dict]

Implementation:
- app/ml/ocr.py
- app/ml/models.py (model loading & caching)
- Tests with sample cell images

Use:
- Transformers library (Hugging Face)
- TrOCR microsoft/trocr-large-handwritten as base
- Torch for inference
- GPU optimization (optional)

Handle:
- Out of memory errors
- Model not found (download from HF hub)
- Rotated text
- Low quality images
"""
```

**After getting the code:**

```bash
# Download TrOCR model (first run will be slow)
python -c "from transformers import TrOCRProcessor, VisionEncoderDecoderModel; VisionEncoderDecoderModel.from_pretrained('microsoft/trocr-large-handwritten')"

# Test OCR on sample cell
python -m app.ml.ocr --image data/samples/cell_001.jpg

# Output should show extracted text and confidence
```

---

## PHASE 8: POST-PROCESSING (PROMPT 4) - Days 11-12

### Prompt 4: Post-Processing & Validation

**VIBE CODING PROMPT:**

```
Implement a post-processing module that corrects OCR outputs using rules for time, codes, and vocabulary.

Create validation and correction engine:

1. CHARACTER NORMALIZATION
   - O/0, l/1/I, S/5, B/8 confusion
   - Regex-based replacement

2. TIME VALIDATION
   - Pattern: HH:MM (00:00 - 23:59)
   - Handle: 14:3O -> 14:30, 1:20 -> 01:20
   - Time range validation: from_time <= to_time

3. CODE VALIDATION
   - Load allowed codes from database
   - Fuzzy match if exact match fails
   - Flag confidence < 0.80

4. VOCABULARY CORRECTION
   - Dictionary: "Refueling", "Safety meeting", "Hydraulic leak", etc.
   - Use symspellpy or fuzzy matching
   - Return suggested corrections

5. BUSINESS LOGIC RULES
   - No-go items must have remarks
   - Shift "Night" allows time rollover past midnight
   - Mandatory fields: operator_name, date, machine_no

Functions:
- normalize_text(text: str) -> str
- validate_time(time_str: str) -> Dict[str, Any]
- validate_code(code: str, form_type: str) -> Dict[str, Any]
- correct_vocabulary(text: str) -> str
- validate_checklist(data: Dict) -> Dict[str, List[str]]

Use:
- regex for pattern matching
- fuzzywuzzy for string matching
- symspellpy for spelling correction
- pydantic validators

Tests:
- Unit tests for each validation rule
- Edge cases: midnight boundary, missing leading zeros, etc.
```

**After getting the code:**

```bash
# Test post-processing
python -c "
from app.ml.postprocessing import validate_time
result = validate_time('14:3O')
print(result)  # Should correct to 14:30
"

# Test vocabulary correction
python -c "
from app.ml.postprocessing import correct_vocabulary
result = correct_vocabulary('Refueling')
print(result)
"
```

---

## PHASE 9: RULE ENGINE (PROMPT 6) - Days 13-14

### Prompt 6: Rule Engine & Validation

**VIBE CODING PROMPT:**

```
Create a rule engine that validates checklist data including no-go items and time consistency.

Build a validation system:

1. RULE DEFINITIONS
   - Load rules from database or YAML
   - Each rule has: name, condition, severity (error/warning), message

2. NO-GO LOGIC
   - If item has ❶ flag AND status == "fail" -> checklist REJECTED
   - Reason: Mandatory safety item failed

3. TIME CONSISTENCY
   - from_time < to_time (within same shift)
   - OR handle time rollover for night shift

4. SHIFT-BASED RULES
   - Day shift: Times must be 06:00 - 18:00
   - Night shift: Allow times 18:00 - 06:00 (next day)

5. MANDATORY FIELDS
   - operator_name (required)
   - date (required)
   - machine_no (required)
   - At least one activity record (required)

6. CROSS-FIELD VALIDATION
   - If "Ore pass full" noted -> mandatory remarks
   - If status == "fail" -> remarks required
   - Activity records must have times

Functions:
- load_rules(checklist_type: str) -> List[Rule]
- apply_rules(checklist: Dict, rules: List[Rule]) -> ValidationResult
- validate_checklist(checklist: Dict) -> Dict

Classes:
- Rule (name, condition_lambda, severity, message)
- ValidationResult (is_valid, errors[], warnings[])
- RuleEngine

Use:
- Python ast.literal_eval for dynamic conditions
- Pydantic field validators
- Custom exception classes

Tests:
- Test each rule individually
- Test rule combinations
- Test edge cases
```

**After getting the code:**

```bash
# Test rule engine
python -c "
from app.services.rule_engine import RuleEngine
engine = RuleEngine()
checklist = {...}
result = engine.validate_checklist(checklist)
print(result)
"
```

---

## PHASE 10: REVIEW DASHBOARD (PROMPT 7) - Days 15-16

### Prompt 7: Manual Review Interface

**VIBE CODING PROMPT:**

```
Build a review dashboard showing low-confidence OCR results for manual correction.

Create web UI for human-in-the-loop correction:

BACKEND ENDPOINTS:
- GET /api/v1/review/queue
  Returns: List of checklists with confidence < 0.85
  Fields: checklist_id, form_type, confidence_score, problem_fields

- GET /api/v1/review/{checklist_id}
  Returns: Full checklist with original OCR + corrections needed
  Fields breakdown with original_value, confidence, corrected_value

- POST /api/v1/review/{checklist_id}/approve
  Approves checklist
  Body: { approved_fields: [{field: "...", value: "..."}] }

- PUT /api/v1/review/{checklist_id}/correct
  Updates field value
  Body: { field_name: "...", corrected_value: "..." }
  Returns: Updated checklist

- POST /api/v1/review/{checklist_id}/reject
  Rejects checklist for rerun
  Body: { reason: "..." }

FRONTEND:
- Dashboard showing:
  - Queue count (by form type)
  - Average confidence score
  - Oldest waiting checklist

- Review card showing:
  - Original image with cell boundaries
  - Extracted fields in a form
  - OCR confidence for each field
  - Editable input for corrections
  - Approve/Reject buttons

- Inline image viewer with zoom/rotate

Use:
- React for frontend
- React Hook Form for form handling
- Material-UI for components
- Axios for API calls
- FastAPI for backend
- SQLAlchemy for database updates

Database:
- Add reviewed_by, review_timestamp to audit_log
```

**After getting the code:**

```bash
# Start backend if not already running
uvicorn app.main:app --reload

# In another terminal, start React frontend
cd frontend
npm start

# Open http://localhost:3000
```

---

## PHASE 11: ANALYTICS (PROMPT 8) - Days 17-18

### Prompt 8: Analytics & Insights

**VIBE CODING PROMPT:**

```
Add analytics: machine utilization, delays, and breakdown trends.

Create analytics endpoints and dashboards:

ENDPOINTS:
- GET /api/v1/analytics/utilization
  Returns: {
    total_hours: 480,
    active_hours: 320,
    idle_hours: 160,
    utilization_rate: 66.7,
    by_machine: [{machine_no: "T-001", utilization: 75.5}, ...]
  }

- GET /api/v1/analytics/breakdown-codes
  Returns top issues by frequency:
  {
    "Hydraulic leak": 12,
    "Transmission": 8,
    "Bucket": 5
  }

- GET /api/v1/analytics/delays
  Returns: {
    total_delays: 45,
    delay_hours: 12.5,
    avg_delay_duration: 50,
    by_category: {
      "maintenance": 8,
      "refueling": 4,
      "safety_meeting": 3
    }
  }

- GET /api/v1/analytics/trends?period=month
  Returns time series data for:
  - Utilization over time
  - Breakdown frequency
  - Downtime patterns

- GET /api/v1/analytics/operator-performance
  Returns: {
    operator_name: "John Doe",
    checklists_submitted: 45,
    avg_no_gos: 2.3,
    error_rate: 0.05
  }

FRONTEND:
- Dashboard with:
  - Utilization gauge chart
  - Breakdown frequency bar chart
  - Delay trend line chart
  - Operator performance table
  - Machine health scorecard

Use:
- SQLAlchemy for complex queries
- Pandas for data aggregation
- Recharts for frontend visualization
- FastAPI for endpoints
```

**After getting the code:**

```bash
# The analytics system should automatically work
# Navigate to http://localhost:3000/analytics
# Select date range and view charts
```

---

## PHASE 12: TESTING & DEPLOYMENT (Days 19-20)

### Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test
pytest tests/test_ocr.py::test_trocr_extraction -v
```

### Load Testing

```bash
# Create tests/load_test.py using k6 or Locust
locust -f tests/load_test.py -u 50 -r 10 -t 5m

# Or use k6:
# k6 run tests/load_test.js
```

### Docker Deployment (Optional)

```bash
# Create Dockerfile and docker-compose.yml
docker-compose up --build

# App runs on http://localhost:8000
```

---

## VERIFICATION CHECKLIST

### Week 1 End
- [ ] All packages installed
- [ ] PostgreSQL running with schema created
- [ ] FastAPI backend running on port 8000
- [ ] Can upload images via /api/v1/checklist/upload
- [ ] Database contains uploaded file records

### Week 2 End
- [ ] TrOCR model integrated and extracting text
- [ ] Post-processing correcting OCR errors
- [ ] OCR accuracy > 85% on test images
- [ ] Manual review UI working
- [ ] Rule engine validating checklists

### Week 3 End
- [ ] Analytics dashboard displaying trends
- [ ] Mobile app (or web app) allowing uploads
- [ ] End-to-end pipeline working: upload → OCR → validation → storage
- [ ] Accuracy > 95% after corrections
- [ ] Manual review rate < 10%

---

## TROUBLESHOOTING QUICK REFERENCE

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'fastapi'` | Run: `pip install -r requirements.txt` |
| `psycopg2` error | Run: `pip install psycopg2-binary==2.9.9` |
| PostgreSQL connection refused | Ensure PostgreSQL is running: `pg_isready` |
| Torch installation fails | Switch to CPU: Use CPU wheel from pytorch.org |
| Tesseract not found | Install from https://github.com/UB-Mannheim/tesseract |
| TrOCR model too slow | Download model first: `python -c "from transformers import VisionEncoderDecoderModel; VisionEncoderDecoderModel.from_pretrained('microsoft/trocr-large-handwritten')"` |
| Out of CUDA memory | Reduce batch size or use CPU inference |
| Port 8000 already in use | Kill process: `lsof -ti:8000 | xargs kill -9` |
| Node modules errors | Delete node_modules and run: `npm install` |

---

## RESOURCES

- FastAPI Docs: https://fastapi.tiangolo.com/
- SQLAlchemy: https://docs.sqlalchemy.org/
- TrOCR Papers: https://arxiv.org/abs/2109.10282
- PyTorch Docs: https://pytorch.org/docs/
- React Docs: https://react.dev/
- PostgreSQL Docs: https://www.postgresql.org/docs/

---

**Total Estimated Time: 20 days with 4-6 hours/day**

**Start Date: [TODAY]**
**Target Completion: [+20 days]**

You're ready to start! Begin with the **PHASE 0 checklist** above.

