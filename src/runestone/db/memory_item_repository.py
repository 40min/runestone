from datetime import datetime
from typing import Optional

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from runestone.db.models import MemoryItem


class MemoryItemRepository:
    """Repository for memory item-related database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session."""
        self.db = db

    async def get_by_id(self, item_id: int) -> Optional[MemoryItem]:
        """Get memory item by ID."""
        stmt = select(MemoryItem).filter(MemoryItem.id == item_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_user_category_key(self, user_id: int, category: str, key: str) -> Optional[MemoryItem]:
        """
        Get memory item by user_id, category, and key.
        Args:
            user_id: User ID
            category: Memory category
            key: Item key

        Returns:
            MemoryItem or None if not found
        """

        stmt = select(MemoryItem).filter(
            and_(
                MemoryItem.user_id == user_id,
                MemoryItem.category == category,
                MemoryItem.key == key,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_items(
        self,
        user_id: int,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryItem]:
        """
        List memory items with optional filters.

        Args:
            user_id: User ID
            category: Optional category filter
            status: Optional status filter
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of MemoryItem objects
        """
        stmt = select(MemoryItem).filter(MemoryItem.user_id == user_id)

        if category:
            stmt = stmt.filter(MemoryItem.category == category)

        if status:
            stmt = stmt.filter(MemoryItem.status == status)

        stmt = stmt.order_by(MemoryItem.updated_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_items(
        self,
        user_id: int,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        """
        Count memory items with optional filters.

        Args:
            user_id: User ID
            category: Optional category filter
            status: Optional status filter

        Returns:
            Count of matching items
        """
        stmt = select(func.count(MemoryItem.id)).filter(MemoryItem.user_id == user_id)

        if category:
            stmt = stmt.filter(MemoryItem.category == category)

        if status:
            stmt = stmt.filter(MemoryItem.status == status)

        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def create(self, item: MemoryItem) -> MemoryItem:
        """
        Create a new memory item.

        Args:
            item: MemoryItem object to create

        Returns:
            Created MemoryItem
        """
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def update(self, item: MemoryItem) -> MemoryItem:
        """
        Update an existing memory item.

        Args:
            item: MemoryItem object to update

        Returns:
            Updated MemoryItem
        """
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def delete(self, item_id: int) -> None:
        """
        Delete a memory item by ID.

        Args:
            item_id: ID of the item to delete
        """
        item = await self.get_by_id(item_id)
        if item:
            await self.db.delete(item)
            await self.db.commit()

    async def delete_by_category(self, user_id: int, category: str) -> int:
        """
        Delete all memory items in a category for a user.
        Args:
            user_id: User ID
            category: Category to clear

        Returns:
            Number of items deleted
        """
        stmt = delete(MemoryItem).filter(and_(MemoryItem.user_id == user_id, MemoryItem.category == category))
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def delete_mastered_older_than(self, user_id: int, cutoff: datetime) -> int:
        """
        Delete mastered area_to_improve items older than the cutoff.

        Uses coalesce(status_changed_at, updated_at) as the timestamp to compare.

        Args:
            user_id: User ID
            cutoff: Cutoff datetime (UTC)

        Returns:
            Number of items deleted
        """
        timestamp = func.coalesce(MemoryItem.status_changed_at, MemoryItem.updated_at)
        stmt = delete(MemoryItem).filter(
            and_(
                MemoryItem.user_id == user_id,
                MemoryItem.category == "area_to_improve",
                MemoryItem.status == "mastered",
                timestamp < cutoff,
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount
