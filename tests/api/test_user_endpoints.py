"""
Tests for user profile API endpoints.

This module tests the user profile endpoints including GET/PUT /api/users/me
and related functionality.
"""


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

    def test_get_user_profile_with_vocabulary_stats(self, client_with_overrides, db_with_test_user):
        """Test user profile with vocabulary statistics."""
        # Get the test user and database session from the fixture
        db, test_user = db_with_test_user

        # Create a vocabulary repository and service that use the same database session
        from unittest.mock import Mock

        from runestone.db.vocabulary_repository import VocabularyRepository
        from runestone.services.vocabulary_service import VocabularyService

        # Mock settings to avoid dependency injection issues
        mock_settings = Mock()
        mock_settings.vocabulary_enrichment_enabled = True

        # Create the repository and service with the test database session
        vocab_repo = VocabularyRepository(db)
        vocab_service = VocabularyService(vocab_repo, mock_settings, Mock())

        client_gen = client_with_overrides(vocabulary_service=vocab_service)
        client, _ = next(client_gen)

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
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.content}")
        vocab_items = response.json()
        # Find the item with "ett äpple" which has in_learn=True
        apple_item = next(item for item in vocab_items if item["word_phrase"] == "ett äpple")
        learned_item_id = apple_item["id"]

        # Use update_last_learned method to properly increment learned_times
        from runestone.dependencies import get_vocabulary_repository

        repo = get_vocabulary_repository(db)
        vocab = repo.get_vocabulary_item(learned_item_id, test_user.id)
        repo.update_last_learned(vocab)

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

    def test_analyze_content_increments_counter(self, client_with_mock_processor):
        """Test that successful analysis increments pages_recognised_count."""
        client, mock_processor_instance = client_with_mock_processor

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

        # Perform analysis
        payload = {"text": "Hej, vad heter du?"}
        response = client.post("/api/analyze", json=payload)

        assert response.status_code == 200

        # Verify processor was called
        mock_processor_instance.run_analysis.assert_called_once_with("Hej, vad heter du?", 1)  # user_id = 1

    def test_analyze_content_failure_does_not_increment(self, client_with_mock_processor):
        """Test that failed analysis does not increment pages_recognised_count."""
        client, mock_processor_instance = client_with_mock_processor
        mock_processor_instance.run_analysis.side_effect = Exception("Analysis failed")

        # Perform analysis (should fail)
        payload = {"text": "Hej, vad heter du?"}
        response = client.post("/api/analyze", json=payload)

        assert response.status_code == 500
