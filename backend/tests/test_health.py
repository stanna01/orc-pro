"""Tests for health check endpoints.

Tests the /health, /health/ready, and /health/live endpoints
to ensure proper status reporting and error handling.
"""

import pytest
from datetime import datetime


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_check_returns_200(self, client):
        """Test that health check returns 200 status code.

        Args:
            client: FastAPI test client.
        """
        response = client.get("/health/")
        assert response.status_code == 200

    def test_health_check_response_structure(self, client):
        """Test that health check response has required fields.

        Args:
            client: FastAPI test client.
        """
        response = client.get("/health/")
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data

    def test_health_check_status_is_healthy(self, client):
        """Test that health check status is 'healthy'.

        Args:
            client: FastAPI test client.
        """
        response = client.get("/health/")
        data = response.json()

        assert data["status"] == "healthy"
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_health_check_version_format(self, client):
        """Test that version follows semantic versioning.

        Args:
            client: FastAPI test client.
        """
        response = client.get("/health/")
        data = response.json()

        version = data["version"]
        parts = version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    def test_health_check_timestamp_is_valid_iso(self, client):
        """Test that timestamp is a valid ISO format datetime.

        Args:
            client: FastAPI test client.
        """
        response = client.get("/health/")
        data = response.json()

        # Should not raise exception
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        assert timestamp is not None

    def test_health_check_environment_is_set(self, client):
        """Test that environment is set to a valid value.

        Args:
            client: FastAPI test client.
        """
        response = client.get("/health/")
        data = response.json()

        assert data["environment"] in ["development", "staging", "production", "testing"]


class TestReadinessEndpoint:
    """Tests for GET /health/ready endpoint."""

    def test_readiness_check_returns_200(self, client):
        """Test that readiness check returns 200 status code.

        Args:
            client: FastAPI test client.
        """
        response = client.get("/health/ready")
        assert response.status_code == 200

    def test_readiness_check_response_structure(self, client):
        """Test that readiness check response has required fields.

        Args:
            client: FastAPI test client.
        """
        response = client.get("/health/ready")
        data = response.json()

        assert "ready" in data
        assert "timestamp" in data

    def test_readiness_check_ready_is_true(self, client):
        """Test that readiness check shows application is ready.

        Args:
            client: FastAPI test client.
        """
        response = client.get("/health/ready")
        data = response.json()

        assert data["ready"] is True


class TestLivenessEndpoint:
    """Tests for GET /health/live endpoint."""

    def test_liveness_check_returns_200(self, client):
        """Test that liveness check returns 200 status code.

        Args:
            client: FastAPI test client.
        """
        response = client.get("/health/live")
        assert response.status_code == 200

    def test_liveness_check_response_structure(self, client):
        """Test that liveness check response has required fields.

        Args:
            client: FastAPI test client.
        """
        response = client.get("/health/live")
        data = response.json()

        assert "alive" in data
        assert "timestamp" in data

    def test_liveness_check_alive_is_true(self, client):
        """Test that liveness check shows application is alive.

        Args:
            client: FastAPI test client.
        """
        response = client.get("/health/live")
        data = response.json()

        assert data["alive"] is True
