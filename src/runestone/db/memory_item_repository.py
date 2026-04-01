from datetime import datetime
from typing import Optional

from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from runestone.constants import MEMORY_DEFAULT_AREA_TO_IMPROVE_PRIORITY
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
        sort_by: Optional[str] = None,
        sort_direction: str = "desc",
    ) -> list[MemoryItem]:
        """
        List memory items with optional filters.

        Args:
            user_id: User ID
            category: Optional category filter
            status: Optional status filter
            limit: Maximum number of items to return
            offset: Number of items to skip
            sort_by: Optional explicit sort field (`updated_at` or `priority`)
            sort_direction: Sort direction (`asc` or `desc`), defaults to `desc`

        Returns:
            List of MemoryItem objects
        """
        stmt = select(MemoryItem).filter(MemoryItem.user_id == user_id)

        if category:
            stmt = stmt.filter(MemoryItem.category == category)

        if status:
            stmt = stmt.filter(MemoryItem.status == status)

        direction_desc = sort_direction == "desc"
        if sort_by == "priority":
            priority_order = MemoryItem.priority.desc() if direction_desc else MemoryItem.priority.asc()
            stmt = stmt.order_by(priority_order.nulls_last(), MemoryItem.updated_at.desc(), MemoryItem.id.asc())
        elif sort_by == "updated_at":
            updated_order = MemoryItem.updated_at.desc() if direction_desc else MemoryItem.updated_at.asc()
            stmt = stmt.order_by(updated_order, MemoryItem.id.asc())
        elif category == "area_to_improve":
            stmt = stmt.order_by(
                MemoryItem.priority.asc().nulls_last(), MemoryItem.updated_at.desc(), MemoryItem.id.asc()
            )
        else:
            stmt = stmt.order_by(MemoryItem.updated_at.desc(), MemoryItem.id.asc())

        stmt = stmt.limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_start_student_info_items(
        self,
        user_id: int,
        *,
        personal_limit: int,
        area_limit: int,
        knowledge_limit: int,
    ) -> list[MemoryItem]:
        """Fetch compact start-of-chat memory in a single query."""
        personal_match = and_(MemoryItem.category == "personal_info", MemoryItem.status == "active")
        area_match = and_(
            MemoryItem.category == "area_to_improve",
            MemoryItem.status.in_(["struggling", "improving"]),
        )
        knowledge_match = and_(MemoryItem.category == "knowledge_strength", MemoryItem.status == "active")

        bucket = case(
            (personal_match, "personal_info"),
            (area_match, "area_to_improve"),
            (knowledge_match, "knowledge_strength"),
            else_=None,
        )
        ranked = (
            select(
                MemoryItem.id.label("id"),
                bucket.label("bucket"),
                func.row_number()
                .over(
                    partition_by=bucket,
                    order_by=(
                        case(
                            (
                                MemoryItem.category == "area_to_improve",
                                func.coalesce(MemoryItem.priority, MEMORY_DEFAULT_AREA_TO_IMPROVE_PRIORITY),
                            ),
                            else_=99,
                        ).asc(),
                        MemoryItem.updated_at.desc(),
                        MemoryItem.id.asc(),
                    ),
                )
                .label("row_num"),
            )
            .where(MemoryItem.user_id == user_id, or_(personal_match, area_match, knowledge_match))
            .subquery()
        )

        stmt = (
            select(MemoryItem)
            .join(ranked, MemoryItem.id == ranked.c.id)
            .where(
                or_(
                    and_(ranked.c.bucket == "personal_info", ranked.c.row_num <= personal_limit),
                    and_(ranked.c.bucket == "area_to_improve", ranked.c.row_num <= area_limit),
                    and_(ranked.c.bucket == "knowledge_strength", ranked.c.row_num <= knowledge_limit),
                )
            )
            .order_by(
                case(
                    (ranked.c.bucket == "personal_info", 0),
                    (ranked.c.bucket == "area_to_improve", 1),
                    (ranked.c.bucket == "knowledge_strength", 2),
                    else_=3,
                ),
                case(
                    (
                        ranked.c.bucket == "area_to_improve",
                        func.coalesce(MemoryItem.priority, MEMORY_DEFAULT_AREA_TO_IMPROVE_PRIORITY),
                    ),
                    else_=99,
                ).asc(),
                MemoryItem.updated_at.desc(),
                MemoryItem.id.asc(),
            )
        )

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
