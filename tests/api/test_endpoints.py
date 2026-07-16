"""
Tests for API endpoints.

This module tests all the API endpoints defined in endpoints.py,
including OCR, analysis, and vocabulary endpoints.
"""

import io
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from runestone.api.endpoints import delete_vocabulary, update_vocabulary
from runestone.api.schemas import VocabularyUpdate
from runestone.core.exceptions import RunestoneError
from runestone.db.models import RecallQueueItemDB, RecallUserStateDB, Vocabulary
from runestone.recall.service import RecallService
from runestone.services.vocabulary_service import VocabularyService


class TestOCREndpoints:
    """Test cases for OCR-related endpoints."""

    async def test_ocr_success(self, client_with_mock_processor):
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

        response = await client.post("/api/ocr", files=files)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["text"] == "Hej, vad heter du?"
        assert data["character_count"] == 18

        # Verify processor was called with image bytes
        mock_processor_instance.run_ocr.assert_called_once_with(image_content)

    async def test_ocr_invalid_file_type(self, client):
        """Test OCR with invalid file type."""
        # Create a mock text file
        files = {"file": ("test.txt", io.BytesIO(b"text content"), "text/plain")}

        response = await client.post("/api/ocr", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "Invalid file type" in data["detail"]

    async def test_ocr_file_too_large(self, client):
        """Test OCR with file that's too large."""
        # Create a large file (11MB)
        large_content = b"x" * (11 * 1024 * 1024)
        files = {"file": ("large.jpg", io.BytesIO(large_content), "image/jpeg")}

        response = await client.post("/api/ocr", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "File too large" in data["detail"]

    async def test_ocr_processing_failure(self, client_with_mock_processor):
        """Test handling of OCR failure."""
        client, mock_processor_instance = client_with_mock_processor
        mock_processor_instance.run_ocr.side_effect = RunestoneError("OCR failed")

        # Create a mock image file
        image_content = b"fake image data"
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = await client.post("/api/ocr", files=files)

        assert response.status_code == 500
        data = response.json()
        assert "OCR failed" in data["detail"]

    async def test_ocr_unexpected_error(self, client_with_mock_processor):
        """Test handling of unexpected OCR errors."""
        client, mock_processor_instance = client_with_mock_processor
        mock_processor_instance.run_ocr.side_effect = Exception("Unexpected error")

        # Create a mock image file
        image_content = b"fake image data"
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = await client.post("/api/ocr", files=files)

        assert response.status_code == 500
        data = response.json()
        assert "Unexpected error" in data["detail"]

    async def test_ocr_no_file(self, client):
        """Test OCR without file upload."""
        response = await client.post("/api/ocr")

        assert response.status_code == 422  # Validation error


class TestAnalysisEndpoints:
    """Test cases for content analysis endpoints."""

    async def test_analyze_success(self, client_with_mock_processor):
        """Test successful content analysis."""
        client, mock_processor_instance = client_with_mock_processor

        from runestone.schemas.analysis import ContentAnalysis, GrammarFocus, VocabularyItem

        mock_analysis_result = ContentAnalysis(
            grammar_focus=GrammarFocus(
                topic="Swedish questions", explanation="Basic question formation", has_explicit_rules=False, rules=""
            ),
            vocabulary=[
                VocabularyItem(swedish="hej", english="hello", example_phrase=None, known=False),
                VocabularyItem(swedish="vad", english="what", example_phrase=None, known=True),
            ],
            core_topics=["questions", "greetings"],
        )
        from unittest.mock import AsyncMock

        mock_processor_instance.run_analysis = AsyncMock(return_value=mock_analysis_result)

        # Test request payload
        payload = {"text": "Hej, vad heter du?"}

        response = await client.post("/api/analyze", json=payload)

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

    async def test_analyze_empty_text(self, client_with_mock_processor):
        """Test analysis with empty text."""
        client, mock_processor_instance = client_with_mock_processor
        mock_processor_instance.run_analysis.side_effect = RunestoneError("No text provided for analysis")

        payload = {"text": ""}

        response = await client.post("/api/analyze", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "No text provided for analysis" in data["detail"]


class TestVocabularyEndpoints:
    """Test cases for vocabulary endpoints."""

    async def test_save_vocabulary_success(self, client):
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

        response = await client.post("/api/vocabulary", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Vocabulary saved successfully"

    async def test_save_vocabulary_duplicate(self, client):
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
        await client.post("/api/vocabulary", json=payload)

        # Second save with same word_phrase
        payload2 = {
            "items": [{"word_phrase": "ett äpple", "translation": "an apple", "example_phrase": "Ett äpple är rött."}]
        }
        response = await client.post("/api/vocabulary", json=payload2)

        assert response.status_code == 200

        # Check that only one entry exists
        response = await client.get("/api/vocabulary")
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "ett äpple"
        assert data[0]["example_phrase"] == "Jag äter ett äpple varje dag."

    async def test_get_vocabulary_empty(self, client):
        """Test getting vocabulary when database is empty."""
        response = await client.get("/api/vocabulary")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_get_vocabulary_with_data(self, client):
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
        await client.post("/api/vocabulary", json=payload)

        # Get the data
        response = await client.get("/api/vocabulary")

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
        assert vocab["updated"] == vocab["updated_at"]

    async def test_save_vocabulary_item_success(self, client):
        """Test successful saving of a single vocabulary item."""
        payload = {
            "word_phrase": "ett äpple",
            "translation": "an apple",
            "example_phrase": "Jag äter ett äpple varje dag.",
        }

        response = await client.post("/api/vocabulary/item", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["word_phrase"] == "ett äpple"
        assert data["translation"] == "an apple"
        assert data["example_phrase"] == "Jag äter ett äpple varje dag."
        assert data["user_id"] == 1
        assert data["in_learn"] is True
        assert data["priority_learn"] == 9
        assert data["last_learned"] is None
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    async def test_save_vocabulary_item_custom_priority(self, client):
        """Test saving a vocabulary item with explicit numeric priority."""
        payload = {
            "word_phrase": "en stol",
            "translation": "a chair",
            "priority_learn": 2,
        }

        response = await client.post("/api/vocabulary/item", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["priority_learn"] == 2

    async def test_save_vocabulary_item_invalid_priority(self, client):
        """Test vocabulary create validation for out-of-range priority."""
        payload = {
            "word_phrase": "ett bord",
            "translation": "a table",
            "priority_learn": 10,
        }

        response = await client.post("/api/vocabulary/item", json=payload)
        assert response.status_code == 422

    async def test_save_vocabulary_item_boolean_priority_rejected(self, client):
        """Test vocabulary create validation rejects legacy boolean priority payloads."""
        payload = {
            "word_phrase": "en mugg",
            "translation": "a mug",
            "priority_learn": False,
        }

        response = await client.post("/api/vocabulary/item", json=payload)
        assert response.status_code == 422

    async def test_save_vocabulary_item_duplicate(self, client):
        """Test saving a duplicate vocabulary item raises an error."""
        # First save
        payload = {
            "word_phrase": "ett äpple",
            "translation": "an apple",
            "example_phrase": "Jag äter ett äpple varje dag.",
        }
        response1 = await client.post("/api/vocabulary/item", json=payload)
        assert response1.status_code == 200
        data1 = response1.json()
        item_id = data1["id"]

        # Second save with same word_phrase
        payload2 = {
            "word_phrase": "ett äpple",
            "translation": "an apple",
            "example_phrase": "Ett äpple är rött.",
        }
        response2 = await client.post("/api/vocabulary/item", json=payload2)

        assert response2.status_code == 400
        data2 = response2.json()
        assert "already exists" in data2["detail"]

        # Verify no new item was created and existing item remains unchanged
        response3 = await client.get("/api/vocabulary")
        data3 = response3.json()
        assert len(data3) == 1
        existing_item = data3[0]
        assert existing_item["id"] == item_id
        assert existing_item["word_phrase"] == "ett äpple"
        assert existing_item["example_phrase"] == "Jag äter ett äpple varje dag."

    async def test_save_vocabulary_item_without_example(self, client):
        """Test saving a vocabulary item without example phrase."""
        payload = {
            "word_phrase": "en banan",
            "translation": "a banana",
        }

        response = await client.post("/api/vocabulary/item", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["word_phrase"] == "en banan"
        assert data["translation"] == "a banana"
        assert data["example_phrase"] is None

    async def test_get_vocabulary_with_search(self, client):
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
        await client.post("/api/vocabulary", json=payload)

        # Search for "banan" - should find one match
        response = await client.get("/api/vocabulary?search_query=banan")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "en banan"

        # Search for "ett" - should find two matches
        response = await client.get("/api/vocabulary?search_query=ett")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Should be ordered by updated_at descending, with id as a tie-breaker
        assert data[0]["word_phrase"] == "ett päron"  # Most recent
        assert data[1]["word_phrase"] == "ett äpple"

        # Search with wildcard "*" - "*ban*" should match "banan"
        response = await client.get("/api/vocabulary?search_query=*ban*")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "en banan"

        # Search case-insensitive - "BANAN" should match "banan"
        response = await client.get("/api/vocabulary?search_query=BANAN")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "en banan"

        # Search for non-existent term
        response = await client.get("/api/vocabulary?search_query=xyz")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

        # Test with limit
        response = await client.get("/api/vocabulary?search_query=ett&limit=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "ett päron"  # Most recent

        # Test search with offset
        response = await client.get("/api/vocabulary?search_query=ett&limit=1&offset=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "ett äpple"


class TestSettingsDependency:
    """Test cases for dependency injection."""

    @patch("runestone.dependencies.settings")
    async def test_settings_dependency_injection(self, mock_settings, client):
        """Test that settings are properly injected."""
        mock_settings.llm_provider = "test_provider"
        mock_settings.verbose = True

        # This test verifies that the settings dependency injection works
        # by checking that our mock settings are used
        from runestone.dependencies import get_settings

        result = get_settings()
        assert result == mock_settings

    async def test_update_vocabulary_success(self, client):
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
        await client.post("/api/vocabulary", json=payload)

        # Get the item to find its ID
        response = await client.get("/api/vocabulary")
        data = response.json()
        item_id = data[0]["id"]

        # Update the item
        update_payload = {
            "word_phrase": "ett rött äpple",
            "translation": "a red apple",
            "in_learn": False,
        }
        response = await client.put(f"/api/vocabulary/{item_id}", json=update_payload)

        assert response.status_code == 200
        updated_data = response.json()
        assert updated_data["word_phrase"] == "ett rött äpple"
        assert updated_data["translation"] == "a red apple"
        assert updated_data["example_phrase"] == "Jag äter ett äpple varje dag."  # Unchanged
        assert updated_data["in_learn"] is False

    async def test_update_vocabulary_priority_validation(self, client):
        """Test vocabulary update validation for out-of-range priority."""
        payload = {
            "items": [
                {
                    "word_phrase": "ett hus",
                    "translation": "a house",
                }
            ]
        }
        await client.post("/api/vocabulary", json=payload)

        response = await client.get("/api/vocabulary")
        item_id = response.json()[0]["id"]

        update_payload = {"priority_learn": -1}
        response = await client.put(f"/api/vocabulary/{item_id}", json=update_payload)
        assert response.status_code == 422

    async def test_update_vocabulary_priority_boolean_rejected(self, client):
        """Test vocabulary update validation rejects legacy boolean priority payloads."""
        payload = {
            "items": [
                {
                    "word_phrase": "en lampa",
                    "translation": "a lamp",
                }
            ]
        }
        await client.post("/api/vocabulary", json=payload)

        response = await client.get("/api/vocabulary")
        item_id = response.json()[0]["id"]

        update_payload = {"priority_learn": True}
        response = await client.put(f"/api/vocabulary/{item_id}", json=update_payload)
        assert response.status_code == 422

    async def test_update_vocabulary_partial(self, client):
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
        await client.post("/api/vocabulary", json=payload)

        # Get the item to find its ID
        response = await client.get("/api/vocabulary")
        data = response.json()
        item_id = data[0]["id"]

        # Update only one field
        update_payload = {"in_learn": False}
        response = await client.put(f"/api/vocabulary/{item_id}", json=update_payload)

        assert response.status_code == 200
        updated_data = response.json()
        assert updated_data["word_phrase"] == "ett äpple"  # Unchanged
        assert updated_data["translation"] == "an apple"  # Unchanged
        assert updated_data["in_learn"] is False

    async def test_soft_delete_queued_vocabulary_compacts_cursor_and_refills(self, client):
        """Soft deletion preserves recall queue invariants in the endpoint transaction."""
        for word in ("ett äpple", "en banan", "ett päron", "en apelsin"):
            response = await client.post(
                "/api/vocabulary",
                json={"items": [{"word_phrase": word, "translation": word}], "enrich": False},
            )
            assert response.status_code == 200

        vocabulary = list(
            (
                await client.db.execute(
                    select(Vocabulary).where(Vocabulary.user_id == client.user.id).order_by(Vocabulary.id.asc())
                )
            )
            .scalars()
            .all()
        )
        state = RecallUserStateDB(user_id=client.user.id, is_enabled=True, next_word_index=2)
        client.db.add(state)
        await client.db.flush()
        client.db.add_all(
            [
                RecallQueueItemDB(user_id=client.user.id, vocabulary_id=item.id, position=position)
                for position, item in enumerate(vocabulary[:3])
            ]
        )
        await client.db.commit()

        response = await client.put(f"/api/vocabulary/{vocabulary[0].id}", json={"in_learn": False})

        assert response.status_code == 200
        queue_rows = list(
            (
                await client.db.execute(
                    select(RecallQueueItemDB)
                    .where(RecallQueueItemDB.user_id == client.user.id)
                    .order_by(RecallQueueItemDB.position.asc())
                )
            )
            .scalars()
            .all()
        )
        await client.db.refresh(state)
        await client.db.refresh(vocabulary[0])
        assert [(row.vocabulary_id, row.position) for row in queue_rows] == [
            (vocabulary[1].id, 0),
            (vocabulary[2].id, 1),
            (vocabulary[3].id, 2),
        ]
        assert state.next_word_index == 1
        assert vocabulary[0].in_learn is False

    async def test_soft_delete_nonqueued_vocabulary_leaves_queue_unchanged(self, client):
        """A nonqueued deactivation does not trigger unnecessary queue maintenance."""
        for word in ("ett äpple", "en banan", "ett päron"):
            response = await client.post(
                "/api/vocabulary",
                json={"items": [{"word_phrase": word, "translation": word}], "enrich": False},
            )
            assert response.status_code == 200
        vocabulary = list(
            (
                await client.db.execute(
                    select(Vocabulary).where(Vocabulary.user_id == client.user.id).order_by(Vocabulary.id.asc())
                )
            )
            .scalars()
            .all()
        )
        state = RecallUserStateDB(user_id=client.user.id, is_enabled=True, next_word_index=1)
        client.db.add(state)
        await client.db.flush()
        client.db.add_all(
            [
                RecallQueueItemDB(user_id=client.user.id, vocabulary_id=item.id, position=position)
                for position, item in enumerate(vocabulary[:2])
            ]
        )
        await client.db.commit()

        response = await client.put(f"/api/vocabulary/{vocabulary[2].id}", json={"in_learn": False})

        assert response.status_code == 200
        rows = list(
            (
                await client.db.execute(
                    select(RecallQueueItemDB)
                    .where(RecallQueueItemDB.user_id == client.user.id)
                    .order_by(RecallQueueItemDB.position.asc())
                )
            )
            .scalars()
            .all()
        )
        await client.db.refresh(state)
        assert [row.vocabulary_id for row in rows] == [vocabulary[0].id, vocabulary[1].id]
        assert state.next_word_index == 1

    async def test_soft_delete_rolls_back_real_queue_removal_when_update_fails(self, client_with_overrides):
        """A failed vocabulary mutation restores the PostgreSQL-backed queue."""
        vocabulary_service = AsyncMock(spec=VocabularyService)
        vocabulary_service.update_vocabulary_item.side_effect = RuntimeError("update failed")
        async for client, _ in client_with_overrides(vocabulary_service=vocabulary_service):
            item = Vocabulary(user_id=client.user.id, word_phrase="ett ord", translation="a word", in_learn=True)
            client.db.add(item)
            await client.db.flush()
            state = RecallUserStateDB(user_id=client.user.id, is_enabled=True, next_word_index=0)
            client.db.add(state)
            await client.db.flush()
            client.db.add(RecallQueueItemDB(user_id=client.user.id, vocabulary_id=item.id, position=0))
            await client.db.commit()
            vocabulary_id = item.id

            response = await client.put(f"/api/vocabulary/{vocabulary_id}", json={"in_learn": False})

            assert response.status_code == 500
            client.db.expire_all()
            queue_row = await client.db.scalar(
                select(RecallQueueItemDB).where(RecallQueueItemDB.vocabulary_id == vocabulary_id)
            )
            persisted = await client.db.get(Vocabulary, vocabulary_id)
            assert queue_row is not None
            assert persisted.in_learn is True

    async def test_update_vocabulary_rolls_back_when_refill_fails(self):
        """The endpoint rolls back both services when queue refill fails."""
        recall_service = AsyncMock(spec=RecallService)
        recall_service.remove_queue_item.return_value = True
        recall_service.refill_queue.side_effect = RuntimeError("refill failed")
        vocabulary_service = AsyncMock(spec=VocabularyService)
        vocabulary_service.update_vocabulary_item.return_value = Mock()
        db = AsyncMock(spec=AsyncSession)
        user = Mock(id=7)

        with pytest.raises(HTTPException) as exc_info:
            await update_vocabulary(
                11,
                VocabularyUpdate(in_learn=False),
                recall_service,
                vocabulary_service,
                db,
                user,
            )

        assert exc_info.value.status_code == 500
        recall_service.remove_queue_item.assert_awaited_once_with(7, 11)
        vocabulary_service.update_vocabulary_item.assert_awaited_once()
        recall_service.refill_queue.assert_awaited_once_with(7)
        db.rollback.assert_awaited_once_with()
        db.commit.assert_not_awaited()

    async def test_refill_failure_rolls_back_postgresql_vocabulary_update(self, client_with_overrides):
        """A refill error does not publish the preceding PostgreSQL mutation."""
        recall_service = AsyncMock(spec=RecallService)
        recall_service.remove_queue_item.return_value = True
        recall_service.refill_queue.side_effect = RuntimeError("refill failed")
        async for client, _ in client_with_overrides(recall_service=recall_service):
            item = Vocabulary(user_id=client.user.id, word_phrase="ett ord", translation="a word", in_learn=True)
            client.db.add(item)
            await client.db.commit()
            vocabulary_id = item.id
            user_id = client.user.id

            response = await client.put(f"/api/vocabulary/{vocabulary_id}", json={"in_learn": False})

            assert response.status_code == 500
            client.db.expire_all()
            persisted = await client.db.get(Vocabulary, vocabulary_id)
            assert persisted.in_learn is True
            recall_service.refill_queue.assert_awaited_once_with(user_id)

    async def test_duplicate_update_rolls_back_speculative_queue_change(self):
        """A domain conflict rolls back queue maintenance before returning 409."""
        from runestone.core.exceptions import VocabularyItemExists

        recall_service = AsyncMock(spec=RecallService)
        recall_service.remove_queue_item.return_value = True
        vocabulary_service = AsyncMock(spec=VocabularyService)
        vocabulary_service.update_vocabulary_item.side_effect = VocabularyItemExists("duplicate")
        db = AsyncMock(spec=AsyncSession)
        user = Mock(id=7)

        with pytest.raises(HTTPException) as exc_info:
            await update_vocabulary(
                11,
                VocabularyUpdate(word_phrase="duplicate", in_learn=False),
                recall_service,
                vocabulary_service,
                db,
                user,
            )

        assert exc_info.value.status_code == 409
        db.rollback.assert_awaited_once_with()
        db.commit.assert_not_awaited()
        recall_service.refill_queue.assert_not_awaited()

    async def test_ordinary_update_commits_once_without_queue_changes(self):
        """The endpoint owns an ordinary vocabulary update transaction."""
        recall_service = AsyncMock(spec=RecallService)
        vocabulary_service = AsyncMock(spec=VocabularyService)
        updated = Mock()
        vocabulary_service.update_vocabulary_item.return_value = updated
        db = AsyncMock(spec=AsyncSession)
        user = Mock(id=7)
        request = VocabularyUpdate(translation="new translation")

        result = await update_vocabulary(11, request, recall_service, vocabulary_service, db, user)

        assert result is updated
        recall_service.remove_queue_item.assert_not_awaited()
        recall_service.refill_queue.assert_not_awaited()
        vocabulary_service.update_vocabulary_item.assert_awaited_once_with(11, request, 7)
        db.commit.assert_awaited_once_with()
        db.rollback.assert_not_awaited()

    async def test_update_vocabulary_not_found(self, client):
        """Test updating a non-existent vocabulary item."""
        update_payload = {"word_phrase": "new phrase"}
        response = await client.put("/api/vocabulary/999", json=update_payload)

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"]

    async def test_update_vocabulary_invalid_data(self, client):
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
        await client.post("/api/vocabulary", json=payload)

        # Get the item to find its ID
        response = await client.get("/api/vocabulary")
        data = response.json()
        item_id = data[0]["id"]

        # Try to update with invalid data (empty word_phrase)
        update_payload = {"word_phrase": ""}
        response = await client.put(f"/api/vocabulary/{item_id}", json=update_payload)

        # Should still succeed since word_phrase is optional in update
        assert response.status_code == 200

    async def test_delete_vocabulary_success(self, client):
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
        await client.post("/api/vocabulary", json=payload)

        # Get the item to find its ID
        response = await client.get("/api/vocabulary")
        data = response.json()
        item_id = data[0]["id"]

        # Delete the item
        response = await client.delete(f"/api/vocabulary/{item_id}")

        assert response.status_code == 200
        delete_data = response.json()
        assert delete_data["message"] == "Vocabulary item deleted successfully"

        # Verify item is completely removed
        response = await client.get("/api/vocabulary")
        data = response.json()
        assert len(data) == 0

    async def test_delete_vocabulary_not_found(self, client):
        """Test deleting a non-existent vocabulary item."""
        response = await client.delete("/api/vocabulary/999")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"]

    async def test_delete_vocabulary_not_found_rolls_back_queue_removal(self):
        """A failed owned-item delete rolls back speculative queue maintenance."""
        recall_service = AsyncMock(spec=RecallService)
        recall_service.remove_queue_item.return_value = True
        vocabulary_service = AsyncMock(spec=VocabularyService)
        vocabulary_service.hard_delete_item.return_value = False
        db = AsyncMock(spec=AsyncSession)
        user = Mock(id=7)

        with pytest.raises(HTTPException) as exc_info:
            await delete_vocabulary(11, recall_service, vocabulary_service, db, user)

        assert exc_info.value.status_code == 404
        recall_service.remove_queue_item.assert_awaited_once_with(7, 11)
        vocabulary_service.hard_delete_item.assert_awaited_once_with(11, 7)
        recall_service.refill_queue.assert_not_awaited()
        db.rollback.assert_awaited_once_with()
        db.commit.assert_not_awaited()

    async def test_delete_vocabulary_rolls_back_when_queue_refill_fails(self):
        """The endpoint does not publish a deletion if queue restoration fails."""
        recall_service = AsyncMock(spec=RecallService)
        recall_service.remove_queue_item.return_value = True
        recall_service.refill_queue.side_effect = RuntimeError("refill failed")
        vocabulary_service = AsyncMock(spec=VocabularyService)
        vocabulary_service.hard_delete_item.return_value = True
        db = AsyncMock(spec=AsyncSession)
        user = Mock(id=7)

        with pytest.raises(HTTPException) as exc_info:
            await delete_vocabulary(11, recall_service, vocabulary_service, db, user)

        assert exc_info.value.status_code == 500
        recall_service.refill_queue.assert_awaited_once_with(7)
        db.rollback.assert_awaited_once_with()
        db.commit.assert_not_awaited()

    async def test_delete_queued_vocabulary_compacts_queue_and_preserves_cursor(self, client):
        """Hard deletion updates its recall queue atomically through production DI."""
        for word in ("ett äpple", "en banan", "ett päron", "en apelsin"):
            response = await client.post(
                "/api/vocabulary",
                json={"items": [{"word_phrase": word, "translation": word}], "enrich": False},
            )
            assert response.status_code == 200

        vocabulary = list(
            (
                await client.db.execute(
                    select(Vocabulary).where(Vocabulary.user_id == client.user.id).order_by(Vocabulary.id.asc())
                )
            )
            .scalars()
            .all()
        )
        state = RecallUserStateDB(
            user_id=client.user.id,
            telegram_chat_id=123,
            is_enabled=True,
            next_word_index=2,
        )
        client.db.add(state)
        await client.db.flush()
        client.db.add_all(
            [
                RecallQueueItemDB(user_id=client.user.id, vocabulary_id=item.id, position=position)
                for position, item in enumerate(vocabulary[:3])
            ]
        )
        await client.db.commit()

        response = await client.delete(f"/api/vocabulary/{vocabulary[0].id}")

        assert response.status_code == 200
        queue_rows = list(
            (
                await client.db.execute(
                    select(RecallQueueItemDB)
                    .where(RecallQueueItemDB.user_id == client.user.id)
                    .order_by(RecallQueueItemDB.position.asc())
                )
            )
            .scalars()
            .all()
        )
        await client.db.refresh(state)
        assert [(row.vocabulary_id, row.position) for row in queue_rows] == [
            (vocabulary[1].id, 0),
            (vocabulary[2].id, 1),
            (vocabulary[3].id, 2),
        ]
        assert state.next_word_index == 1
        assert await client.db.get(Vocabulary, vocabulary[0].id) is None

    async def test_save_vocabulary_with_enrichment_enabled(self, client_with_mock_vocabulary_service):
        """Test saving vocabulary with enrichment enabled."""
        client, mock_vocabulary_service = client_with_mock_vocabulary_service
        from unittest.mock import AsyncMock

        mock_vocabulary_service.save_vocabulary = AsyncMock(return_value={"message": "Vocabulary saved successfully"})

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

        response = await client.post("/api/vocabulary", json=request_data)

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

    async def test_save_vocabulary_with_enrichment_disabled(self, client_with_mock_vocabulary_service):
        """Test saving vocabulary with enrichment disabled."""
        client, mock_vocabulary_service = client_with_mock_vocabulary_service
        from unittest.mock import AsyncMock

        mock_vocabulary_service.save_vocabulary = AsyncMock(return_value={"message": "Vocabulary saved successfully"})

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

        response = await client.post("/api/vocabulary", json=request_data)

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

    async def test_save_vocabulary_enrichment_default_true(self, client_with_mock_vocabulary_service):
        """Test that enrichment defaults to True when not specified."""
        client, mock_vocabulary_service = client_with_mock_vocabulary_service
        from unittest.mock import AsyncMock

        mock_vocabulary_service.save_vocabulary = AsyncMock(return_value={"message": "Vocabulary saved successfully"})

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

        response = await client.post("/api/vocabulary", json=request_data)

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

    async def test_get_vocabulary_with_precise_search(self, client):
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
        await client.post("/api/vocabulary", json=payload)

        # Test precise=False (default) - should match all containing "apple"
        response = await client.get("/api/vocabulary?search_query=apple&precise=false")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # apple, APPLE, pineapple
        phrases = [item["word_phrase"] for item in data]
        assert "apple" in phrases
        assert "APPLE" in phrases
        assert "pineapple" in phrases
        assert "app" not in phrases  # No partial match

        # Test precise=True - should match only exact case-insensitive
        response = await client.get("/api/vocabulary?search_query=apple&precise=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2  # apple and APPLE
        phrases = [item["word_phrase"] for item in data]
        assert "apple" in phrases
        assert "APPLE" in phrases
        assert "pineapple" not in phrases
        assert "app" not in phrases

        # Test default precise behavior (should be False)
        response = await client.get("/api/vocabulary?search_query=apple")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # Same as precise=false

        # Test precise search for non-existent term
        response = await client.get("/api/vocabulary?search_query=banana&precise=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

        # Test precise search with case sensitivity difference
        response = await client.get("/api/vocabulary?search_query=PINEAPPLE&precise=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "pineapple"

    async def test_get_vocabulary_invalid_limit(self, client):
        """Test get_vocabulary with invalid limit values."""
        # Test limit too high
        response = await client.get("/api/vocabulary?limit=101")
        assert response.status_code == 400
        data = response.json()
        assert "Limit must be between 1 and 100" in data["detail"]

        # Test limit too low
        response = await client.get("/api/vocabulary?limit=0")
        assert response.status_code == 400
        data = response.json()
        assert "Limit must be between 1 and 100" in data["detail"]

        # Test negative limit
        response = await client.get("/api/vocabulary?limit=-1")
        assert response.status_code == 400
        data = response.json()
        assert "Limit must be between 1 and 100" in data["detail"]

    async def test_get_vocabulary_invalid_offset(self, client):
        """Test get_vocabulary with invalid offset values."""
        response = await client.get("/api/vocabulary?offset=-1")
        assert response.status_code == 400
        data = response.json()
        assert "Offset must be non-negative" in data["detail"]

    async def test_get_vocabulary_limit_bounds(self, client):
        """Test get_vocabulary with valid limit bounds."""
        # Save multiple items
        payload = {"items": [{"word_phrase": f"word_{i}", "translation": f"trans_{i}"} for i in range(5)]}
        await client.post("/api/vocabulary", json=payload)

        # Test minimum valid limit
        response = await client.get("/api/vocabulary?limit=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        # Test maximum valid limit
        response = await client.get("/api/vocabulary?limit=100")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5  # All items

        # Test offset pagination
        response = await client.get("/api/vocabulary?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert [item["word_phrase"] for item in data] == ["word_2", "word_1"]

        # Test default limit (should be 100)
        response = await client.get("/api/vocabulary")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
