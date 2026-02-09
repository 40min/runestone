"""
Service layer for memory item operations.

This module contains service classes that handle business logic
for memory item-related operations.
"""

from datetime import datetime
from typing import Optional

from runestone.api.memory_item_schemas import (
    AreaToImproveStatus,
    KnowledgeStrengthStatus,
    MemoryCategory,
    MemoryItemResponse,
    PersonalInfoStatus,
)
from runestone.core.exceptions import UserNotFoundError
from runestone.core.logging_config import get_logger
from runestone.db.memory_item_repository import MemoryItemRepository
from runestone.db.models import MemoryItem

logger = get_logger(__name__)


class MemoryItemService:
    """Service for memory item-related business logic."""

    # Default statuses for each category
    DEFAULT_STATUS = {
        MemoryCategory.PERSONAL_INFO: PersonalInfoStatus.ACTIVE.value,
        MemoryCategory.AREA_TO_IMPROVE: AreaToImproveStatus.STRUGGLING.value,
        MemoryCategory.KNOWLEDGE_STRENGTH: KnowledgeStrengthStatus.ACTIVE.value,
    }

    # Valid status transitions per category
    VALID_STATUSES = {
        MemoryCategory.PERSONAL_INFO: {s.value for s in PersonalInfoStatus},
        MemoryCategory.AREA_TO_IMPROVE: {s.value for s in AreaToImproveStatus},
        MemoryCategory.KNOWLEDGE_STRENGTH: {s.value for s in KnowledgeStrengthStatus},
    }

    def __init__(self, memory_item_repository: MemoryItemRepository):
        """Initialize service with memory item repository."""
        self.repo = memory_item_repository

    def _validate_status(self, category: str, status: str) -> None:
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
            raise ValueError(f"Invalid status '{status}' for category '{category}'")

    def list_memory_items(
        self,
        user_id: int,
        category: Optional[str] = None,
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
        items = self.repo.list_items(user_id, category, status, limit, offset)
        return [MemoryItemResponse.model_validate(item) for item in items]

    def upsert_memory_item(
        self,
        user_id: int,
        category: str,
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
            status = self.DEFAULT_STATUS.get(category, "active")

        # Validate status
        self._validate_status(category, status)

        # Check if item exists
        existing_item = self.repo.get_by_user_category_key(user_id, category, key)

        if existing_item:
            # Update existing item
            existing_item.content = content
            old_status = existing_item.status
            existing_item.status = status
            if old_status != status:
                existing_item.status_changed_at = datetime.utcnow()
            existing_item.updated_at = datetime.utcnow()
            updated_item = self.repo.update(existing_item)
            return MemoryItemResponse.model_validate(updated_item)
        else:
            # Create new item
            new_item = MemoryItem(
                user_id=user_id,
                category=category,
                key=key,
                content=content,
                status=status,
                status_changed_at=datetime.utcnow(),
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
            raise ValueError("You don't have permission to update this item")

        # Validate new status
        self._validate_status(item.category, new_status)

        # Update status
        old_status = item.status
        item.status = new_status
        if old_status != new_status:
            item.status_changed_at = datetime.utcnow()
        item.updated_at = datetime.utcnow()

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
            raise ValueError("You don't have permission to promote this item")

        if item.category != MemoryCategory.AREA_TO_IMPROVE.value:
            raise ValueError("Only area_to_improve items can be promoted")

        if item.status != AreaToImproveStatus.MASTERED.value:
            raise ValueError("Only mastered items can be promoted to knowledge_strength")

        # Create new knowledge_strength item
        new_item = MemoryItem(
            user_id=user_id,
            category=MemoryCategory.KNOWLEDGE_STRENGTH.value,
            key=item.key,
            content=item.content,
            status=KnowledgeStrengthStatus.ACTIVE.value,
            status_changed_at=datetime.utcnow(),
        )
        created_item = self.repo.create(new_item)

        # Delete the old area_to_improve item
        self.repo.delete(item_id)

        return MemoryItemResponse.model_validate(created_item)

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
            raise ValueError("You don't have permission to delete this item")

        self.repo.delete(item_id)

    def clear_category(self, user_id: int, category: str) -> int:
        """
        Clear all items in a category for a user.

        Args:
            user_id: User ID
            category: Category to clear

        Returns:
            Number of items deleted
        """
        return self.repo.delete_by_category(user_id, category)
