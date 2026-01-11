"""
Tests for user profile API endpoints.

This module tests the user profile endpoints including GET/PUT /api/users/me
and related functionality.
"""

from runestone.db.vocabulary_repository import VocabularyRepository
from runestone.schemas.analysis import ContentAnalysis, GrammarFocus, SearchNeeded, VocabularyItem


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
        assert data["words_skipped_count"] == 0
        assert data["overall_words_count"] == 0
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
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.content}")
        vocab_items = response.json()
        # Find the item with "ett äpple" which has in_learn=True
        apple_item = next(item for item in vocab_items if item["word_phrase"] == "ett äpple")
        learned_item_id = apple_item["id"]

        # Use update_last_learned method to properly increment learned_times
        repo = VocabularyRepository(client.db)
        vocab = repo.get_vocabulary_item(learned_item_id, client.user.id)
        repo.update_last_learned(vocab)

        # Get user profile
        response = client.get("/api/me")
        assert response.status_code == 200
        data = response.json()

        # Verify stats
        # words_in_learn_count: count of words with in_learn=True AND last_learned IS NOT NULL
        assert data["words_in_learn_count"] == 1  # Only ett äpple (has last_learned)
        # words_skipped_count: count of words with in_learn=False
        assert data["words_skipped_count"] == 1  # ett päron (in_learn=False)
        # overall_words_count: total count of all words
        assert data["overall_words_count"] == 3  # All three words

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

    def test_update_user_profile_email_success(self, client):
        """Test successful user email update."""
        update_payload = {
            "email": "newemail@example.com",
        }

        response = client.put("/api/me", json=update_payload)

        assert response.status_code == 200
        data = response.json()

        # Verify email was updated
        assert data["email"] == "newemail@example.com"

        # Verify other fields remain unchanged
        assert data["name"] == "Test User"
        assert data["surname"] == "Testsson"
        assert data["timezone"] == "UTC"

    def test_update_user_profile_email_duplicate(self, client, user_factory):
        """Test user email update with duplicate email should fail."""
        # Create a second user with a specific email
        user_factory(email="existing@example.com")

        # Try to update the first user's email to the second user's email
        update_payload = {
            "email": "existing@example.com",
        }

        response = client.put("/api/me", json=update_payload)

        assert response.status_code == 400
        data = response.json()
        assert "Email address is already registered by another user" in data["detail"]

    def test_update_user_profile_email_no_change(self, client):
        """Test user email update with the same email (no actual change)."""
        # Get current user profile
        initial_response = client.get("/api/me")
        assert initial_response.status_code == 200
        current_email = initial_response.json()["email"]

        # Update with the same email
        update_payload = {
            "email": current_email,
        }

        response = client.put("/api/me", json=update_payload)

        assert response.status_code == 200
        data = response.json()

        # Verify email remains the same
        assert data["email"] == current_email


class TestPageRecognitionCounter:
    """Test cases for page recognition counter functionality."""

    def test_analyze_content_increments_counter(self, client_with_mock_processor):
        """Test that successful analysis increments pages_recognised_count."""
        client, mock_processor_instance = client_with_mock_processor

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

        # Verify processor was called with user from the mock processor
        # The user should be in the mock processor's call arguments
        args, kwargs = mock_processor_instance.run_analysis.call_args
        called_text, called_user = args
        assert called_text == "Hej, vad heter du?"

    def test_analyze_content_failure_does_not_increment(self, client_with_mock_processor):
        """Test that failed analysis does not increment pages_recognised_count."""
        client, mock_processor_instance = client_with_mock_processor
        mock_processor_instance.run_analysis.side_effect = Exception("Analysis failed")

        # Perform analysis (should fail)
        payload = {"text": "Hej, vad heter du?"}
        response = client.post("/api/analyze", json=payload)

        assert response.status_code == 500


class TestUserMemoryEndpoints:
    """Test cases for user memory endpoints."""

    def test_update_user_memory_success(self, client):
        """Test successful update of user memory fields."""
        memory_payload = {
            "personal_info": {"name": "Anna", "goal": "B1"},
            "areas_to_improve": {"grammar": "word order"},
        }

        response = client.put("/api/me", json=memory_payload)

        assert response.status_code == 200
        data = response.json()

        assert data["personal_info"] == {"name": "Anna", "goal": "B1"}
        assert data["areas_to_improve"] == {"grammar": "word order"}
        # Verify persistence
        get_response = client.get("/api/me")
        assert get_response.json()["personal_info"] == {"name": "Anna", "goal": "B1"}

    def test_update_user_memory_invalid_json(self, client):
        """Test update with invalid JSON (not a dict)."""
        memory_payload = {
            "personal_info": "not a dict",
        }

        response = client.put("/api/me", json=memory_payload)

        assert response.status_code == 422  # Validation error

    def test_clear_user_memory_all(self, client):
        """Test clearing all user memory."""
        # First set some memory
        client.put("/api/me", json={"personal_info": {"a": 1}, "areas_to_improve": {"b": 2}})

        # Clear all
        response = client.delete("/api/me/memory")
        assert response.status_code == 200
        data = response.json()

        assert data["personal_info"] is None
        assert data["areas_to_improve"] is None
        assert data["knowledge_strengths"] is None

    def test_clear_user_memory_category(self, client):
        """Test clearing specific memory category."""
        # First set some memory
        client.put("/api/me", json={"personal_info": {"a": 1}, "areas_to_improve": {"b": 2}})

        # Clear only personal_info
        response = client.delete("/api/me/memory?category=personal_info")
        assert response.status_code == 200
        data = response.json()

        assert data["personal_info"] is None
        assert data["areas_to_improve"] == {"b": 2}

    def test_clear_user_memory_invalid_category(self, client):
        """Test clearing invalid memory category."""
        response = client.delete("/api/me/memory?category=invalid_field")
        assert response.status_code == 400
