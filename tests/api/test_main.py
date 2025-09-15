"""
Tests for the main FastAPI application.

This module tests the FastAPI app setup, configuration, and basic endpoints
like health checks.
"""

from fastapi.testclient import TestClient

from runestone.api.main import app


class TestFastAPIApp:
    """Test cases for the FastAPI application setup."""

    def test_app_creation(self):
        """Test that the FastAPI app is created successfully."""
        assert app is not None
        assert app.title == "Runestone API"
        assert app.version == "1.0.0"

    def test_health_check_endpoint(self):
        """Test the health check endpoint."""
        client = TestClient(app)
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "runestone-api"

    def test_cors_middleware(self):
        """Test that CORS middleware is properly configured."""
        # Check that CORS headers are present in responses
        client = TestClient(app)
        response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})

        # Check CORS headers are present
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "access-control-allow-credentials" in response.headers

    def test_api_router_included(self):
        """Test that the API router is properly included."""
        # The /api/health endpoint should exist, indicating router is included
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200