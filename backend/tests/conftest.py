"""Pytest configuration and shared fixtures for backend tests.

This file contains pytest setup, fixtures, and configuration used
across all test modules.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
import os

# Set test environment variables before importing the app
os.environ["DEBUG"] = "true"
os.environ["ENVIRONMENT"] = "testing"


@pytest.fixture
def mock_env():
    """Mock environment variables for testing.

    Yields:
        dict: Environment variables dictionary.
    """
    env_vars = {
        "DEBUG": "true",
        "ENVIRONMENT": "testing",
        "APP_NAME": "ORC Pro",
        "APP_VERSION": "0.1.0",
        "DATABASE_URL": "sqlite:///./test_orc_pro.db",
        "DATABASE_ECHO": "false",
    }

    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


@pytest.fixture
def client(mock_env):
    """Create a FastAPI test client with mocked environment.

    Args:
        mock_env: Mocked environment variables.

    Yields:
        TestClient: FastAPI test client for making requests.
    """
    from backend.app.main import create_app

    app = create_app()
    yield TestClient(app)
