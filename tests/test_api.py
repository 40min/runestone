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
    def test_ocr_success(self, mock_processor):
        """Test successful OCR processing."""
        # Mock processor
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance

        mock_ocr_result = {
            "text": "Hej, vad heter du?",
            "character_count": 17,
        }
        mock_processor_instance.run_ocr.return_value = mock_ocr_result

        # Create a mock image file
        image_content = b"fake image data"
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = self.client.post("/api/ocr", files=files)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["text"] == "Hej, vad heter du?"
        assert data["character_count"] == 17

        # Verify processor was called with image bytes
        mock_processor.assert_called_once()
        mock_processor_instance.run_ocr.assert_called_once_with(image_content)

    def test_ocr_invalid_file_type(self):
        """Test OCR with invalid file type."""
        # Create a mock text file
        files = {"file": ("test.txt", io.BytesIO(b"text content"), "text/plain")}

        response = self.client.post("/api/ocr", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "Invalid file type" in data["detail"]

    def test_ocr_file_too_large(self):
        """Test OCR with file that's too large."""
        # Create a large file (11MB)
        large_content = b"x" * (11 * 1024 * 1024)
        files = {"file": ("large.jpg", io.BytesIO(large_content), "image/jpeg")}

        response = self.client.post("/api/ocr", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "File too large" in data["detail"]

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_ocr_processing_failure(self, mock_processor):
        """Test handling of OCR failure."""
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance
        mock_processor_instance.run_ocr.side_effect = RunestoneError("OCR failed")

        # Create a mock image file
        image_content = b"fake image data"
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = self.client.post("/api/ocr", files=files)

        assert response.status_code == 500
        data = response.json()
        assert "OCR failed" in data["detail"]

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_ocr_unexpected_error(self, mock_processor):
        """Test handling of unexpected OCR errors."""
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance
        mock_processor_instance.run_ocr.side_effect = Exception("Unexpected error")

        # Create a mock image file
        image_content = b"fake image data"
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = self.client.post("/api/ocr", files=files)

        assert response.status_code == 500
        data = response.json()
        assert "Unexpected error" in data["detail"]

    def test_ocr_no_file(self):
        """Test OCR without file upload."""
        response = self.client.post("/api/ocr")

        assert response.status_code == 422  # Validation error

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_analyze_success(self, mock_processor):
        """Test successful content analysis."""
        # Mock processor
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance

        mock_analysis_result = {
            "grammar_focus": {
                "topic": "Swedish questions",
                "explanation": "Basic question formation",
                "has_explicit_rules": False,
            },
            "vocabulary": [
                {"swedish": "hej", "english": "hello"},
                {"swedish": "vad", "english": "what"},
            ],
            "core_topics": ["questions", "greetings"],
            "search_needed": {
                "should_search": True,
                "query_suggestions": ["Swedish question formation"]
            }
        }
        mock_processor_instance.run_analysis.return_value = mock_analysis_result

        # Test request payload
        payload = {"text": "Hej, vad heter du?"}

        response = self.client.post("/api/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["grammar_focus"]["topic"] == "Swedish questions"
        assert len(data["vocabulary"]) == 2

        # Verify processor was called
        mock_processor.assert_called_once()
        mock_processor_instance.run_analysis.assert_called_once_with("Hej, vad heter du?")

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_analyze_empty_text(self, mock_processor):
        """Test analysis with empty text."""
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance
        mock_processor_instance.run_analysis.side_effect = RunestoneError("No text provided for analysis")

        payload = {"text": ""}

        response = self.client.post("/api/analyze", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "No text provided for analysis" in data["detail"]

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_resources_success(self, mock_processor):
        """Test successful resource search."""
        # Mock processor
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance

        mock_extra_info = "Additional learning resources about Swedish questions"
        mock_processor_instance.run_resource_search.return_value = mock_extra_info

        # Test request payload with minimal required data
        payload = {
            "analysis": {
                "core_topics": ["questions", "greetings"],
                "search_needed": {
                    "should_search": True,
                    "query_suggestions": ["Swedish question formation", "Basic Swedish grammar"]
                }
            }
        }

        response = self.client.post("/api/resources", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Verify response
        assert data["extra_info"] == mock_extra_info

        # Verify processor was called with minimal data
        mock_processor.assert_called_once()
        mock_processor_instance.run_resource_search.assert_called_once_with({
            "search_needed": {
                "query_suggestions": ["Swedish question formation", "Basic Swedish grammar"],
                "should_search": True
            },
            "core_topics": ["questions", "greetings"]
        })

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