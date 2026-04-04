# ORC PRO - DIRECTORY STRUCTURE & FILE ORGANIZATION

## Project Root Layout

```
ORC pro/
├── README.md                          # Project overview
├── IMPLEMENTATION_ROADMAP.md          # Full system specification
├── SETUP_SCRIPTS.md                   # Installation scripts
├── EXECUTION_CHECKLIST.md             # Step-by-step tasks (THIS FILE)
├── PROJECT_STRUCTURE.md               # Directory layout (this file)
│
├── requirements.txt                   # Python dependencies
├── package.json                       # Node.js dependencies (root level)
├── .env                               # Environment variables (CREATE YOURSELF)
├── .env.example                       # Template for .env
├── .gitignore                         # Git ignore rules
│
├── setup.ps1                          # Windows setup script
├── setup.sh                           # Linux/Mac setup script
├── verify_setup.py                    # Verification script
│
├── venv/                              # Python virtual environment (auto-created)
│
# BACKEND
├── backend/
│   ├── __init__.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI application entry point
│   │   ├── config.py                  # Settings & environment variables
│   │   │
│   │   # API Routes
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── upload.py              # POST /upload endpoints
│   │   │   ├── review.py              # GET/PUT manual review endpoints
│   │   │   ├── analytics.py           # GET analytics endpoints
│   │   │   └── health.py              # Health check endpoint
│   │   │
│   │   # Data Models (ORM & Pydantic)
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── database.py            # SQLAlchemy base models
│   │   │   ├── checklist.py           # Checklist, Header, Inspection models
│   │   │   ├── activity.py            # ActivityLog, Codes models
│   │   │   ├── audit.py               # AuditLog model
│   │   │   └── schemas.py             # Pydantic schemas (request/response)
│   │   │
│   │   # Database Connection & Session
│   │   ├── database.py                # SQLAlchemy engine, session manager
│   │   ├── deps.py                    # Dependency injection
│   │   │
│   │   # ML/OCR Pipeline
│   │   ├── ml/
│   │   │   ├── __init__.py
│   │   │   ├── preprocessing.py       # Image preprocessing & cell detection
│   │   │   ├── ocr.py                 # TrOCR integration
│   │   │   ├── models.py              # Model loading & caching
│   │   │   ├── postprocessing.py      # Validation & correction rules
│   │   │   └── trocr_models/
│   │   │       ├── time_model.py      # Fine-tuned for HH:MM format
│   │   │       ├── code_model.py      # Fine-tuned for numeric codes
│   │   │       └── text_model.py      # Fine-tuned for handwritten text
│   │   │
│   │   # Business Logic
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── checklist_service.py   # Checklist CRUD operations
│   │   │   ├── ocr_pipeline.py        # End-to-end OCR pipeline
│   │   │   ├── rule_engine.py         # Validation rule engine
│   │   │   └── analytics.py           # Analytics queries & aggregations
│   │   │
│   │   # Utilities
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── logger.py              # Logging setup
│   │   │   ├── validators.py          # Custom validators
│   │   │   ├── constants.py           # Constants, allowed codes, rules
│   │   │   └── helpers.py             # Utility functions
│   │   │
│   │   # Middleware
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── cors.py                # CORS configuration
│   │       ├── auth.py                # JWT authentication
│   │       └── logging.py             # Request/response logging
│   │
│   # Database Migrations
│   ├── migrations/
│   │   ├── versions/
│   │   │   ├── 001_initial_schema.py
│   │   │   ├── 002_add_audit_trail.py
│   │   │   └── ...
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── alembic.ini
│   │
│   # Tests
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                # Pytest configuration & fixtures
│   │   ├── test_api.py                # API endpoint tests
│   │   ├── test_ocr.py                # OCR pipeline tests
│   │   ├── test_preprocessing.py      # Image processing tests
│   │   ├── test_postprocessing.py     # Validation rule tests
│   │   ├── test_database.py           # Database query tests
│   │   ├── test_rule_engine.py        # Business logic tests
│   │   └── fixtures/
│   │       ├── sample_images/
│   │       │   ├── truck_checklist.jpg
│   │       │   ├── loader_checklist.jpg
│   │       │   └── cell_samples/
│   │       └── mock_data.py
│   │
│   # Documentation
│   ├── docs/
│   │   ├── API.md                     # API documentation
│   │   ├── DATABASE.md                # Schema documentation
│   │   ├── OCR_PIPELINE.md            # ML pipeline explanation
│   │   └── RULES.md                   # Business rules documentation
│   │
│   └── requirements.txt               # Backend-specific deps (optional)
│
# FRONTEND (Web)
├── frontend/
│   ├── package.json
│   ├── vite.config.js                 # Vite configuration
│   ├── tailwind.config.js             # Tailwind CSS config
│   ├── src/
│   │   ├── index.jsx                  # React entry point
│   │   ├── App.jsx                    # Main App component
│   │   ├── main.jsx                   # Vite entry
│   │   │
│   │   # Pages
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx          # Main dashboard
│   │   │   ├── Upload.jsx             # Image upload page
│   │   │   ├── Review.jsx             # Manual correction dashboard
│   │   │   ├── Analytics.jsx          # Analytics & insights
│   │   │   ├── Settings.jsx           # Configuration page
│   │   │   └── NotFound.jsx           # 404 page
│   │   │
│   │   # Components
│   │   ├── components/
│   │   │   ├── Upload/
│   │   │   │   ├── ImageUpload.jsx
│   │   │   │   ├── ProgressBar.jsx
│   │   │   │   └── UploadForm.jsx
│   │   │   │
│   │   │   ├── Review/
│   │   │   │   ├── ReviewCard.jsx
│   │   │   │   ├── ReviewQueue.jsx
│   │   │   │   ├── ReviewForm.jsx
│   │   │   │   └── ImageViewer.jsx
│   │   │   │
│   │   │   ├── Analytics/
│   │   │   │   ├── UtilizationChart.jsx
│   │   │   │   ├── BreakdownChart.jsx
│   │   │   │   ├── TrendChart.jsx
│   │   │   │   └── OperatorPerformance.jsx
│   │   │   │
│   │   │   ├── Common/
│   │   │   │   ├── Header.jsx
│   │   │   │   ├── Sidebar.jsx
│   │   │   │   ├── Navigation.jsx
│   │   │   │   ├── Loading.jsx
│   │   │   │   └── ErrorBoundary.jsx
│   │   │   │
│   │   │   └── Layout/
│   │   │       ├── MainLayout.jsx
│   │   │       └── AuthLayout.jsx
│   │   │
│   │   # State Management
│   │   ├── store/
│   │   │   ├── checklist.store.js     # Zustand store
│   │   │   ├── review.store.js
│   │   │   ├── analytics.store.js
│   │   │   └── auth.store.js
│   │   │
│   │   # API Integration
│   │   ├── api/
│   │   │   ├── client.js              # Axios instance with interceptors
│   │   │   ├── checklist.api.js       # Checklist endpoints
│   │   │   ├── review.api.js          # Review endpoints
│   │   │   ├── analytics.api.js       # Analytics endpoints
│   │   │   └── auth.api.js            # Authentication endpoints
│   │   │
│   │   # Utilities
│   │   ├── utils/
│   │   │   ├── constants.js           # Constants & enums
│   │   │   ├── formatters.js          # Data formatting functions
│   │   │   ├── validators.js          # Form validation
│   │   │   └── helpers.js             # General utilities
│   │   │
│   │   # Hooks
│   │   ├── hooks/
│   │   │   ├── useUpload.js
│   │   │   ├── useReview.js
│   │   │   ├── useAnalytics.js
│   │   │   └── useAuth.js
│   │   │
│   │   # Styles
│   │   ├── styles/
│   │   │   ├── index.css              # Global styles
│   │   │   ├── tailwind.css           # Tailwind directives
│   │   │   └── components.css         # Component-specific styles
│   │   │
│   │   └── assets/
│   │       ├── images/
│   │       ├── icons/
│   │       └── logos/
│   │
│   ├── public/
│   │   └── index.html
│   │
│   ├── tests/
│   │   ├── components.test.jsx
│   │   ├── api.test.js
│   │   └── store.test.js
│   │
│   └── .env.example
│
# MOBILE APP (Optional - React Native)
├── mobile/
│   ├── app.json                       # Expo configuration
│   ├── package.json
│   ├── App.tsx                        # Root component
│   │
│   ├── src/
│   │   ├── screens/
│   │   │   ├── HomeScreen.tsx
│   │   │   ├── CameraScreen.tsx       # Camera for photo capture
│   │   │   ├── ReviewScreen.tsx
│   │   │   └── SettingsScreen.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── CameraView.tsx
│   │   │   ├── ImagePreview.tsx
│   │   │   ├── FormField.tsx
│   │   │   └── Navigation.tsx
│   │   │
│   │   ├── services/
│   │   │   ├── api.ts
│   │   │   ├── camera.ts
│   │   │   └── storage.ts
│   │   │
│   │   ├── store/
│   │   │   └── app.store.ts
│   │   │
│   │   └── utils/
│   │       ├── constants.ts
│   │       └── helpers.ts
│   │
│   ├── tests/
│   │   └── screens.test.tsx
│   │
│   └── .env.example
│
# ML & DATA
├── ml/
│   ├── datasets/
│   │   ├── train/                    # Training samples (500+ images)
│   │   │   ├── truck/
│   │   │   │   ├── images/
│   │   │   │   └── labels.csv
│   │   │   └── loader/
│   │   │       ├── images/
│   │   │       └── labels.csv
│   │   │
│   │   ├── test/                     # Test samples (100+ images)
│   │   │   ├── truck/
│   │   │   └── loader/
│   │   │
│   │   └── val/                      # Validation samples
│   │       ├── truck/
│   │       └── loader/
│   │
│   ├── models/                       # Fine-tuned model checkpoints
│   │   ├── trocr-time/
│   │   ├── trocr-code/
│   │   ├── trocr-text/
│   │   └── layout-detection/
│   │
│   ├── training/
│   │   ├── train_trocr.ipynb         # Training notebook
│   │   ├── train_time_model.ipynb
│   │   ├── train_code_model.ipynb
│   │   ├── train_text_model.ipynb
│   │   ├── evaluate.ipynb            # Model evaluation
│   │   └── logs/                     # Training logs (tensorboard)
│   │
│   ├── notebooks/
│   │   ├── eda.ipynb                 # Exploratory data analysis
│   │   ├── data_annotation.ipynb     # Manual labeling
│   │   └── model_comparison.ipynb    # Compare different approaches
│   │
│   └── docs/
│       ├── DATASET_STRUCTURE.md
│       ├── TRAINING_GUIDE.md
│       └── MODEL_PERFORMANCE.md
│
# DATA & SAMPLES
├── data/
│   ├── samples/
│   │   ├── truck_checklist_1.jpg     # Example images
│   │   ├── loader_checklist_1.jpg
│   │   └── cell_samples/
│   │
│   ├── exports/                      # Exported analytics data
│   │   ├── utilization_report.csv
│   │   └── breakdown_analysis.json
│   │
│   └── uploads/                      # Uploaded checklist images (auto-created)
│       ├── 2026-04-02/
│       │   ├── checklist_uuid_001.jpg
│       │   └── cells/
│       │       └── processed_cells/
│       └── 2026-04-03/
│
# DEVOPS & INFRASTRUCTURE
├── devops/
│   ├── docker/
│   │   ├── Dockerfile                # Backend container
│   │   ├── Dockerfile.frontend       # Frontend container
│   │   └── Dockerfile.ml             # ML worker container
│   │
│   ├── docker-compose.yml            # Local development stack
│   ├── docker-compose.prod.yml       # Production stack
│   │
│   ├── kubernetes/                   # K8s manifests (optional)
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── configmap.yaml
│   │
│   ├── nginx/
│   │   ├── Dockerfile
│   │   ├── nginx.conf                # Reverse proxy config
│   │   └── ssl/                      # SSL certificates (prod)
│   │
│   ├── scripts/
│   │   ├── deploy.sh                 # Deployment script
│   │   ├── backup.sh                 # Database backup script
│   │   ├── health_check.sh           # Health monitoring
│   │   └── migrate.sh                # Migration script
│   │
│   └── monitoring/
│       ├── prometheus.yml            # Prometheus config
│       ├── grafana-dashboard.json    # Grafana dashboard
│       └── alerting_rules.yml        # Alert definitions
│
# DOCUMENTATION
├── docs/
│   ├── GETTING_STARTED.md            # Quick start guide
│   ├── ARCHITECTURE.md               # System architecture
│   ├── API_DOCUMENTATION.md          # API reference
│   ├── DATABASE_SCHEMA.md            # Database design
│   ├── ML_PIPELINE.md                # ML system explanation
│   ├── DEPLOYMENT.md                 # Deployment guide
│   ├── TROUBLESHOOTING.md            # Common issues & solutions
│   │
│   ├── images/
│   │   ├── architecture_diagram.png
│   │   ├── data_flow.png
│   │   └── ui_mockups.png
│   │
│   └── research/
│       ├── TrOCR_paper.pdf
│       ├── Handwriting_Recognition_Survey.pdf
│       └── OCR_Best_Practices.md
│
# TESTS
├── tests/
│   ├── unit/
│   │   ├── test_preprocessing.py
│   │   ├── test_ocr.py
│   │   ├── test_postprocessing.py
│   │   ├── test_rule_engine.py
│   │   └── test_database.py
│   │
│   ├── integration/
│   │   ├── test_upload_pipeline.py
│   │   ├── test_api_endpoints.py
│   │   ├── test_database_integration.py
│   │   └── test_full_workflow.py
│   │
│   ├── e2e/
│   │   ├── test_user_flow.py
│   │   └── test_review_flow.py
│   │
│   ├── load/
│   │   ├── load_test.py              # Locust load test
│   │   └── k6_test.js                # K6 load test
│   │
│   ├── fixtures/
│   │   ├── sample_checklists/
│   │   ├── mock_api_responses.json
│   │   └── test_data.sql
│   │
│   └── conftest.py                   # Pytest configuration
│
# LOGS & MONITORING
├── logs/
│   ├── app.log                       # Application logs
│   ├── api.log                       # API request logs
│   ├── ocr.log                       # OCR pipeline logs
│   ├── error.log                     # Error logs
│   └── audit.log                     # Audit trail logs

# GIT & CI/CD
├── .github/
│   ├── workflows/
│   │   ├── test.yml                  # Run tests on push
│   │   ├── build.yml                 # Build Docker images
│   │   ├── deploy.yml                # Deploy to production
│   │   └── code_quality.yml          # Lint & type check
│   │
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   │
│   └── pull_request_template.md
│
├── .gitignore
├── .gitattributes
│
# CONFIG FILES
├── .env.example                      # Environment template
├── .editorconfig                     # Editor configuration
├── pytest.ini                        # Pytest configuration
├── pyproject.toml                    # Python project config
├── tsconfig.json                     # TypeScript config (if using TS)
├── eslintrc.json                     # ESLint config
│
# DOCUMENTATION
├── README.md                         # Project overview
├── CONTRIBUTING.md                   # Contribution guidelines
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md                      # Version history
├── LICENSE                           # MIT or similar
│
# ADDITIONAL
├── logs/                             # Runtime logs (auto-created)
│   ├── app_*.log
│   └── error_*.log
│
├── uploads/                          # User uploads (auto-created)
│   └── images/
│
├── models/                           # Downloaded model cache
│   └── trocr-large-handwritten/
│
└── .vscode/
    ├── settings.json                 # VS Code settings
    ├── extensions.json               # Recommended extensions
    └── launch.json                   # Debug configuration
```

---

## FILE CREATION ORDER

### Phase 0: Core Setup Files
```bash
1. requirements.txt              # Install dependencies
2. .env                         # Configuration
3. .gitignore                   # Git rules
4. README.md                    # Project overview
```

### Phase 1: Backend Structure
```bash
backend/
├── app/main.py               # FastAPI app
├── app/config.py             # Settings
├── app/database.py           # DB connection
└── app/routes/upload.py      # Upload endpoints
```

### Phase 2: Database
```bash
backend/
├── app/models/database.py    # ORM models
├── migrations/               # Alembic setup
└── app/services/checklist_service.py
```

### Phase 3: ML/OCR
```bash
backend/app/ml/
├── preprocessing.py
├── ocr.py
├── models.py
└── postprocessing.py
```

### Phase 4: Frontend
```bash
frontend/
├── src/pages/Upload.jsx
├── src/pages/Review.jsx
├── src/components/
└── src/api/
```

### Phase 5: Testing
```bash
tests/
├── unit/
├── integration/
└── fixtures/
```

---

## NOTES

- **Auto-Created Directories**: `venv/`, `uploads/`, `logs/`, `models/`, `node_modules/`
- **Git-Ignored**: All auto-created directories
- **Environment-Specific**: `.env` files should never be committed
- **Data**: Keep sample data in `data/samples/` for testing

---

## Quick Directory Creation

Run this script to create the full structure:

```bash
# From project root (ORC pro/)

# Backend
mkdir -p backend/app/{routes,models,services,ml,utils,middleware}
mkdir -p backend/{tests,migrations,logs}

# Frontend
mkdir -p frontend/src/{pages,components,store,api,utils,styles,assets}
mkdir -p frontend/{public,tests}

# Mobile (optional)
mkdir -p mobile/src/{screens,components,services,store}

# ML
mkdir -p ml/{datasets/{train,test,val},models,training,notebooks}

# Data
mkdir -p data/{samples,exports}

# DevOps
mkdir -p devops/{docker,kubernetes,nginx,scripts,monitoring}

# Docs
mkdir -p docs/{images,research}

# Tests
mkdir -p tests/{unit,integration,e2e,load,fixtures}

echo "✓ Directory structure created successfully!"
```

