"""
Service layer for user operations.

This module contains service classes that handle business logic
for user-related operations.
"""

from typing import Optional
from uuid import uuid4

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

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Get a user by their ID.

        Args:
            user_id: The user's ID

        Returns:
            User model or None if not found
        """
        return await self.user_repo.get_by_id(user_id)

    async def get_user_profile(self, user: User) -> UserProfileResponse:
        """Get user profile."""
        return UserProfileResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            surname=user.surname,
            telegram_username=user.telegram_username,
            mother_tongue=user.mother_tongue,
            timezone=user.timezone,
            pages_recognised_count=user.pages_recognised_count,
            created_at=user.created_at.isoformat() if user.created_at else None,
            updated_at=user.updated_at.isoformat() if user.updated_at else None,
        )

    async def update_user_profile(self, user: User, update_data: UserProfileUpdate) -> UserProfileResponse:
        """Update user profile."""
        # Validate password if provided
        if update_data.password is not None:
            if len(update_data.password) < 6:
                raise ValueError("Password must be at least 6 characters long")

        # Check if email is being updated and validate uniqueness
        if update_data.email is not None and update_data.email != user.email:
            existing_user = await self.user_repo.get_by_email(update_data.email)
            if existing_user is not None and existing_user.id != user.id:
                raise ValueError("Email address is already registered by another user")

        if update_data.telegram_username is not None and update_data.telegram_username != user.telegram_username:
            existing_users = await self.user_repo.find_by_telegram_username(update_data.telegram_username)
            if any(existing_user.id != user.id for existing_user in existing_users):
                raise ValueError("Telegram username is already linked to another account")

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
            updated_user = await self.user_repo.update(user)
        except IntegrityError as e:
            error_str = str(e)
            if "users_email_key" in error_str or "UNIQUE constraint failed: users.email" in error_str:
                raise ValueError("Email address is already registered by another user") from e
            if (
                "users_telegram_username_key" in error_str
                or "ix_users_telegram_username" in error_str
                or "UNIQUE constraint failed: users.telegram_username" in error_str
            ):
                raise ValueError("Telegram username is already linked to another account") from e
            raise

        return await self.get_user_profile(updated_user)

    async def increment_pages_recognised_count(self, user: User) -> None:
        """Increment the pages recognised count for a user."""
        await self.user_repo.increment_pages_recognised_count(user.id)

    async def reset_user_password(self, email: str, new_password: str = "test123test") -> User:
        """Reset user password by email."""
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise UserNotFoundError(f"User with email '{email}' not found")

        user.hashed_password = hash_password(new_password)
        await self.user_repo.update(user)

        return user

    async def get_or_create_current_chat_id(self, user_id: int) -> str:
        """
        Get the current chat id for user, creating one if missing.

        Args:
            user_id: User ID

        Returns:
            Current chat ID
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id {user_id} not found")

        if user.current_chat_id:
            return user.current_chat_id

        user.current_chat_id = str(uuid4())
        await self.user_repo.update(user)
        return user.current_chat_id

    async def rotate_current_chat_id(self, user_id: int) -> str:
        """
        Generate and persist a new current chat id for the user.

        Args:
            user_id: User ID

        Returns:
            Newly generated chat ID
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id {user_id} not found")

        user.current_chat_id = str(uuid4())
        await self.user_repo.update(user)
        return user.current_chat_id
