"""
User repository for database operations.

This module contains repository classes that encapsulate database
logic for user entities.
"""

from typing import Optional

from sqlalchemy.orm import Session

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
