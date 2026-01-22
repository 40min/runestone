"""
Tests for user database repository functionality.

This module contains tests for the user repository.
"""

import pytest

from runestone.core.exceptions import UserNotFoundError
from runestone.db.models import User
from runestone.db.user_repository import UserRepository


class TestUserRepository:
    """Test cases for UserRepository."""

    @pytest.fixture
    def repo(self, db_session):
        """Create a UserRepository instance."""
        return UserRepository(db_session)

    def test_update_user_memory_success(self, repo, db_session):
        """Test successful update of user memory field."""
        # Create a test user
        user = User(
            email="memory-test@example.com",
            hashed_password="dummy",
            name="Memory Test User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Update memory field
        test_data = {"name": "Anna", "goal": "B2"}
        repo.update_user_memory(user.id, "personal_info", test_data)

        # Verify the update
        updated_user = db_session.query(User).filter(User.id == user.id).first()
        assert updated_user.personal_info == '{"name": "Anna", "goal": "B2"}'

    def test_update_user_memory_multiple_fields(self, repo, db_session):
        """Test updating multiple memory fields."""
        # Create a test user
        user = User(
            email="memory-multi@example.com",
            hashed_password="dummy",
            name="Memory Multi User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Update multiple fields
        repo.update_user_memory(user.id, "personal_info", {"name": "Test"})
        repo.update_user_memory(user.id, "areas_to_improve", {"grammar": "subjunctive"})
        repo.update_user_memory(user.id, "knowledge_strengths", {"vocabulary": "strong"})

        # Verify all updates
        updated_user = db_session.query(User).filter(User.id == user.id).first()
        assert updated_user.personal_info == '{"name": "Test"}'
        assert updated_user.areas_to_improve == '{"grammar": "subjunctive"}'
        assert updated_user.knowledge_strengths == '{"vocabulary": "strong"}'

    def test_update_user_memory_with_none_data(self, repo, db_session):
        """Test updating memory field with None data clears the field."""
        # Create a test user with existing data
        user = User(
            email="memory-none@example.com",
            hashed_password="dummy",
            name="Memory None User",
            personal_info='{"name": "Old"}',
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Update with None data (should clear)
        repo.update_user_memory(user.id, "personal_info", None)

        # Verify field is cleared
        updated_user = db_session.query(User).filter(User.id == user.id).first()
        assert updated_user.personal_info is None

    def test_update_user_memory_empty_data(self, repo, db_session):
        """Test updating memory field with empty dict clears the field."""
        # Create a test user with existing data
        user = User(
            email="memory-empty@example.com",
            hashed_password="dummy",
            name="Memory Empty User",
            personal_info='{"name": "Old"}',
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Update with empty dict (should clear)
        repo.update_user_memory(user.id, "personal_info", {})

        # Verify field is cleared
        updated_user = db_session.query(User).filter(User.id == user.id).first()
        assert updated_user.personal_info is None

    def test_update_user_memory_user_not_found(self, repo):
        """Test updating memory for non-existent user raises error."""
        with pytest.raises(UserNotFoundError, match="User with id 999 not found"):
            repo.update_user_memory(999, "personal_info", {"test": "data"})

    def test_update_user_memory_invalid_field(self, repo, db_session):
        """Test updating with invalid field name raises ValueError."""
        # Create a test user
        user = User(
            email="memory-invalid@example.com",
            hashed_password="dummy",
            name="Memory Invalid User",
        )
        db_session.add(user)
        db_session.commit()

        with pytest.raises(ValueError, match="Invalid memory field: 'invalid_field'"):
            repo.update_user_memory(user.id, "invalid_field", {"test": "data"})
