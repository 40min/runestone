"""
API tests for Runestone web application.

This module contains tests for the FastAPI endpoints and API functionality.
"""

import io
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from runestone.api.main import app
from runestone.config import Settings
from runestone.core.exceptions import RunestoneError


class TestAPI:
    """Test cases for the Runestone API."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.settings = Settings()

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "runestone-api"

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_process_image_success(self, mock_processor):
        """Test successful image processing."""
        # Mock processor and results
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance

        mock_results = {
            "ocr_result": {
                "text": "Hej, vad heter du?",
                "character_count": 17,
            },
            "analysis": {
                "grammar_focus": {
                    "topic": "Swedish questions",
                    "explanation": "Basic question formation",
                    "has_explicit_rules": False,
                },
                "vocabulary": [
                    {"swedish": "hej", "english": "hello"},
                    {"swedish": "vad", "english": "what"},
                ],
            },
            "extra_info": "Additional learning resources",
            "processing_successful": True,
        }
        mock_processor_instance.process_image.return_value = mock_results

        # Create a mock image file
        image_content = b"fake image data"
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = self.client.post("/api/process", files=files)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["processing_successful"] is True
        assert data["ocr_result"]["text"] == "Hej, vad heter du?"
        assert data["ocr_result"]["character_count"] == 17
        assert data["analysis"]["grammar_focus"]["topic"] == "Swedish questions"
        assert len(data["analysis"]["vocabulary"]) == 2
        assert data["extra_info"] == "Additional learning resources"

        # Verify processor was called
        mock_processor.assert_called_once()
        mock_processor_instance.process_image.assert_called_once()

    def test_process_image_invalid_file_type(self):
        """Test processing with invalid file type."""
        # Create a mock text file
        files = {"file": ("test.txt", io.BytesIO(b"text content"), "text/plain")}

        response = self.client.post("/api/process", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "Invalid file type" in data["detail"]

    def test_process_image_file_too_large(self):
        """Test processing with file that's too large."""
        # Create a large file (11MB)
        large_content = b"x" * (11 * 1024 * 1024)
        files = {"file": ("large.jpg", io.BytesIO(large_content), "image/jpeg")}

        response = self.client.post("/api/process", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "File too large" in data["detail"]

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_process_image_processing_failure(self, mock_processor):
        """Test handling of processing failure."""
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance
        mock_processor_instance.process_image.side_effect = RunestoneError("OCR failed")

        # Create a mock image file
        image_content = b"fake image data"
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = self.client.post("/api/process", files=files)

        assert response.status_code == 500
        data = response.json()
        assert "Processing failed" in data["detail"]

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_process_image_unexpected_error(self, mock_processor):
        """Test handling of unexpected errors."""
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance
        mock_processor_instance.process_image.side_effect = Exception("Unexpected error")

        # Create a mock image file
        image_content = b"fake image data"
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = self.client.post("/api/process", files=files)

        assert response.status_code == 500
        data = response.json()
        assert "Unexpected error" in data["detail"]

    def test_process_image_no_file(self):
        """Test processing without file upload."""
        response = self.client.post("/api/process")

        assert response.status_code == 422  # Validation error

    @patch("runestone.api.endpoints.settings")
    def test_settings_dependency_injection(self, mock_settings):
        """Test that settings are properly injected."""
        mock_settings.llm_provider = "test_provider"
        mock_settings.verbose = True

        # This test verifies that the settings dependency injection works
        # by checking that our mock settings are used
        from runestone.api.endpoints import get_settings

        result = get_settings()
        assert result == mock_settings
