"""
User repository for database operations.

This module contains repository classes that encapsulate database
logic for user entities.
"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from ..core.constants import MEMORY_FIELDS
from ..core.exceptions import UserNotFoundError
from ..db.models import User


class UserRepository:
    """Repository for user-related database operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.db.query(User).filter(User.email == email).first()

    def create(self, user: User) -> User:
        """Create a new user."""
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user: User) -> User:
        """Update an existing user."""
        self.db.commit()
        self.db.refresh(user)
        return user

    def increment_pages_recognised_count(self, user_id: int) -> None:
        """Increment the pages recognised count for a user by ID."""
        user = self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id {user_id} not found")

        user.pages_recognised_count += 1
        self.db.commit()

    def _validate_memory_field(self, field: str) -> None:
        """
        Validate that a memory field name is valid.

        Args:
            field: Field name to validate

        Raises:
            ValueError: If field name is invalid
        """
        if field not in MEMORY_FIELDS:
            raise ValueError(f"Invalid memory field: '{field}'. Must be one of {MEMORY_FIELDS}")

    def _get_user_or_raise(self, user_id: int) -> User:
        """
        Get user by ID or raise exception if not found.

        Args:
            user_id: ID of the user

        Returns:
            User object

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id {user_id} not found")
        return user

    def update_user_memory(self, user_id: int, field: str, data: dict) -> None:
        """
        Update a specific memory field with new data.

        Args:
            user_id: ID of the user
            field: Memory field name ('personal_info', 'areas_to_improve', 'knowledge_strengths')
            data: Dictionary to store as JSON

        Raises:
            UserNotFoundError: If user not found
            ValueError: If field name is invalid
        """
        self._validate_memory_field(field)
        json_data = json.dumps(data) if data else None

        result = self.db.query(User).filter(User.id == user_id).update({field: json_data})
        if result == 0:
            raise UserNotFoundError(f"User with id {user_id} not found")

        self.db.commit()

    def clear_user_memory(self, user_id: int, field: Optional[str] = None) -> User:
        """
        Clear one or all memory fields for a user.

        Args:
            user_id: ID of the user
            field: Specific field to clear, or None to clear all memory fields

        Returns:
            Updated user object

        Raises:
            UserNotFoundError: If user not found
            ValueError: If field name is invalid
        """
        if field:
            self._validate_memory_field(field)

        user = self._get_user_or_raise(user_id)

        if field:
            # Clear specific field - setattr is safe here due to validation
            setattr(user, field, None)
        else:
            # Clear all memory fields explicitly
            # This is more explicit and type-safe than using setattr in a loop
            user.personal_info = None
            user.areas_to_improve = None
            user.knowledge_strengths = None

        self.db.commit()
        self.db.refresh(user)
        return user
