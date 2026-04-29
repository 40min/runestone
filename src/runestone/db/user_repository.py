from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import UserNotFoundError
from ..db.models import User


class UserRepository:
    """Repository for user-related database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session."""
        self.db = db

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        stmt = select(User).filter(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        stmt = select(User).filter(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def find_by_telegram_username(self, username: str | None) -> list[User]:
        """Find users linked to a canonical Telegram username."""
        if username is None:
            return []

        stmt = select(User).filter(User.telegram_username == username)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, user: User) -> User:
        """Create a new user."""
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user: User) -> User:
        """Update an existing user."""
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def increment_pages_recognised_count(self, user_id: int) -> None:
        """Increment the pages recognised count for a user by ID."""
        stmt = update(User).where(User.id == user_id).values(pages_recognised_count=User.pages_recognised_count + 1)
        result = await self.db.execute(stmt)
        if result.rowcount == 0:
            raise UserNotFoundError(f"User with id {user_id} not found")
        await self.db.commit()
