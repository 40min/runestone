from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import UserEmailAlreadyExistsError, UserNotFoundError
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

    async def is_active(self, user_id: int) -> bool:
        """Read current activation directly without using an identity-mapped entity."""
        stmt = select(User.active).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is True

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

    async def add_user(self, user: User) -> User:
        """Add and flush a user without deciding the outer transaction."""
        self.db.add(user)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            if self._is_user_email_unique_violation(exc):
                raise UserEmailAlreadyExistsError("Email already registered") from exc
            raise
        return user

    @staticmethod
    def _is_user_email_unique_violation(exc: IntegrityError) -> bool:
        """Identify only the supported database constraints for unique user email."""
        supported_constraints = {"users_email_key", "ix_users_email"}
        pending = [exc.orig]
        seen: set[int] = set()
        has_unique_violation_state = False
        constraint_names: set[str] = set()

        while pending:
            current = pending.pop()
            if current is None or id(current) in seen:
                continue
            seen.add(id(current))

            if str(current) == "UNIQUE constraint failed: users.email":
                return True

            sqlstate = getattr(current, "sqlstate", None) or getattr(current, "pgcode", None)
            has_unique_violation_state = has_unique_violation_state or sqlstate == "23505"

            constraint_name = getattr(current, "constraint_name", None)
            diagnostic = getattr(current, "diag", None)
            if diagnostic is not None:
                constraint_name = constraint_name or getattr(diagnostic, "constraint_name", None)
            if constraint_name:
                constraint_names.add(constraint_name)

            pending.extend((getattr(current, "__cause__", None), getattr(current, "__context__", None)))

        return has_unique_violation_state and bool(constraint_names & supported_constraints)

    async def commit(self) -> None:
        """Commit the current user use-case transaction."""
        await self.db.commit()

    async def rollback(self) -> None:
        """Roll back the current user use-case transaction."""
        await self.db.rollback()

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

    async def set_personal_info_summary(self, user_id: int, summary: str | None) -> None:
        """Persist the derived personal-info summary for one user."""
        stmt = update(User).where(User.id == user_id).values(personal_info_summary=summary)
        result = await self.db.execute(stmt)
        if result.rowcount == 0:
            raise UserNotFoundError(f"User with id {user_id} not found")
        await self.db.commit()
