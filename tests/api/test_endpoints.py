"""
Tests for API endpoints.

This module tests all the API endpoints defined in endpoints.py,
including OCR, analysis, resources, and vocabulary endpoints.
"""

import io
from unittest.mock import patch

from runestone.core.exceptions import RunestoneError


class TestOCREndpoints:
    """Test cases for OCR-related endpoints."""

    def test_ocr_success(self, client_with_mock_processor):
        """Test successful OCR processing."""
        client, mock_processor_instance = client_with_mock_processor
        from runestone.schemas.ocr import OCRResult, RecognitionStatistics

        mock_ocr_result = OCRResult(
            transcribed_text="Hej, vad heter du?",
            recognition_statistics=RecognitionStatistics(
                total_elements=5,
                successfully_transcribed=5,
                unclear_uncertain=0,
                unable_to_recognize=0,
            ),
        )
        mock_processor_instance.run_ocr.return_value = mock_ocr_result

        # Create a mock image file
        image_content = b"fake image data"
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = client.post("/api/ocr", files=files)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["text"] == "Hej, vad heter du?"
        assert data["character_count"] == 18

        # Verify processor was called with image bytes
        mock_processor_instance.run_ocr.assert_called_once_with(image_content)

    def test_ocr_invalid_file_type(self, client):
        """Test OCR with invalid file type."""
        # Create a mock text file
        files = {"file": ("test.txt", io.BytesIO(b"text content"), "text/plain")}

        response = client.post("/api/ocr", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "Invalid file type" in data["detail"]

    def test_ocr_file_too_large(self, client):
        """Test OCR with file that's too large."""
        # Create a large file (11MB)
        large_content = b"x" * (11 * 1024 * 1024)
        files = {"file": ("large.jpg", io.BytesIO(large_content), "image/jpeg")}

        response = client.post("/api/ocr", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "File too large" in data["detail"]

    def test_ocr_processing_failure(self, client_with_mock_processor):
        """Test handling of OCR failure."""
        client, mock_processor_instance = client_with_mock_processor
        mock_processor_instance.run_ocr.side_effect = RunestoneError("OCR failed")

        # Create a mock image file
        image_content = b"fake image data"
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = client.post("/api/ocr", files=files)

        assert response.status_code == 500
        data = response.json()
        assert "OCR failed" in data["detail"]

    def test_ocr_unexpected_error(self, client_with_mock_processor):
        """Test handling of unexpected OCR errors."""
        client, mock_processor_instance = client_with_mock_processor
        mock_processor_instance.run_ocr.side_effect = Exception("Unexpected error")

        # Create a mock image file
        image_content = b"fake image data"
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = client.post("/api/ocr", files=files)

        assert response.status_code == 500
        data = response.json()
        assert "Unexpected error" in data["detail"]

    def test_ocr_no_file(self, client):
        """Test OCR without file upload."""
        response = client.post("/api/ocr")

        assert response.status_code == 422  # Validation error


class TestAnalysisEndpoints:
    """Test cases for content analysis endpoints."""

    def test_analyze_success(self, client_with_mock_processor):
        """Test successful content analysis."""
        client, mock_processor_instance = client_with_mock_processor

        from runestone.schemas.analysis import ContentAnalysis, GrammarFocus, SearchNeeded, VocabularyItem

        mock_analysis_result = ContentAnalysis(
            grammar_focus=GrammarFocus(
                topic="Swedish questions", explanation="Basic question formation", has_explicit_rules=False, rules=""
            ),
            vocabulary=[
                VocabularyItem(swedish="hej", english="hello", example_phrase=None, known=False),
                VocabularyItem(swedish="vad", english="what", example_phrase=None, known=True),
            ],
            core_topics=["questions", "greetings"],
            search_needed=SearchNeeded(
                should_search=True,
                query_suggestions=["Swedish question formation"],
            ),
        )
        mock_processor_instance.run_analysis.return_value = mock_analysis_result

        # Test request payload
        payload = {"text": "Hej, vad heter du?"}

        response = client.post("/api/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["grammar_focus"]["topic"] == "Swedish questions"
        assert len(data["vocabulary"]) == 2

        # Verify known field is present and correct
        assert data["vocabulary"][0]["swedish"] == "hej"
        assert data["vocabulary"][0]["known"] is False
        assert data["vocabulary"][1]["swedish"] == "vad"
        assert data["vocabulary"][1]["known"] is True

        # Verify processor was called with user from the mock processor
        # The user should be in the mock processor's call arguments
        args, kwargs = mock_processor_instance.run_analysis.call_args
        called_text, called_user = args
        assert called_text == "Hej, vad heter du?"

    def test_analyze_empty_text(self, client_with_mock_processor):
        """Test analysis with empty text."""
        client, mock_processor_instance = client_with_mock_processor
        mock_processor_instance.run_analysis.side_effect = RunestoneError("No text provided for analysis")

        payload = {"text": ""}

        response = client.post("/api/analyze", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "No text provided for analysis" in data["detail"]


class TestResourceEndpoints:
    """Test cases for resource search endpoints."""

    def test_resources_success(self, client_with_mock_processor):
        """Test successful resource search."""
        client, mock_processor_instance = client_with_mock_processor

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

        response = client.post("/api/resources", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Verify response
        assert data["extra_info"] == mock_extra_info

        # Verify processor was called with core_topics and search_needed
        call_args = mock_processor_instance.run_resource_search.call_args
        assert call_args.kwargs["core_topics"] == ["questions", "greetings"]
        assert call_args.kwargs["search_needed"].should_search is True
        assert call_args.kwargs["search_needed"].query_suggestions == [
            "Swedish question formation",
            "Basic Swedish grammar",
        ]


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

        # Search with wildcard "*" - "*ban*" should match "banan"
        response = client.get("/api/vocabulary?search_query=*ban*")
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
    def test_settings_dependency_injection(self, mock_settings, client):
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

    def test_save_vocabulary_with_enrichment_enabled(self, client_with_mock_vocabulary_service):
        """Test saving vocabulary with enrichment enabled."""
        client, mock_vocabulary_service = client_with_mock_vocabulary_service
        mock_vocabulary_service.save_vocabulary.return_value = {"message": "Vocabulary saved successfully"}

        # Request with enrichment enabled
        request_data = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Jag äter ett äpple.",
                }
            ],
            "enrich": True,
        }

        response = client.post("/api/vocabulary", json=request_data)

        # Verify response
        assert response.status_code == 200

        # Verify service was called with correct arguments
        mock_vocabulary_service.save_vocabulary.assert_called_once()
        call_args = mock_vocabulary_service.save_vocabulary.call_args
        # Check positional args: call_args.args[0] is items, call_args.args[1] is enrich
        # Verify items parameter (converted to VocabularyItemCreate objects by Pydantic)
        items_arg = call_args.args[0]
        assert len(items_arg) == 1
        assert items_arg[0].word_phrase == request_data["items"][0]["word_phrase"]
        assert items_arg[0].translation == request_data["items"][0]["translation"]
        assert items_arg[0].example_phrase == request_data["items"][0]["example_phrase"]
        assert call_args.args[1] == 1  # Verify user_id parameter
        assert call_args.args[2] is True  # Verify enrich parameter

    def test_save_vocabulary_with_enrichment_disabled(self, client_with_mock_vocabulary_service):
        """Test saving vocabulary with enrichment disabled."""
        client, mock_vocabulary_service = client_with_mock_vocabulary_service
        mock_vocabulary_service.save_vocabulary.return_value = {"message": "Vocabulary saved successfully"}

        # Request with enrichment disabled
        request_data = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Jag äter ett äpple.",
                }
            ],
            "enrich": False,
        }

        response = client.post("/api/vocabulary", json=request_data)

        # Verify response
        assert response.status_code == 200

        # Verify service was called with correct arguments
        mock_vocabulary_service.save_vocabulary.assert_called_once()
        call_args = mock_vocabulary_service.save_vocabulary.call_args
        # Check positional args: call_args.args[0] is items, call_args.args[1] is enrich
        # Verify items parameter (converted to VocabularyItemCreate objects by Pydantic)
        items_arg = call_args.args[0]
        assert len(items_arg) == 1
        assert items_arg[0].word_phrase == request_data["items"][0]["word_phrase"]
        assert items_arg[0].translation == request_data["items"][0]["translation"]
        assert items_arg[0].example_phrase == request_data["items"][0]["example_phrase"]
        assert call_args.args[1] == 1  # Verify user_id parameter
        assert call_args.args[2] is False  # Verify enrich parameter

    def test_save_vocabulary_enrichment_default_true(self, client_with_mock_vocabulary_service):
        """Test that enrichment defaults to True when not specified."""
        client, mock_vocabulary_service = client_with_mock_vocabulary_service
        mock_vocabulary_service.save_vocabulary.return_value = {"message": "Vocabulary saved successfully"}

        # Request without enrich field
        request_data = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Jag äter ett äpple.",
                }
            ]
        }

        response = client.post("/api/vocabulary", json=request_data)

        # Verify response
        assert response.status_code == 200

        # Verify service was called with correct arguments (default enrich=True)
        mock_vocabulary_service.save_vocabulary.assert_called_once()
        call_args = mock_vocabulary_service.save_vocabulary.call_args
        # Check positional args: call_args.args[0] is items, call_args.args[1] is enrich (default True)
        # Verify items parameter (converted to VocabularyItemCreate objects by Pydantic)
        items_arg = call_args.args[0]
        assert len(items_arg) == 1
        assert items_arg[0].word_phrase == request_data["items"][0]["word_phrase"]
        assert items_arg[0].translation == request_data["items"][0]["translation"]
        assert items_arg[0].example_phrase == request_data["items"][0]["example_phrase"]
        assert call_args.args[1] == 1  # Verify user_id parameter
        assert call_args.args[2] is True  # Verify enrich parameter (default value)

    def test_get_vocabulary_with_precise_search(self, client):
        """Test the precise search functionality via API."""
        # Save test data with case variations and partial matches
        payload = {
            "items": [
                {
                    "word_phrase": "apple",
                    "translation": "äpple",
                },
                {
                    "word_phrase": "APPLE",
                    "translation": "ÄPPLE",
                },
                {
                    "word_phrase": "pineapple",
                    "translation": "ananas",
                },
                {
                    "word_phrase": "app",
                    "translation": "app",
                },
            ]
        }
        client.post("/api/vocabulary", json=payload)

        # Test precise=False (default) - should match all containing "apple"
        response = client.get("/api/vocabulary?search_query=apple&precise=false")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # apple, APPLE, pineapple
        phrases = [item["word_phrase"] for item in data]
        assert "apple" in phrases
        assert "APPLE" in phrases
        assert "pineapple" in phrases
        assert "app" not in phrases  # No partial match

        # Test precise=True - should match only exact case-insensitive
        response = client.get("/api/vocabulary?search_query=apple&precise=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2  # apple and APPLE
        phrases = [item["word_phrase"] for item in data]
        assert "apple" in phrases
        assert "APPLE" in phrases
        assert "pineapple" not in phrases
        assert "app" not in phrases

        # Test default precise behavior (should be False)
        response = client.get("/api/vocabulary?search_query=apple")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # Same as precise=false

        # Test precise search for non-existent term
        response = client.get("/api/vocabulary?search_query=banana&precise=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

        # Test precise search with case sensitivity difference
        response = client.get("/api/vocabulary?search_query=PINEAPPLE&precise=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "pineapple"

    def test_get_vocabulary_invalid_limit(self, client):
        """Test get_vocabulary with invalid limit values."""
        # Test limit too high
        response = client.get("/api/vocabulary?limit=101")
        assert response.status_code == 400
        data = response.json()
        assert "Limit must be between 1 and 100" in data["detail"]

        # Test limit too low
        response = client.get("/api/vocabulary?limit=0")
        assert response.status_code == 400
        data = response.json()
        assert "Limit must be between 1 and 100" in data["detail"]

        # Test negative limit
        response = client.get("/api/vocabulary?limit=-1")
        assert response.status_code == 400
        data = response.json()
        assert "Limit must be between 1 and 100" in data["detail"]

    def test_get_vocabulary_limit_bounds(self, client):
        """Test get_vocabulary with valid limit bounds."""
        # Save multiple items
        payload = {"items": [{"word_phrase": f"word_{i}", "translation": f"trans_{i}"} for i in range(5)]}
        client.post("/api/vocabulary", json=payload)

        # Test minimum valid limit
        response = client.get("/api/vocabulary?limit=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        # Test maximum valid limit
        response = client.get("/api/vocabulary?limit=100")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5  # All items

        # Test default limit (should be 100)
        response = client.get("/api/vocabulary")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
