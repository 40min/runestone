"""
Service layer for user operations.

This module contains service classes that handle business logic
for user-related operations.
"""

from sqlalchemy.exc import IntegrityError

from ..api.schemas import UserProfileResponse, UserProfileUpdate
from ..auth.security import hash_password
from ..core.exceptions import UserNotFoundError
from ..core.logging_config import get_logger
from ..db.models import User
from ..db.user_repository import UserRepository
from ..db.vocabulary_repository import VocabularyRepository


class UserService:
    """Service for user-related business logic."""

    def __init__(self, user_repository: UserRepository, vocabulary_repository: VocabularyRepository):
        """Initialize service with user and vocabulary repositories."""
        self.user_repo = user_repository
        self.vocab_repo = vocabulary_repository
        self.logger = get_logger(__name__)

    def get_user_profile(self, user: User) -> UserProfileResponse:
        """Get user profile with stats."""
        # Get vocabulary stats
        words_in_learn_count = self.vocab_repo.get_words_in_learn_count(user.id)
        words_learned_count = self.vocab_repo.get_words_learned_count(user.id)

        return UserProfileResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            surname=user.surname,
            timezone=user.timezone,
            pages_recognised_count=user.pages_recognised_count,
            words_in_learn_count=words_in_learn_count,
            words_learned_count=words_learned_count,
            created_at=user.created_at.isoformat() if user.created_at else None,
            updated_at=user.updated_at.isoformat() if user.updated_at else None,
        )

    def update_user_profile(self, user: User, update_data: UserProfileUpdate) -> UserProfileResponse:
        """Update user profile."""
        # Validate password if provided
        if update_data.password is not None:
            if len(update_data.password) < 6:
                raise ValueError("Password must be at least 6 characters long")

        # Check if email is being updated and validate uniqueness
        if update_data.email is not None and update_data.email != user.email:
            # Check if the new email is already registered by another user
            existing_user = self.user_repo.get_by_email(update_data.email)
            if existing_user is not None and existing_user.id != user.id:
                raise ValueError("Email address is already registered by another user")

        # Update user fields
        update_dict = update_data.model_dump(exclude_unset=True)

        # Hash password if provided
        if "password" in update_dict:
            update_dict["hashed_password"] = hash_password(update_dict.pop("password"))

        # Update user attributes
        for key, value in update_dict.items():
            if hasattr(user, key):
                setattr(user, key, value)

        # Save changes using user repository
        try:
            updated_user = self.user_repo.update(user)
        except IntegrityError as e:
            # Handle race condition TOCTOU: another user may have taken this email
            # Check for unique constraint violation on email column
            error_str = str(e)
            if "users_email_key" in error_str or "UNIQUE constraint failed: users.email" in error_str:
                raise ValueError("Email address is already registered by another user") from e
            raise  # Re-raise other integrity errors

        # Return updated profile
        return self.get_user_profile(updated_user)

    def increment_pages_recognised_count(self, user: User) -> None:
        """Increment the pages recognised count for a user."""
        self.user_repo.increment_pages_recognised_count(user.id)

    def reset_user_password(self, email: str, new_password: str = "test123test") -> User:
        """Reset user password by email."""
        # Find user by email
        user = self.user_repo.get_by_email(email)
        if not user:
            raise UserNotFoundError(f"User with email '{email}' not found")

        # Hash and set new password
        user.hashed_password = hash_password(new_password)
        self.user_repo.update(user)

        return user
