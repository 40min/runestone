"""
Service layer for memory item operations.

This module contains service classes that handle business logic
for memory item-related operations.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError

from runestone.agents.schemas import AgentPersonalInfoStatus
from runestone.api.memory_item_schemas import (
    DEFAULT_STATUS_BY_CATEGORY,
    VALID_STATUSES_BY_CATEGORY,
    MemoryCategory,
    MemoryItemResponse,
    MemorySortBy,
    PersonalInfoStatus,
    SortDirection,
)
from runestone.constants import MEMORY_DEFAULT_AREA_TO_IMPROVE_PRIORITY
from runestone.core.exceptions import MemoryItemNotFoundError, PermissionDeniedError
from runestone.core.logging_config import get_logger
from runestone.db.memory_item_repository import MemoryItemRepository
from runestone.db.models import MemoryItem

logger = get_logger(__name__)


class MemoryItemService:
    """Service for memory item-related business logic."""

    # Re-exported for local use; the canonical definitions live in memory_item_schemas.
    DEFAULT_STATUS = DEFAULT_STATUS_BY_CATEGORY
    VALID_STATUSES = VALID_STATUSES_BY_CATEGORY
    PERSONAL_INFO_ACTIVE = AgentPersonalInfoStatus.ACTIVE.value
    PERSONAL_INFO_AGENT_STATUSES = {status.value for status in AgentPersonalInfoStatus}

    def __init__(self, memory_item_repository: MemoryItemRepository):
        """Initialize service with memory item repository."""
        self.repo = memory_item_repository

    def _utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def get_item_by_id(self, item_id: int) -> Optional[MemoryItem]:
        """Return one memory item by id for service-layer callers that need raw row access."""
        return await self.repo.get_by_id(item_id)

    async def get_items_by_ids(self, item_ids: list[int]) -> list[MemoryItem]:
        """Return raw memory items by id while keeping repository access behind the service boundary."""
        return await self.repo.get_by_ids(item_ids)

    async def get_item_by_user_category_key(
        self,
        user_id: int,
        category: MemoryCategory,
        key: str,
    ) -> Optional[MemoryItem]:
        """Return one memory item by user, category, and key."""
        return await self.repo.get_by_user_category_key(user_id, category.value, key)

    async def list_item_keys(self, user_id: int, category: MemoryCategory) -> set[str]:
        """Return all distinct keys for one user's category without list pagination semantics."""
        return await self.repo.list_keys_by_user_category(user_id, category.value)

    def validate_status(self, category: MemoryCategory, status: str) -> None:
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

    async def list_memory_items(
        self,
        user_id: int,
        category: Optional[MemoryCategory] = None,
        statuses: list[str] | tuple[str, ...] | None = None,
        sort_by: Optional[MemorySortBy] = None,
        sort_direction: SortDirection = SortDirection.DESC,
        limit: int | None = 100,
        offset: int = 0,
    ) -> list[MemoryItemResponse]:
        """
        List memory items with optional filters.

        Args:
            user_id: User ID
            category: Optional category filter
            statuses: Optional status filters
            sort_by: Optional explicit sort field
            sort_direction: Sort direction for explicit sort field
            limit: Maximum number of items (default 100 for initial load), or `None` for no limit
            offset: Number of items to skip (for infinite scroll)

        Returns:
            List of MemoryItemResponse objects
        """
        if sort_by == MemorySortBy.PRIORITY and category != MemoryCategory.AREA_TO_IMPROVE:
            raise ValueError("priority sorting is only supported for category 'area_to_improve'")

        category_value = category.value if category is not None else None
        sort_by_value = sort_by.value if sort_by is not None else None
        items = await self.repo.list_items(
            user_id=user_id,
            category=category_value,
            statuses=tuple(statuses) if statuses is not None else None,
            limit=limit,
            offset=offset,
            sort_by=sort_by_value,
            sort_direction=sort_direction.value,
        )
        return [MemoryItemResponse.model_validate(item) for item in items]

    async def list_start_area_to_improve_items(
        self,
        user_id: int,
        area_limit: int,
    ) -> list[MemoryItemResponse]:
        """Return the compact starter learning-focus bundle used at the start of a chat."""
        items = await self.repo.list_start_area_to_improve_items(
            user_id,
            area_limit=area_limit,
        )
        return [MemoryItemResponse.model_validate(item) for item in items]

    async def append_personal_info_item(
        self,
        user_id: int,
        *,
        key: str,
        content: str,
        status: str,
    ) -> MemoryItemResponse:
        """Create a new personal_info memory row without checking for an existing key."""
        category = MemoryCategory.PERSONAL_INFO
        if status not in self.PERSONAL_INFO_AGENT_STATUSES:
            raise ValueError(f"Invalid agent personal_info status '{status}'")

        if not isinstance(key, str) or not key.strip():
            raise ValueError("key must not be empty")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must not be empty")

        new_item = MemoryItem(
            user_id=user_id,
            category=category.value,
            key=key,
            content=content,
            status=status,
            status_changed_at=self._utc_now(),
        )
        created_item = await self.repo.create(new_item)
        return MemoryItemResponse.model_validate(created_item)

    async def create_item(
        self,
        user_id: int,
        category: MemoryCategory,
        key: str,
        content: str,
        status: Optional[str] = None,
        priority: Optional[int] = None,
    ) -> MemoryItemResponse:
        """Create a new public memory item."""
        if not status:
            status = self.DEFAULT_STATUS[category]

        self.validate_status(category, status)

        if category == MemoryCategory.AREA_TO_IMPROVE:
            if priority is not None and not (0 <= priority <= 9):
                raise ValueError(f"priority must be between 0 and 9, got {priority}")
        elif priority is not None:
            raise ValueError("priority is only applicable to category 'area_to_improve'")

        existing_item = await self.repo.get_by_user_category_key(user_id, category.value, key)
        if existing_item:
            raise ValueError(f"Memory item with key '{key}' already exists in category '{category.value}'")

        create_priority = priority
        if category == MemoryCategory.AREA_TO_IMPROVE and create_priority is None:
            create_priority = MEMORY_DEFAULT_AREA_TO_IMPROVE_PRIORITY

        new_item = MemoryItem(
            user_id=user_id,
            category=category.value,
            key=key,
            content=content,
            status=status,
            priority=create_priority,
            status_changed_at=self._utc_now(),
        )
        created_item = await self.repo.create(new_item)
        return MemoryItemResponse.model_validate(created_item)

    async def upsert_memory_item(
        self,
        user_id: int,
        category: MemoryCategory,
        key: str,
        content: str,
        status: Optional[str] = None,
        priority: Optional[int] = None,
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
        if not status:
            status = self.DEFAULT_STATUS[category]

        self.validate_status(category, status)

        # Check if item exists
        existing_item = await self.repo.get_by_user_category_key(user_id, category.value, key)

        # Validate priority
        if category == MemoryCategory.AREA_TO_IMPROVE:
            if priority is not None and not (0 <= priority <= 9):
                raise ValueError(f"priority must be between 0 and 9, got {priority}")
        elif priority is not None:
            raise ValueError("priority is only applicable to category 'area_to_improve'")

        if existing_item:
            # Update existing item
            existing_item.content = content
            old_status = existing_item.status
            existing_item.status = status
            if old_status != status:
                existing_item.status_changed_at = self._utc_now()
            if priority is not None:
                existing_item.priority = priority
            existing_item.updated_at = self._utc_now()
            updated_item = await self.repo.update(existing_item)
            return MemoryItemResponse.model_validate(updated_item)
        else:
            # Create new item
            create_priority = priority
            if category == MemoryCategory.AREA_TO_IMPROVE and create_priority is None:
                create_priority = MEMORY_DEFAULT_AREA_TO_IMPROVE_PRIORITY
            new_item = MemoryItem(
                user_id=user_id,
                category=category.value,
                key=key,
                content=content,
                status=status,
                priority=create_priority,
                status_changed_at=self._utc_now(),
            )
            created_item = await self.repo.create(new_item)
            return MemoryItemResponse.model_validate(created_item)

    async def update_item_status(self, item_id: int, new_status: str, user_id: int) -> MemoryItemResponse:
        """
        Update the status of a memory item.

        Args:
            item_id: Item ID
            new_status: New status value
            user_id: User ID (for authorization)

        Returns:
            Updated MemoryItemResponse

        Raises:
            MemoryItemNotFoundError: If item not found
            ValueError: If user doesn't own item or status is invalid
        """
        item = await self.repo.get_by_id(item_id)
        if not item:
            raise MemoryItemNotFoundError(f"Memory item with id {item_id} not found")

        if item.user_id != user_id:
            raise PermissionDeniedError("You don't have permission to update this item")

        # Validate new status
        try:
            category = MemoryCategory(item.category)
        except Exception as e:
            raise ValueError(f"Invalid category '{item.category}' on memory item {item.id}") from e
        if category == MemoryCategory.PERSONAL_INFO:
            raise ValueError("status updates are not supported for category 'personal_info'")
        self.validate_status(category, new_status)

        # Update status
        old_status = item.status
        item.status = new_status
        if old_status != new_status:
            item.status_changed_at = self._utc_now()
        item.updated_at = self._utc_now()

        updated_item = await self.repo.update(item)
        return MemoryItemResponse.model_validate(updated_item)

    async def update_personal_info_status_for_maintenance(
        self,
        item_id: int,
        new_status: str,
        user_id: int,
    ) -> MemoryItemResponse:
        """Update personal_info workflow status for internal maintenance only."""
        item = await self.repo.get_by_id(item_id)
        if not item:
            raise MemoryItemNotFoundError(f"Memory item with id {item_id} not found")
        if item.user_id != user_id:
            raise PermissionDeniedError("You don't have permission to update this item")
        if item.category != MemoryCategory.PERSONAL_INFO.value:
            raise ValueError("maintenance status updates are only supported for category 'personal_info'")
        if new_status not in self.PERSONAL_INFO_AGENT_STATUSES:
            raise ValueError(f"Invalid agent personal_info status '{new_status}'")

        old_status = item.status
        item.status = new_status
        if old_status != new_status:
            item.status_changed_at = self._utc_now()
        item.updated_at = self._utc_now()
        updated_item = await self.repo.update(item)
        return MemoryItemResponse.model_validate(updated_item)

    async def update_item_content_in_category(
        self,
        item_id: int,
        category: MemoryCategory,
        content: str,
        user_id: int,
    ) -> MemoryItemResponse:
        """
        Update the content of a memory item and require the expected category to match.

        Args:
            item_id: Item ID
            category: Expected category for the item
            content: Replacement content for the existing item
            user_id: User ID (for authorization)

        Returns:
            Updated MemoryItemResponse

        Raises:
            MemoryItemNotFoundError: If item not found
            PermissionDeniedError: If user doesn't own item
            ValueError: If category mismatches or content is blank
        """
        item = await self.repo.get_by_id(item_id)
        if not item:
            raise MemoryItemNotFoundError(f"Memory item with id {item_id} not found")

        if item.user_id != user_id:
            raise PermissionDeniedError("You don't have permission to update this item")

        if item.category != category.value:
            raise ValueError(f"content update category mismatch: expected '{category.value}', found '{item.category}'")

        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must not be empty")

        if item.category == MemoryCategory.PERSONAL_INFO.value and item.status != self.PERSONAL_INFO_ACTIVE:
            raise ValueError("personal_info item is no longer active")

        item.content = content
        item.updated_at = self._utc_now()
        updated_item = await self.repo.update(item)
        return MemoryItemResponse.model_validate(updated_item)

    async def update_item(
        self,
        item_id: int,
        *,
        key: str,
        content: str,
        status: Optional[str],
        priority: Optional[int],
        user_id: int,
    ) -> MemoryItemResponse:
        """Update an existing memory item's editable fields."""

        if not isinstance(key, str) or not key.strip():
            raise ValueError("key must not be empty")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must not be empty")

        item = await self.repo.get_by_id(item_id)
        if not item:
            raise MemoryItemNotFoundError(f"Memory item with id {item_id} not found")
        if item.user_id != user_id:
            raise PermissionDeniedError("You don't have permission to update this item")

        category = MemoryCategory(item.category)
        if category == MemoryCategory.PERSONAL_INFO and item.status != PersonalInfoStatus.ACTIVE.value:
            raise ValueError("personal_info items can only be edited while active")

        existing_item = await self.repo.get_by_user_category_key(item.user_id, item.category, key)
        if existing_item and existing_item.id != item.id:
            raise ValueError(f"Memory item with key '{key}' already exists in category '{item.category}'")

        if status is not None:
            self.validate_status(category, status)
            old_status = item.status
            item.status = status
            if old_status != status:
                item.status_changed_at = self._utc_now()

        if category == MemoryCategory.AREA_TO_IMPROVE:
            if priority is not None and not (0 <= priority <= 9):
                raise ValueError(f"priority must be between 0 and 9, got {priority}")
            if priority is not None:
                item.priority = priority
        elif priority is not None:
            raise ValueError("priority is only applicable to category 'area_to_improve'")

        item.key = key
        item.content = content
        item.updated_at = self._utc_now()
        updated_item = await self.repo.update(item)
        return MemoryItemResponse.model_validate(updated_item)

    async def update_item_priority(self, item_id: int, priority: Optional[int], user_id: int) -> MemoryItemResponse:
        """
        Set the priority of an area_to_improve memory item.

        Args:
            item_id: Item ID
            priority: New priority (0-9). None maps to 9 (lowest/default).
            user_id: User ID (for authorization)

        Returns:
            Updated MemoryItemResponse

        Raises:
            MemoryItemNotFoundError: If item not found
            PermissionDeniedError: If user doesn't own item
            ValueError: If category is not area_to_improve or priority out of range
        """
        item = await self.repo.get_by_id(item_id)
        if not item:
            raise MemoryItemNotFoundError(f"Memory item with id {item_id} not found")

        if item.user_id != user_id:
            raise PermissionDeniedError("You don't have permission to update this item")

        if item.category != MemoryCategory.AREA_TO_IMPROVE.value:
            raise ValueError("priority is only applicable to category 'area_to_improve'")

        if priority is None:
            priority = MEMORY_DEFAULT_AREA_TO_IMPROVE_PRIORITY

        if not (0 <= priority <= 9):
            raise ValueError(f"priority must be between 0 and 9, got {priority}")

        item.priority = priority
        item.updated_at = self._utc_now()
        updated_item = await self.repo.update(item)
        return MemoryItemResponse.model_validate(updated_item)

    async def update_item_priority_with_old_value(
        self,
        item_id: int,
        priority: Optional[int],
        user_id: int,
    ) -> tuple[int | None, MemoryItemResponse]:
        """
        Update an item's priority and return both the previous and updated values.

        Returns:
            Tuple of previous priority and updated response.

        Raises:
            MemoryItemNotFoundError: If item not found.
            PermissionDeniedError: If the user does not own the item.
            ValueError: If the item cannot accept priority updates or the new priority is invalid.
        """
        item = await self.repo.get_by_id(item_id)
        if not item:
            raise MemoryItemNotFoundError(f"Memory item with id {item_id} not found")

        if item.user_id != user_id:
            raise PermissionDeniedError("You don't have permission to update this item")

        old_priority = item.priority
        updated_item = await self.update_item_priority(item_id, priority, user_id)
        return old_priority, updated_item

    async def create_item_and_delete_sources(
        self,
        *,
        item: MemoryItem,
        source_items: list[MemoryItem],
    ) -> tuple[MemoryItemResponse, list[int]]:
        """
        Persist a new memory item and delete the supplied source items atomically.

        The caller is responsible for constructing a valid `MemoryItem` and validating that
        the supplied source items should be replaced together.

        Raises:
            ValueError: If the new item is structurally invalid.
            RuntimeError: If create/delete/commit fails after the write transaction starts.
        """
        if not isinstance(item.key, str) or not item.key.strip():
            raise ValueError("invalid_target_key:empty")
        if not isinstance(item.content, str) or not item.content.strip():
            raise ValueError("content must not be empty")

        db = self.repo.db
        db.add(item)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError("duplicate_target_key") from exc
        except Exception as exc:
            await db.rollback()
            raise RuntimeError(f"create_failed:{type(exc).__name__}") from exc

        created_response = MemoryItemResponse(
            id=item.id,
            user_id=item.user_id,
            category=item.category,
            key=item.key,
            content=item.content,
            status=item.status,
            priority=item.priority,
            created_at=item.created_at,
            updated_at=item.updated_at,
            status_changed_at=item.status_changed_at,
            metadata_json=item.metadata_json,
        )

        deleted_ids: list[int] = []
        for item in source_items:
            try:
                await db.delete(item)
                deleted_ids.append(item.id)
            except Exception as exc:
                await db.rollback()
                raise RuntimeError(f"delete_failed:{type(exc).__name__}") from exc

        try:
            await db.commit()
        except Exception as exc:
            await db.rollback()
            raise RuntimeError(f"commit_failed:{type(exc).__name__}") from exc

        return created_response, deleted_ids

    async def delete_item(self, item_id: int, user_id: int) -> None:
        """
        Delete a memory item.

        Args:
            item_id: Item ID
            user_id: User ID (for authorization)

        Raises:
            MemoryItemNotFoundError: If item not found
            ValueError: If user doesn't own item
        """
        item = await self.repo.get_by_id(item_id)
        if not item:
            raise MemoryItemNotFoundError(f"Memory item with id {item_id} not found")

        if item.user_id != user_id:
            raise PermissionDeniedError("You don't have permission to delete this item")

        await self.repo.delete(item_id)

    async def cleanup_old_mastered_areas(self, user_id: int, older_than_days: int) -> int:
        """
        Delete old mastered area_to_improve items.

        Intended to run at the start of a new chat to keep memory compact.
        """
        cutoff = self._utc_now() - timedelta(days=older_than_days)
        logger.info(
            "Cleaning up mastered area_to_improve items older than %s for user %s",
            cutoff,
            user_id,
        )
        return await self.repo.delete_mastered_older_than(user_id=user_id, cutoff=cutoff)

    async def cleanup_stale_personal_info_outdated(
        self,
        user_id: int,
        older_than_days: int,
        *,
        dry_run: bool = False,
    ) -> int:
        """Count or delete outdated personal_info rows older than the retention window."""
        cutoff = self._utc_now() - timedelta(days=older_than_days)
        logger.info(
            "Cleaning up outdated personal_info items older than %s for user %s (dry_run=%s)",
            cutoff,
            user_id,
            dry_run,
        )
        if dry_run:
            return await self.repo.count_personal_info_outdated_older_than(user_id=user_id, cutoff=cutoff)
        return await self.repo.delete_personal_info_outdated_older_than(user_id=user_id, cutoff=cutoff)

    async def clear_category(self, user_id: int, category: MemoryCategory) -> int:
        """
        Clear all items in a category for a user.

        Args:
            user_id: User ID
            category: Category to clear

        Returns:
            Number of items deleted
        """
        return await self.repo.delete_by_category(user_id, category.value)
