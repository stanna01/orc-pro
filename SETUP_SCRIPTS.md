# AUTOMATED SETUP SCRIPTS

## For Windows PowerShell

Save as: `setup.ps1`

```powershell
# ORC PRO - Automated Setup Script
# Run as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ORC PRO - Mining Checklist System Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[1/8] Checking Python installation..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
    Write-Host "ERROR: Python not found. Please install Python 3.10+ from https://www.python.org" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Python found: $($python.Version)" -ForegroundColor Green

# Check Node.js
Write-Host "[2/8] Checking Node.js installation..." -ForegroundColor Yellow
$node = Get-Command node -ErrorAction SilentlyContinue
if ($null -eq $node) {
    Write-Host "WARNING: Node.js not found. Skipping frontend setup." -ForegroundColor Yellow
} else {
    Write-Host "✓ Node.js found: $(node --version)" -ForegroundColor Green
}

# Create project structure
Write-Host "[3/8] Creating project structure..." -ForegroundColor Yellow
$dirs = @(
    "backend",
    "frontend",
    "mobile",
    "ml",
    "data",
    "docs",
    "tests",
    "devops"
)

foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Name $dir | Out-Null
        Write-Host "  ✓ Created .\$dir" -ForegroundColor Green
    }
}

# Create virtual environment
Write-Host "[4/8] Creating Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "✓ Virtual environment already exists" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "[5/8] Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"
Write-Host "✓ Virtual environment activated" -ForegroundColor Green

# Install Python packages
Write-Host "[6/8] Installing Python packages (this may take 3-5 minutes)..." -ForegroundColor Yellow
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
Write-Host "✓ Python packages installed" -ForegroundColor Green

# Setup Node.js packages (if available)
Write-Host "[7/8] Setting up Node.js packages..." -ForegroundColor Yellow
if ($null -ne (Get-Command npm -ErrorAction SilentlyContinue)) {
    Push-Location frontend
    npm install
    Pop-Location
    Write-Host "✓ Frontend packages installed" -ForegroundColor Green
} else {
    Write-Host "⊘ Node.js not found, skipping frontend setup" -ForegroundColor Yellow
}

# Create .env file
Write-Host "[8/8] Creating environment configuration..." -ForegroundColor Yellow
$env_content = @"
# Database
DATABASE_URL=postgresql://orc_user:secure_password@localhost:5432/orc_pro
SQLALCHEMY_DATABASE_URL=postgresql://orc_user:secure_password@localhost:5432/orc_pro

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Security
SECRET_KEY=your-secret-key-here-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Redis (for production)
REDIS_URL=redis://localhost:6379

# ML Models
MODEL_CACHE_DIR=./models
TROCR_MODEL=microsoft/trocr-large-handwritten
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log

# Environment
ENVIRONMENT=development
DEBUG=True
"@

if (-not (Test-Path ".env")) {
    $env_content | Out-File -FilePath ".env" -Encoding UTF8
    Write-Host "✓ Created .env file (update with your configuration)" -ForegroundColor Green
} else {
    Write-Host "✓ .env file already exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✓ Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Update .env file with your database credentials"
Write-Host "2. Setup PostgreSQL database"
Write-Host "3. Run migrations: alembic upgrade head"
Write-Host "4. Start backend: python -m uvicorn app.main:app --reload"
Write-Host "5. Start frontend: cd frontend && npm start"
Write-Host ""
Write-Host "Documentation: Check IMPLEMENTATION_ROADMAP.md for detailed instructions"
```

---

## For Linux/Mac

Save as: `setup.sh`

```bash
#!/bin/bash

# ORC PRO - Automated Setup Script

echo "========================================"
echo "ORC PRO - Mining Checklist System Setup"
echo "========================================"
echo ""

# Check Python
echo "[1/8] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found. Please install Python 3.10+"
    exit 1
fi
echo "✓ Python found: $(python3 --version)"

# Check Node.js
echo "[2/8] Checking Node.js installation..."
if command -v node &> /dev/null; then
    echo "✓ Node.js found: $(node --version)"
else
    echo "⊘ Node.js not found. Skipping frontend setup."
fi

# Create project structure
echo "[3/8] Creating project structure..."
for dir in backend frontend mobile ml data docs tests devops; do
    mkdir -p "$dir"
    echo "  ✓ Created ./$dir"
done

# Create virtual environment
echo "[4/8] Creating Python virtual environment..."
python3 -m venv venv
echo "✓ Virtual environment created"

# Activate virtual environment
echo "[5/8] Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# Install Python packages
echo "[6/8] Installing Python packages (this may take 3-5 minutes)..."
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
echo "✓ Python packages installed"

# Setup Node.js packages
echo "[7/8] Setting up Node.js packages..."
if command -v npm &> /dev/null; then
    cd frontend
    npm install
    cd ..
    echo "✓ Frontend packages installed"
else
    echo "⊘ Node.js not found, skipping frontend setup"
fi

# Create .env file
echo "[8/8] Creating environment configuration..."
cat > .env << 'EOF'
# Database
DATABASE_URL=postgresql://orc_user:secure_password@localhost:5432/orc_pro
SQLALCHEMY_DATABASE_URL=postgresql://orc_user:secure_password@localhost:5432/orc_pro

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Security
SECRET_KEY=your-secret-key-here-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Redis
REDIS_URL=redis://localhost:6379

# ML Models
MODEL_CACHE_DIR=./models
TROCR_MODEL=microsoft/trocr-large-handwritten
TESSERACT_PATH=/usr/bin/tesseract

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log

# Environment
ENVIRONMENT=development
DEBUG=True
EOF
echo "✓ Created .env file (update with your configuration)"

echo ""
echo "========================================"
echo "✓ Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Update .env file with your database credentials"
echo "2. Setup PostgreSQL database"
echo "3. Run migrations: alembic upgrade head"
echo "4. Start backend: python -m uvicorn app.main:app --reload"
echo "5. Start frontend: cd frontend && npm start"
echo ""
echo "Documentation: Check IMPLEMENTATION_ROADMAP.md for detailed instructions"
```

---

## requirements.txt

```txt
# WEB FRAMEWORK
fastapi==0.104.1
uvicorn==0.24.0
python-multipart==0.0.6
python-dotenv==1.0.0

# VALIDATION & AUTH
pydantic==2.5.0
pydantic-settings==2.1.0
python-jose==3.3.0
passlib==1.7.4
bcrypt==4.1.1

# DATABASE
psycopg2-binary==2.9.9
sqlalchemy==2.0.23
alembic==1.13.0
SQLAlchemy-Utils==0.41.1

# ASYNC & QUEUE
redis==5.0.1
celery==5.3.4
flower==2.0.1

# LOGGING & MONITORING
structlog==23.2.0
prometheus-client==0.19.0

# ML & OCR
torch==2.1.1
torchvision==0.16.1
transformers==4.35.2
datasets==2.15.0
accelerate==0.25.0
pytesseract==0.3.10

# IMAGE PROCESSING
opencv-python==4.8.1.78
opencv-contrib-python==4.8.1.78
Pillow==10.1.0
scikit-image==0.22.0

# TEXT PROCESSING
fuzzywuzzy==0.18.0
python-Levenshtein==0.21.1
textdistance==4.6.1
symspellpy==6.7.7

# TESTING
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-xdist==3.5.0

# CODE QUALITY
black==23.12.0
flake8==6.1.0
isort==5.13.2
mypy==1.7.1

# DATA SCIENCE
jupyter==1.0.0
matplotlib==3.8.2
pandas==2.1.3
numpy==1.24.3
scikit-learn==1.3.2

# MISC
requests==2.31.0
httpx==0.25.2
aiofiles==23.2.1
```

---

## PostgreSQL Quick Setup (Windows CMD)

Save as: `setup_postgres.bat`

```batch
@echo off
REM PostgreSQL Setup Script for Windows
REM Run as Administrator

echo Installing PostgreSQL...
echo.

REM Check if PostgreSQL is installed
psql --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: PostgreSQL not installed
    echo Download from: https://www.postgresql.org/download/windows/
    pause
    exit /b 1
)

echo Creating database and user...
REM Connect as postgres and create database
psql -U postgres -c "CREATE DATABASE orc_pro;"
psql -U postgres -c "CREATE USER orc_user WITH PASSWORD 'secure_password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE orc_pro TO orc_user;"

echo.
echo ✓ PostgreSQL setup complete!
echo.
pause
```

---

## Docker Compose Setup (Optional)

Save as: `docker-compose.yml`

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: orc_pro
      POSTGRES_USER: orc_user
      POSTGRES_PASSWORD: secure_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U orc_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://orc_user:secure_password@postgres:5432/orc_pro
      - REDIS_URL=redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - .:/app

volumes:
  postgres_data:
```

To use:
```bash
docker-compose up --build
```

---

## How to Run Setup

### On Windows:
```powershell
# Open PowerShell as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup.ps1
```

### On Linux/Mac:
```bash
chmod +x setup.sh
./setup.sh
```

---

## Verification Script

Save as: `verify_setup.py`

```python
#!/usr/bin/env python3

import sys
import importlib
from typing import Tuple

def check_package(package_name: str, import_name: str = None) -> Tuple[bool, str]:
    """Check if a package is installed"""
    if import_name is None:
        import_name = package_name
    
    try:
        module = importlib.import_module(import_name)
        version = getattr(module, '__version__', 'unknown')
        return True, version
    except ImportError:
        return False, "NOT INSTALLED"

print("=" * 50)
print("ORC PRO - Setup Verification")
print("=" * 50)

packages = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("pydantic", "pydantic"),
    ("sqlalchemy", "sqlalchemy"),
    ("psycopg2", "psycopg2"),
    ("torch", "torch"),
    ("transformers", "transformers"),
    ("cv2", "cv2"),
    ("pytest", "pytest"),
    ("celery", "celery"),
]

all_ok = True
for package, import_name in packages:
    ok, version = check_package(package, import_name)
    status = "✓" if ok else "✗"
    print(f"{status} {package:20} {version}")
    if not ok:
        all_ok = False

print("=" * 50)
if all_ok:
    print("✓ All packages installed!")
    sys.exit(0)
else:
    print("✗ Some packages missing. Run: pip install -r requirements.txt")
    sys.exit(1)
```

Run it:
```bash
python verify_setup.py
```

---

