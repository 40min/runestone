"""
Service layer for memory item operations.

This module contains service classes that handle business logic
for memory item-related operations.
"""

from datetime import datetime, timezone
from typing import Optional

from runestone.api.memory_item_schemas import (
    DEFAULT_STATUS_BY_CATEGORY,
    VALID_STATUSES_BY_CATEGORY,
    AreaToImproveStatus,
    KnowledgeStrengthStatus,
    MemoryCategory,
    MemoryItemResponse,
)
from runestone.core.exceptions import PermissionDeniedError, UserNotFoundError
from runestone.core.logging_config import get_logger
from runestone.db.memory_item_repository import MemoryItemRepository
from runestone.db.models import MemoryItem

logger = get_logger(__name__)


class MemoryItemService:
    """Service for memory item-related business logic."""

    # Re-exported for local use; the canonical definitions live in memory_item_schemas.
    DEFAULT_STATUS = DEFAULT_STATUS_BY_CATEGORY
    VALID_STATUSES = VALID_STATUSES_BY_CATEGORY

    def __init__(self, memory_item_repository: MemoryItemRepository):
        """Initialize service with memory item repository."""
        self.repo = memory_item_repository

    def _utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _validate_status(self, category: MemoryCategory, status: str) -> None:
        """
        Validate that status is valid for the given category.

        Args:
            category: Memory category
            status: Status to validate

        Raises:
            ValueError: If status is invalid for category
        """
        valid_statuses = self.VALID_STATUSES.get(category)
        if not valid_statuses or status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}' for category '{category.value}'")

    def list_memory_items(
        self,
        user_id: int,
        category: Optional[MemoryCategory] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryItemResponse]:
        """
        List memory items with optional filters.

        Args:
            user_id: User ID
            category: Optional category filter
            status: Optional status filter
            limit: Maximum number of items (default 100 for initial load)
            offset: Number of items to skip (for infinite scroll)

        Returns:
            List of MemoryItemResponse objects
        """
        category_value = category.value if category is not None else None
        items = self.repo.list_items(user_id, category_value, status, limit, offset)
        return [MemoryItemResponse.model_validate(item) for item in items]

    def upsert_memory_item(
        self,
        user_id: int,
        category: MemoryCategory,
        key: str,
        content: str,
        status: Optional[str] = None,
    ) -> MemoryItemResponse:
        """
        Create or update a memory item.

        Args:
            user_id: User ID
            category: Memory category
            key: Item key (unique within user+category)
            content: Item content
            status: Optional status (defaults based on category)

        Returns:
            MemoryItemResponse

        Raises:
            ValueError: If status is invalid for category
        """
        # Use default status if not provided
        if not status:
            status = self.DEFAULT_STATUS[category]

        # Validate status
        self._validate_status(category, status)

        # Check if item exists
        existing_item = self.repo.get_by_user_category_key(user_id, category.value, key)

        if existing_item:
            # Update existing item
            existing_item.content = content
            old_status = existing_item.status
            existing_item.status = status
            if old_status != status:
                existing_item.status_changed_at = self._utc_now()
            existing_item.updated_at = self._utc_now()
            updated_item = self.repo.update(existing_item)
            return MemoryItemResponse.model_validate(updated_item)
        else:
            # Create new item
            new_item = MemoryItem(
                user_id=user_id,
                category=category.value,
                key=key,
                content=content,
                status=status,
                status_changed_at=self._utc_now(),
            )
            created_item = self.repo.create(new_item)
            return MemoryItemResponse.model_validate(created_item)

    def update_item_status(self, item_id: int, new_status: str, user_id: int) -> MemoryItemResponse:
        """
        Update the status of a memory item.

        Args:
            item_id: Item ID
            new_status: New status value
            user_id: User ID (for authorization)

        Returns:
            Updated MemoryItemResponse

        Raises:
            UserNotFoundError: If item not found
            ValueError: If user doesn't own item or status is invalid
        """
        item = self.repo.get_by_id(item_id)
        if not item:
            raise UserNotFoundError(f"Memory item with id {item_id} not found")

        if item.user_id != user_id:
            raise PermissionDeniedError("You don't have permission to update this item")

        # Validate new status
        try:
            category = MemoryCategory(item.category)
        except Exception as e:
            raise ValueError(f"Invalid category '{item.category}' on memory item {item.id}") from e
        self._validate_status(category, new_status)

        # Update status
        old_status = item.status
        item.status = new_status
        if old_status != new_status:
            item.status_changed_at = self._utc_now()
        item.updated_at = self._utc_now()

        updated_item = self.repo.update(item)
        return MemoryItemResponse.model_validate(updated_item)

    def promote_to_strength(self, item_id: int, user_id: int) -> MemoryItemResponse:
        """
        Promote a mastered area_to_improve item to knowledge_strength.

        Args:
            item_id: Item ID
            user_id: User ID (for authorization)

        Returns:
            New MemoryItemResponse in knowledge_strength category

        Raises:
            UserNotFoundError: If item not found
            ValueError: If item is not mastered or not in area_to_improve
        """
        item = self.repo.get_by_id(item_id)
        if not item:
            raise UserNotFoundError(f"Memory item with id {item_id} not found")

        if item.user_id != user_id:
            raise PermissionDeniedError("You don't have permission to promote this item")

        if item.category != MemoryCategory.AREA_TO_IMPROVE.value:
            raise ValueError("Only area_to_improve items can be promoted")

        if item.status != AreaToImproveStatus.MASTERED.value:
            raise ValueError("Only mastered items can be promoted to knowledge_strength")

        # Create + delete in a single transaction to avoid partial state.
        with self.repo.db.begin():
            existing_strength = self.repo.get_by_user_category_key(
                user_id,
                MemoryCategory.KNOWLEDGE_STRENGTH.value,
                item.key,
            )
            if existing_strength:
                existing_strength.content = item.content
                old_status = existing_strength.status
                existing_strength.status = KnowledgeStrengthStatus.ACTIVE.value
                if old_status != existing_strength.status:
                    existing_strength.status_changed_at = self._utc_now()
                existing_strength.updated_at = self._utc_now()
                self.repo.db.delete(item)
                self.repo.db.flush()
                self.repo.db.refresh(existing_strength)
                promoted_item = existing_strength
            else:
                new_item = MemoryItem(
                    user_id=user_id,
                    category=MemoryCategory.KNOWLEDGE_STRENGTH.value,
                    key=item.key,
                    content=item.content,
                    status=KnowledgeStrengthStatus.ACTIVE.value,
                    status_changed_at=self._utc_now(),
                )
                self.repo.db.add(new_item)
                self.repo.db.delete(item)
                self.repo.db.flush()
                self.repo.db.refresh(new_item)
                promoted_item = new_item

        return MemoryItemResponse.model_validate(promoted_item)

    def delete_item(self, item_id: int, user_id: int) -> None:
        """
        Delete a memory item.

        Args:
            item_id: Item ID
            user_id: User ID (for authorization)

        Raises:
            UserNotFoundError: If item not found
            ValueError: If user doesn't own item
        """
        item = self.repo.get_by_id(item_id)
        if not item:
            raise UserNotFoundError(f"Memory item with id {item_id} not found")

        if item.user_id != user_id:
            raise PermissionDeniedError("You don't have permission to delete this item")

        self.repo.delete(item_id)

    def clear_category(self, user_id: int, category: MemoryCategory) -> int:
        """
        Clear all items in a category for a user.

        Args:
            user_id: User ID
            category: Category to clear

        Returns:
            Number of items deleted
        """
        return self.repo.delete_by_category(user_id, category.value)
