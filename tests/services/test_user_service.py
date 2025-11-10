"""
Tests for user service.

This module contains unit tests for the UserService class.
"""


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
        try:
            user_service.update_user_profile(user, update_data)
            assert False, "Expected ValueError was not raised"
        except ValueError as e:
            assert "Email address is already registered by another user" in str(e)

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
        try:
            user_service.update_user_profile(user, update_data)
            assert False, "Expected ValueError was not raised"
        except ValueError as e:
            assert "Email address is already registered by another user" in str(e)

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
