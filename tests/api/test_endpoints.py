"""
Tests for API endpoints.

This module tests all the API endpoints defined in endpoints.py,
including OCR, analysis, resources, and vocabulary endpoints.
"""

import io
from unittest.mock import Mock, patch

from runestone.core.exceptions import RunestoneError


class TestOCREndpoints:
    """Test cases for OCR-related endpoints."""

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_ocr_success(self, mock_processor, client_no_db):
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

        response = client_no_db.post("/api/ocr", files=files)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["text"] == "Hej, vad heter du?"
        assert data["character_count"] == 17

        # Verify processor was called with image bytes
        mock_processor.assert_called_once()
        mock_processor_instance.run_ocr.assert_called_once_with(image_content)

    def test_ocr_invalid_file_type(self, client_no_db):
        """Test OCR with invalid file type."""
        # Create a mock text file
        files = {"file": ("test.txt", io.BytesIO(b"text content"), "text/plain")}

        response = client_no_db.post("/api/ocr", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "Invalid file type" in data["detail"]

    def test_ocr_file_too_large(self, client_no_db):
        """Test OCR with file that's too large."""
        # Create a large file (11MB)
        large_content = b"x" * (11 * 1024 * 1024)
        files = {"file": ("large.jpg", io.BytesIO(large_content), "image/jpeg")}

        response = client_no_db.post("/api/ocr", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "File too large" in data["detail"]

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_ocr_processing_failure(self, mock_processor, client_no_db):
        """Test handling of OCR failure."""
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance
        mock_processor_instance.run_ocr.side_effect = RunestoneError("OCR failed")

        # Create a mock image file
        image_content = b"fake image data"
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = client_no_db.post("/api/ocr", files=files)

        assert response.status_code == 500
        data = response.json()
        assert "OCR failed" in data["detail"]

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_ocr_unexpected_error(self, mock_processor, client_no_db):
        """Test handling of unexpected OCR errors."""
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance
        mock_processor_instance.run_ocr.side_effect = Exception("Unexpected error")

        # Create a mock image file
        image_content = b"fake image data"
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = client_no_db.post("/api/ocr", files=files)

        assert response.status_code == 500
        data = response.json()
        assert "Unexpected error" in data["detail"]

    def test_ocr_no_file(self, client_no_db):
        """Test OCR without file upload."""
        response = client_no_db.post("/api/ocr")

        assert response.status_code == 422  # Validation error


class TestAnalysisEndpoints:
    """Test cases for content analysis endpoints."""

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_analyze_success(self, mock_processor, client_no_db):
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
            "search_needed": {"should_search": True, "query_suggestions": ["Swedish question formation"]},
        }
        mock_processor_instance.run_analysis.return_value = mock_analysis_result

        # Test request payload
        payload = {"text": "Hej, vad heter du?"}

        response = client_no_db.post("/api/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["grammar_focus"]["topic"] == "Swedish questions"
        assert len(data["vocabulary"]) == 2

        # Verify processor was called
        mock_processor.assert_called_once()
        mock_processor_instance.run_analysis.assert_called_once_with("Hej, vad heter du?")

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_analyze_empty_text(self, mock_processor, client_no_db):
        """Test analysis with empty text."""
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance
        mock_processor_instance.run_analysis.side_effect = RunestoneError("No text provided for analysis")

        payload = {"text": ""}

        response = client_no_db.post("/api/analyze", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "No text provided for analysis" in data["detail"]


class TestResourceEndpoints:
    """Test cases for resource search endpoints."""

    @patch("runestone.api.endpoints.RunestoneProcessor")
    def test_resources_success(self, mock_processor, client_no_db):
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
                    "query_suggestions": ["Swedish question formation", "Basic Swedish grammar"],
                },
            }
        }

        response = client_no_db.post("/api/resources", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Verify response
        assert data["extra_info"] == mock_extra_info

        # Verify processor was called with minimal data
        mock_processor.assert_called_once()
        mock_processor_instance.run_resource_search.assert_called_once_with(
            {
                "search_needed": {
                    "query_suggestions": ["Swedish question formation", "Basic Swedish grammar"],
                    "should_search": True,
                },
                "core_topics": ["questions", "greetings"],
            }
        )


class TestVocabularyEndpoints:
    """Test cases for vocabulary endpoints."""

    def test_save_vocabulary_success(self, client):
        """Test successful vocabulary saving."""
        payload = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Jag äter ett äpple varje dag.",
                },
                {"word_phrase": "en banan", "translation": "a banana", "example_phrase": None},
            ]
        }

        response = client.post("/api/vocabulary", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Vocabulary saved successfully"

    def test_save_vocabulary_duplicate(self, client):
        """Test saving vocabulary with duplicates."""
        # First save
        payload = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Jag äter ett äpple varje dag.",
                }
            ]
        }
        client.post("/api/vocabulary", json=payload)

        # Second save with same word_phrase
        payload2 = {
            "items": [{"word_phrase": "ett äpple", "translation": "an apple", "example_phrase": "Ett äpple är rött."}]
        }
        response = client.post("/api/vocabulary", json=payload2)

        assert response.status_code == 200

        # Check that only one entry exists
        response = client.get("/api/vocabulary")
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "ett äpple"
        assert data[0]["example_phrase"] == "Jag äter ett äpple varje dag."

    def test_get_vocabulary_empty(self, client):
        """Test getting vocabulary when database is empty."""
        response = client.get("/api/vocabulary")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_vocabulary_with_data(self, client):
        """Test getting vocabulary with data."""
        # Save some data first
        payload = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Jag äter ett äpple varje dag.",
                }
            ]
        }
        client.post("/api/vocabulary", json=payload)

        # Get the data
        response = client.get("/api/vocabulary")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        vocab = data[0]
        assert vocab["word_phrase"] == "ett äpple"
        assert vocab["translation"] == "an apple"
        assert vocab["example_phrase"] == "Jag äter ett äpple varje dag."
        assert vocab["user_id"] == 1
        assert vocab["in_learn"] is True
        assert vocab["last_learned"] is None
        assert "id" in vocab
        assert "created_at" in vocab
        assert "updated_at" in vocab

    def test_save_vocabulary_item_success(self, client):
        """Test successful saving of a single vocabulary item."""
        payload = {
            "word_phrase": "ett äpple",
            "translation": "an apple",
            "example_phrase": "Jag äter ett äpple varje dag.",
        }

        response = client.post("/api/vocabulary/item", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["word_phrase"] == "ett äpple"
        assert data["translation"] == "an apple"
        assert data["example_phrase"] == "Jag äter ett äpple varje dag."
        assert data["user_id"] == 1
        assert data["in_learn"] is True
        assert data["last_learned"] is None
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_save_vocabulary_item_duplicate(self, client):
        """Test saving a duplicate vocabulary item raises an error."""
        # First save
        payload = {
            "word_phrase": "ett äpple",
            "translation": "an apple",
            "example_phrase": "Jag äter ett äpple varje dag.",
        }
        response1 = client.post("/api/vocabulary/item", json=payload)
        assert response1.status_code == 200
        data1 = response1.json()
        item_id = data1["id"]

        # Second save with same word_phrase
        payload2 = {
            "word_phrase": "ett äpple",
            "translation": "an apple",
            "example_phrase": "Ett äpple är rött.",
        }
        response2 = client.post("/api/vocabulary/item", json=payload2)

        assert response2.status_code == 400
        data2 = response2.json()
        assert "already exists" in data2["detail"]

        # Verify no new item was created and existing item remains unchanged
        response3 = client.get("/api/vocabulary")
        data3 = response3.json()
        assert len(data3) == 1
        existing_item = data3[0]
        assert existing_item["id"] == item_id
        assert existing_item["word_phrase"] == "ett äpple"
        assert existing_item["example_phrase"] == "Jag äter ett äpple varje dag."

    def test_save_vocabulary_item_without_example(self, client):
        """Test saving a vocabulary item without example phrase."""
        payload = {
            "word_phrase": "en banan",
            "translation": "a banana",
        }

        response = client.post("/api/vocabulary/item", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["word_phrase"] == "en banan"
        assert data["translation"] == "a banana"
        assert data["example_phrase"] is None

    def test_get_vocabulary_with_search(self, client):
        """Test getting vocabulary with search query."""
        # Save some test data
        payload = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Jag äter ett äpple varje dag.",
                },
                {
                    "word_phrase": "en banan",
                    "translation": "a banana",
                    "example_phrase": None,
                },
                {
                    "word_phrase": "ett päron",
                    "translation": "a pear",
                    "example_phrase": None,
                },
            ]
        }
        client.post("/api/vocabulary", json=payload)

        # Search for "banan" - should find one match
        response = client.get("/api/vocabulary?search_query=banan")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "en banan"

        # Search for "ett" - should find two matches
        response = client.get("/api/vocabulary?search_query=ett")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Should be ordered by created_at descending
        assert data[0]["word_phrase"] == "ett päron"  # Most recent
        assert data[1]["word_phrase"] == "ett äpple"

        # Search with wildcard "*" - "ban*" should match "banan"
        response = client.get("/api/vocabulary?search_query=ban*")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "en banan"

        # Search case-insensitive - "BANAN" should match "banan"
        response = client.get("/api/vocabulary?search_query=BANAN")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "en banan"

        # Search for non-existent term
        response = client.get("/api/vocabulary?search_query=xyz")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

        # Test with limit
        response = client.get("/api/vocabulary?search_query=ett&limit=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "ett päron"  # Most recent


class TestSettingsDependency:
    """Test cases for dependency injection."""

    @patch("runestone.dependencies.settings")
    def test_settings_dependency_injection(self, mock_settings, client_no_db):
        """Test that settings are properly injected."""
        mock_settings.llm_provider = "test_provider"
        mock_settings.verbose = True

        # This test verifies that the settings dependency injection works
        # by checking that our mock settings are used
        from runestone.dependencies import get_settings

        result = get_settings()
        assert result == mock_settings

    def test_update_vocabulary_success(self, client):
        """Test successful vocabulary update."""
        # First, save some vocabulary
        payload = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Jag äter ett äpple varje dag.",
                }
            ]
        }
        client.post("/api/vocabulary", json=payload)

        # Get the item to find its ID
        response = client.get("/api/vocabulary")
        data = response.json()
        item_id = data[0]["id"]

        # Update the item
        update_payload = {
            "word_phrase": "ett rött äpple",
            "translation": "a red apple",
            "in_learn": False,
        }
        response = client.put(f"/api/vocabulary/{item_id}", json=update_payload)

        assert response.status_code == 200
        updated_data = response.json()
        assert updated_data["word_phrase"] == "ett rött äpple"
        assert updated_data["translation"] == "a red apple"
        assert updated_data["example_phrase"] == "Jag äter ett äpple varje dag."  # Unchanged
        assert updated_data["in_learn"] is False

    def test_update_vocabulary_partial(self, client):
        """Test updating vocabulary with partial fields."""
        # First, save some vocabulary
        payload = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Jag äter ett äpple varje dag.",
                }
            ]
        }
        client.post("/api/vocabulary", json=payload)

        # Get the item to find its ID
        response = client.get("/api/vocabulary")
        data = response.json()
        item_id = data[0]["id"]

        # Update only one field
        update_payload = {"in_learn": False}
        response = client.put(f"/api/vocabulary/{item_id}", json=update_payload)

        assert response.status_code == 200
        updated_data = response.json()
        assert updated_data["word_phrase"] == "ett äpple"  # Unchanged
        assert updated_data["translation"] == "an apple"  # Unchanged
        assert updated_data["in_learn"] is False

    def test_update_vocabulary_not_found(self, client):
        """Test updating a non-existent vocabulary item."""
        update_payload = {"word_phrase": "new phrase"}
        response = client.put("/api/vocabulary/999", json=update_payload)

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"]

    def test_update_vocabulary_invalid_data(self, client):
        """Test updating vocabulary with invalid data."""
        # First, save some vocabulary
        payload = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                }
            ]
        }
        client.post("/api/vocabulary", json=payload)

        # Get the item to find its ID
        response = client.get("/api/vocabulary")
        data = response.json()
        item_id = data[0]["id"]

        # Try to update with invalid data (empty word_phrase)
        update_payload = {"word_phrase": ""}
        response = client.put(f"/api/vocabulary/{item_id}", json=update_payload)

        # Should still succeed since word_phrase is optional in update
        assert response.status_code == 200

    def test_delete_vocabulary_success(self, client):
        """Test successful vocabulary item deletion."""
        # First, save some vocabulary
        payload = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Jag äter ett äpple varje dag.",
                }
            ]
        }
        client.post("/api/vocabulary", json=payload)

        # Get the item to find its ID
        response = client.get("/api/vocabulary")
        data = response.json()
        item_id = data[0]["id"]

        # Delete the item
        response = client.delete(f"/api/vocabulary/{item_id}")

        assert response.status_code == 200
        delete_data = response.json()
        assert delete_data["message"] == "Vocabulary item deleted successfully"

        # Verify item is completely removed
        response = client.get("/api/vocabulary")
        data = response.json()
        assert len(data) == 0

    def test_delete_vocabulary_not_found(self, client):
        """Test deleting a non-existent vocabulary item."""
        response = client.delete("/api/vocabulary/999")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"]
