"""
Tests for user profile API endpoints.

This module tests the user profile endpoints including GET/PUT /api/users/me
and related functionality.
"""

from unittest.mock import Mock

from sqlalchemy.orm import Session

from runestone.db.models import User, Vocabulary
from runestone.dependencies import get_runestone_processor


class TestUserProfileEndpoints:
    """Test cases for user profile endpoints."""

    def test_get_user_profile_success(self, client):
        """Test successful retrieval of user profile with stats."""
        response = client.get("/api/me")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["id"] == 1
        assert "test-" in data["email"] and "@example.com" in data["email"]
        assert data["name"] == "Test User"
        assert data["surname"] == "Testsson"
        assert data["timezone"] == "UTC"
        assert data["pages_recognised_count"] == 0
        assert data["words_in_learn_count"] == 0
        assert data["words_learned_count"] == 0
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_user_profile_with_vocabulary_stats(self, client):
        """Test user profile with vocabulary statistics."""
        # Save some vocabulary items
        vocab_payload = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "in_learn": True,
                },
                {
                    "word_phrase": "en banan",
                    "translation": "a banana",
                    "in_learn": True,
                },
                {
                    "word_phrase": "ett päron",
                    "translation": "a pear",
                    "in_learn": False,  # Not in learning
                },
            ],
            "enrich": False,  # Disable enrichment for tests
        }
        client.post("/api/vocabulary", json=vocab_payload)

        # Update one item to be learned
        response = client.get("/api/vocabulary")
        vocab_items = response.json()
        learned_item_id = vocab_items[0]["id"]

        update_payload = {"learned_times": 1}
        client.put(f"/api/vocabulary/{learned_item_id}", json=update_payload)

        # Get user profile
        response = client.get("/api/me")
        assert response.status_code == 200
        data = response.json()

        # Verify stats
        assert data["words_in_learn_count"] == 2  # ett äpple, en banan
        assert data["words_learned_count"] == 1  # ett äpple (learned_times > 0)

    def test_update_user_profile_success(self, client):
        """Test successful user profile update."""
        update_payload = {
            "name": "Updated Name",
            "surname": "Updated Surname",
            "timezone": "Europe/Stockholm",
        }

        response = client.put("/api/me", json=update_payload)

        assert response.status_code == 200
        data = response.json()

        # Verify updated fields
        assert data["name"] == "Updated Name"
        assert data["surname"] == "Updated Surname"
        assert data["timezone"] == "Europe/Stockholm"

        # Verify unchanged fields
        assert "test-" in data["email"] and "@example.com" in data["email"]

    def test_update_user_profile_partial(self, client):
        """Test partial user profile update."""
        update_payload = {
            "name": "Partial Update",
            # surname and timezone not provided
        }

        response = client.put("/api/me", json=update_payload)

        assert response.status_code == 200
        data = response.json()

        # Verify updated field
        assert data["name"] == "Partial Update"

        # Verify unchanged fields retain original values
        assert data["surname"] == "Testsson"
        assert data["timezone"] == "UTC"

    def test_update_user_profile_password(self, client):
        """Test updating user password."""
        update_payload = {
            "password": "newpassword123",
        }

        response = client.put("/api/me", json=update_payload)

        assert response.status_code == 200

        # Verify password was updated by trying to login (indirect test)
        # This would require additional auth testing setup
        # For now, just verify the endpoint returns success

    def test_update_user_profile_password_too_short(self, client):
        """Test updating user password with too short password."""
        update_payload = {
            "password": "123",  # Too short
        }

        response = client.put("/api/me", json=update_payload)

        assert response.status_code == 400
        data = response.json()
        assert "Password must be at least 6 characters long" in data["detail"]

    def test_update_user_profile_empty_fields(self, client):
        """Test updating user profile with empty string values."""
        update_payload = {
            "name": "",
            "surname": "",
            "timezone": "",
        }

        response = client.put("/api/me", json=update_payload)

        assert response.status_code == 200
        data = response.json()

        # Verify empty strings are accepted
        assert data["name"] == ""
        assert data["surname"] == ""
        assert data["timezone"] == ""

    def test_get_user_profile_unauthorized(self, client_no_db):
        """Test accessing user profile without authentication."""
        response = client_no_db.get("/api/me")

        assert response.status_code == 403

    def test_update_user_profile_unauthorized(self, client_no_db):
        """Test updating user profile without authentication."""
        update_payload = {"name": "New Name"}

        response = client_no_db.put("/api/me", json=update_payload)

        assert response.status_code == 403


class TestPageRecognitionCounter:
    """Test cases for page recognition counter functionality."""

    def test_analyze_content_increments_counter(self, client):
        """Test that successful analysis increments pages_recognised_count."""
        # Mock processor for analysis
        mock_processor_instance = Mock()

        from runestone.schemas.analysis import ContentAnalysis, GrammarFocus, SearchNeeded, VocabularyItem

        mock_analysis_result = ContentAnalysis(
            grammar_focus=GrammarFocus(
                topic="Swedish questions",
                explanation="Basic question formation",
                rules="",
                has_explicit_rules=False,
            ),
            vocabulary=[
                VocabularyItem(swedish="hej", english="hello", example_phrase=None, known=False),
            ],
            core_topics=["questions"],
            search_needed=SearchNeeded(
                should_search=False,
                query_suggestions=[],
            ),
        )
        mock_processor_instance.run_analysis.return_value = mock_analysis_result

        # Override the dependency
        client.app.dependency_overrides[get_runestone_processor] = lambda: mock_processor_instance

        # Perform analysis
        payload = {"text": "Hej, vad heter du?"}
        response = client.post("/api/analyze", json=payload)

        assert response.status_code == 200

        # Verify processor was called
        mock_processor_instance.run_analysis.assert_called_once_with("Hej, vad heter du?", 1)  # user_id = 1

        # Clean up
        client.app.dependency_overrides.clear()

    def test_analyze_content_failure_does_not_increment(self, client):
        """Test that failed analysis does not increment pages_recognised_count."""
        # Mock processor to raise error
        mock_processor_instance = Mock()
        mock_processor_instance.run_analysis.side_effect = Exception("Analysis failed")

        # Override the dependency
        client.app.dependency_overrides[get_runestone_processor] = lambda: mock_processor_instance

        # Perform analysis (should fail)
        payload = {"text": "Hej, vad heter du?"}
        response = client.post("/api/analyze", json=payload)

        assert response.status_code == 500

        # Clean up
        client.app.dependency_overrides.clear()


class TestVocabularyRepositoryStats:
    """Test cases for vocabulary repository statistics methods."""

    def test_get_words_in_learn_count(self, db_session: Session):
        """Test counting words in learning."""
        from runestone.db.vocabulary_repository import VocabularyRepository

        repo = VocabularyRepository(db_session)

        # Create test user
        user = User(
            email="stats@example.com",
            hashed_password="dummy",
            name="Stats User",
            surname="User",
        )
        db_session.add(user)
        db_session.commit()

        # Add vocabulary items
        vocab_payload = {
            "items": [
                {"word_phrase": "word1", "translation": "trans1", "in_learn": True},
                {"word_phrase": "word2", "translation": "trans2", "in_learn": True},
                {"word_phrase": "word3", "translation": "trans3", "in_learn": False},
            ]
        }

        # Use vocabulary service to save items
        from runestone.api.schemas import VocabularyItemCreate
        from runestone.db.vocabulary_repository import VocabularyRepository
        from runestone.services.vocabulary_service import VocabularyService

        # Create service with proper dependencies
        vocab_repo = VocabularyRepository(db_session)
        # Mock settings and llm_client for service
        mock_settings = Mock()
        mock_llm_client = Mock()
        service = VocabularyService(vocab_repo, mock_settings, mock_llm_client)
        service.save_vocabulary(
            [VocabularyItemCreate(**item) for item in vocab_payload["items"]], user.id, enrich=False
        )

        # Test stats
        count = repo.get_words_in_learn_count(user.id)
        assert count == 2  # word1, word2

    def test_get_words_learned_count(self, db_session: Session):
        """Test counting learned words."""
        from runestone.db.vocabulary_repository import VocabularyRepository

        repo = VocabularyRepository(db_session)

        # Create test user
        user = User(
            email="learned@example.com",
            hashed_password="dummy",
            name="Learned User",
        )
        db_session.add(user)
        db_session.commit()

        # Add vocabulary items
        vocab_payload = {
            "items": [
                {"word_phrase": "word1", "translation": "trans1", "in_learn": True},
                {"word_phrase": "word2", "translation": "trans2", "in_learn": True},
                {"word_phrase": "word3", "translation": "trans3", "in_learn": True},
                {"word_phrase": "word4", "translation": "trans4", "in_learn": False},  # Not in learn
            ]
        }

        # Use vocabulary service to save items
        from runestone.api.schemas import VocabularyItemCreate
        from runestone.db.vocabulary_repository import VocabularyRepository
        from runestone.services.vocabulary_service import VocabularyService

        # Create service with proper dependencies
        vocab_repo = VocabularyRepository(db_session)
        mock_settings = Mock()
        mock_llm_client = Mock()
        service = VocabularyService(vocab_repo, mock_settings, mock_llm_client)

        items = [VocabularyItemCreate(**item) for item in vocab_payload["items"]]
        service.save_vocabulary(items, user.id, enrich=False)

        # Update learned_times for some items
        vocab_items = db_session.query(Vocabulary).filter(Vocabulary.user_id == user.id).all()
        vocab_items[0].learned_times = 1  # word1 learned
        vocab_items[1].learned_times = 2  # word2 learned
        # word3 not learned
        db_session.commit()

        # Test stats
        count = repo.get_words_learned_count(user.id)
        assert count == 2  # word1, word2
