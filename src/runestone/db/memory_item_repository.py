"""
Memory item repository for database operations.

This module contains repository classes that encapsulate database
logic for memory item entities.
"""

from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from runestone.db.models import MemoryItem


class MemoryItemRepository:
    """Repository for memory item-related database operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def get_by_id(self, item_id: int) -> Optional[MemoryItem]:
        """Get memory item by ID."""
        return self.db.query(MemoryItem).filter(MemoryItem.id == item_id).first()

    def get_by_user_category_key(self, user_id: int, category: str, key: str) -> Optional[MemoryItem]:
        """
        Get memory item by user_id, category, and key.

        Args:
            user_id: User ID
            category: Memory category
            key: Item key

        Returns:
            MemoryItem or None if not found
        """
        return (
            self.db.query(MemoryItem)
            .filter(
                and_(
                    MemoryItem.user_id == user_id,
                    MemoryItem.category == category,
                    MemoryItem.key == key,
                )
            )
            .first()
        )

    def list_items(
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
        query = self.db.query(MemoryItem).filter(MemoryItem.user_id == user_id)

        if category:
            query = query.filter(MemoryItem.category == category)

        if status:
            query = query.filter(MemoryItem.status == status)

        return query.order_by(MemoryItem.updated_at.desc()).limit(limit).offset(offset).all()

    def count_items(
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
        query = self.db.query(func.count(MemoryItem.id)).filter(MemoryItem.user_id == user_id)

        if category:
            query = query.filter(MemoryItem.category == category)

        if status:
            query = query.filter(MemoryItem.status == status)

        return query.scalar()

    def create(self, item: MemoryItem) -> MemoryItem:
        """
        Create a new memory item.

        Args:
            item: MemoryItem object to create

        Returns:
            Created MemoryItem
        """
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update(self, item: MemoryItem) -> MemoryItem:
        """
        Update an existing memory item.

        Args:
            item: MemoryItem object to update

        Returns:
            Updated MemoryItem
        """
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item_id: int) -> None:
        """
        Delete a memory item by ID.

        Args:
            item_id: ID of the item to delete
        """
        item = self.get_by_id(item_id)
        if item:
            self.db.delete(item)
            self.db.commit()

    def delete_by_category(self, user_id: int, category: str) -> int:
        """
        Delete all memory items in a category for a user.

        Args:
            user_id: User ID
            category: Category to clear

        Returns:
            Number of items deleted
        """
        count = (
            self.db.query(MemoryItem)
            .filter(and_(MemoryItem.user_id == user_id, MemoryItem.category == category))
            .delete()
        )
        self.db.commit()
        return count
