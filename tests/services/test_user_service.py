"""
Tests for user service.

This module contains unit tests for the UserService class.
"""

import pytest


class TestUserService:
    """Test cases for UserService."""

    def test_update_user_profile_email_validation_duplicate(self, user_service, mock_user_repo, mock_vocab_repo, user):
        """Test email update validation fails when email is already taken."""
        # Mock get_by_email to return another user
        from datetime import datetime

        from runestone.db.models import User

        existing_user = User(
            id=2,
            email="existing@example.com",
            hashed_password="hash",
            name="Existing User",
            surname="Test",
            timezone="UTC",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_user_repo.get_by_email.return_value = existing_user

        from runestone.api.schemas import UserProfileUpdate

        # Try to update to existing email
        update_data = UserProfileUpdate(email="existing@example.com")

        # Should raise ValueError
        with pytest.raises(ValueError, match="Email address is already registered by another user"):
            user_service.update_user_profile(user, update_data)

        # Verify get_by_email was called
        mock_user_repo.get_by_email.assert_called_once_with("existing@example.com")

    def test_update_user_profile_email_validation_success(self, user_service, mock_user_repo, mock_vocab_repo, user):
        """Test successful email update when email is available."""
        # Mock get_by_email to return None (email available)
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.update.return_value = user

        from runestone.api.schemas import UserProfileUpdate

        # Update to new email
        update_data = UserProfileUpdate(email="newemail@example.com")
        result = user_service.update_user_profile(user, update_data)

        # Should succeed
        assert result is not None

        # Verify get_by_email was called
        mock_user_repo.get_by_email.assert_called_once_with("newemail@example.com")

    def test_update_user_profile_email_no_change(self, user_service, mock_user_repo, mock_vocab_repo, user):
        """Test email update when email is the same (no change)."""
        # Set user email
        user.email = "current@example.com"

        # Mock get_by_email - not called since email hasn't changed
        mock_user_repo.update.return_value = user

        from runestone.api.schemas import UserProfileUpdate

        # Update with same email
        update_data = UserProfileUpdate(email="current@example.com")
        result = user_service.update_user_profile(user, update_data)

        # Should succeed without calling get_by_email
        assert result is not None
        mock_user_repo.get_by_email.assert_not_called()

    def test_update_user_profile_email_other_user_owns_it(self, user_service, mock_user_repo, mock_vocab_repo, user):
        """Test email update validation fails when another user owns the email."""
        # Mock get_by_email to return a different user
        from datetime import datetime

        from runestone.db.models import User

        existing_user = User(
            id=999,  # Different user ID
            email="taken@example.com",
            hashed_password="hash",
            name="Other User",
            surname="Test",
            timezone="UTC",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_user_repo.get_by_email.return_value = existing_user

        from runestone.api.schemas import UserProfileUpdate

        # Try to update to taken email
        update_data = UserProfileUpdate(email="taken@example.com")

        # Should raise ValueError
        with pytest.raises(ValueError, match="Email address is already registered by another user"):
            user_service.update_user_profile(user, update_data)

    def test_update_user_profile_email_same_user_allowed(self, user_service, mock_user_repo, mock_vocab_repo, user):
        """Test that updating to own email (from different case) is allowed."""
        # Set user email
        user.email = "Current@Example.com"

        # Mock get_by_email to return the same user (case-insensitive match)
        mock_user_repo.get_by_email.return_value = user
        mock_user_repo.update.return_value = user

        from runestone.api.schemas import UserProfileUpdate

        # Update with different case of same email
        update_data = UserProfileUpdate(email="current@example.com")
        result = user_service.update_user_profile(user, update_data)

        # Should succeed (get_by_email was called but returned same user)
        assert result is not None
        mock_user_repo.get_by_email.assert_called_once_with("current@example.com")

    def test_update_user_profile_email_toctou_race_condition(self, user_service, mock_user_repo, mock_vocab_repo, user):
        """Test TOCTOU race condition: IntegrityError is caught and converted to ValueError."""
        from sqlalchemy.exc import IntegrityError

        from runestone.api.schemas import UserProfileUpdate

        # Set user email to a new one and mock get_by_email to return None
        # (simulating the case where email is available at check time)
        user.email = "old@example.com"
        mock_user_repo.get_by_email.return_value = None

        # Mock update to raise IntegrityError (simulating race condition)
        # where another user took the email between check and update
        integrity_error = IntegrityError(
            'Duplicate key value violates unique constraint "users_email_key"',
            'Duplicate key value violates unique constraint "users_email_key"',
            "ORIGINAL ERROR: psycopg2.errors.UniqueViolation: "
            'duplicate key value violates unique constraint "users_email_key"',
        )
        mock_user_repo.update.side_effect = integrity_error

        # Try to update email
        update_data = UserProfileUpdate(email="newemail@example.com")

        # Should raise ValueError with user-friendly message
        with pytest.raises(ValueError, match="Email address is already registered by another user"):
            user_service.update_user_profile(user, update_data)

        # Verify update was called
        mock_user_repo.update.assert_called_once()

    def test_update_user_profile_email_toctou_sqlite_constraint(
        self, user_service, mock_user_repo, mock_vocab_repo, user
    ):
        """Test TOCTOU race condition with SQLite-style UNIQUE constraint failed message."""
        from sqlalchemy.exc import IntegrityError

        from runestone.api.schemas import UserProfileUpdate

        # Set user email
        user.email = "old@example.com"
        mock_user_repo.get_by_email.return_value = None

        # Mock update to raise IntegrityError with SQLite-style message
        integrity_error = IntegrityError(
            "(sqlite3.IntegrityError) UNIQUE constraint failed: users.email",
            "(sqlite3.IntegrityError) UNIQUE constraint failed: users.email",
            "UNIQUE constraint failed: users.email",
        )
        mock_user_repo.update.side_effect = integrity_error

        # Try to update email
        update_data = UserProfileUpdate(email="newemail@example.com")

        # Should raise ValueError with user-friendly message
        with pytest.raises(ValueError, match="Email address is already registered by another user"):
            user_service.update_user_profile(user, update_data)

    def test_update_user_profile_other_integrity_error_raised(
        self, user_service, mock_user_repo, mock_vocab_repo, user
    ):
        """Test that non-email IntegrityError is re-raised."""
        from sqlalchemy.exc import IntegrityError

        from runestone.api.schemas import UserProfileUpdate

        # Set user email
        user.email = "old@example.com"
        mock_user_repo.get_by_email.return_value = None

        # Mock update to raise IntegrityError with a different constraint
        integrity_error = IntegrityError(
            "Foreign key violation", "Foreign key violation", "FOREIGN KEY constraint failed"
        )
        mock_user_repo.update.side_effect = integrity_error

        # Try to update
        update_data = UserProfileUpdate(email="newemail@example.com")

        # Should re-raise the IntegrityError
        with pytest.raises(IntegrityError):
            user_service.update_user_profile(user, update_data)

    def test_update_user_profile_memory_fields(self, user_service, mock_user_repo, mock_vocab_repo, user):
        """Test updating memory fields with Pydantic validation."""
        import json

        from runestone.api.schemas import UserProfileUpdate

        # Mock update to return updated user
        mock_user_repo.update.return_value = user

        # Test updating memory fields with dict
        memory_data = {"key": "value"}
        update_data = UserProfileUpdate(personal_info=memory_data)

        # Verify that the model contains a string if passed a dict (due to validator)
        assert isinstance(update_data.personal_info, str)
        assert json.loads(update_data.personal_info) == memory_data

        user_service.update_user_profile(user, update_data)

        # Verify user attribute was updated with JSON string
        assert user.personal_info == json.dumps(memory_data)
        mock_user_repo.update.assert_called()

    def test_update_user_profile_memory_invalid_json_input(self):
        """Test that invalid memory field raises validation error in Pydantic."""
        from pydantic import ValidationError

        from runestone.api.schemas import UserProfileUpdate

        # Should raise validation error (not dict)
        with pytest.raises(ValidationError):
            UserProfileUpdate(personal_info=["list"])

    def test_clear_user_memory(self, user_service, mock_user_repo, user):
        """Test clearing user memory."""
        # Mock clear_user_memory repo method
        mock_user_repo.clear_user_memory.return_value = user

        user_service.clear_user_memory(user, "personal_info")

        mock_user_repo.clear_user_memory.assert_called_once_with(user.id, "personal_info")

    def test_update_user_profile_mother_tongue(self, user_service, mock_user_repo, mock_vocab_repo, user):
        """Test updating mother tongue."""
        from runestone.api.schemas import UserProfileUpdate

        # Mock update to return updated user
        mock_user_repo.update.return_value = user

        # Test updating mother tongue
        update_data = UserProfileUpdate(mother_tongue="Spanish")
        user_service.update_user_profile(user, update_data)

        # Verify user attribute was updated
        assert user.mother_tongue == "Spanish"
        mock_user_repo.update.assert_called()
