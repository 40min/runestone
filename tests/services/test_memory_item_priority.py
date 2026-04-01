from datetime import datetime, timezone
from typing import Optional

import pytest

from runestone.api.memory_item_schemas import (
    AreaToImproveStatus,
    MemoryCategory,
    MemorySortBy,
    PersonalInfoStatus,
    SortDirection,
)
from runestone.core.exceptions import PermissionDeniedError
from runestone.db.memory_item_repository import MemoryItemRepository
from runestone.db.models import MemoryItem
from runestone.services.memory_item_service import MemoryItemService


def _service(db) -> MemoryItemService:
    return MemoryItemService(MemoryItemRepository(db))


def _area_item(user_id: int, key: str, priority: Optional[int] = None) -> MemoryItem:
    return MemoryItem(
        user_id=user_id,
        category=MemoryCategory.AREA_TO_IMPROVE.value,
        key=key,
        content=f"Content for {key}",
        status=AreaToImproveStatus.STRUGGLING.value,
        priority=priority,
    )


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------


async def test_priority_ordering_area_to_improve(db_with_test_user):
    db, user = db_with_test_user
    db.add_all(
        [
            _area_item(user.id, "p5", priority=5),
            _area_item(user.id, "p1", priority=1),
            _area_item(user.id, "null_prio", priority=None),
            _area_item(user.id, "p3", priority=3),
        ]
    )
    await db.commit()

    repo = MemoryItemRepository(db)
    items = await repo.list_items(user.id, category="area_to_improve")
    keys = [i.key for i in items]
    # Prioritised items first (ascending), NULLs last
    assert keys == ["p1", "p3", "p5", "null_prio"]


async def test_priority_ordering_area_to_improve_desc(db_with_test_user):
    db, user = db_with_test_user
    db.add_all(
        [
            _area_item(user.id, "p5", priority=5),
            _area_item(user.id, "p1", priority=1),
            _area_item(user.id, "null_prio", priority=None),
            _area_item(user.id, "p3", priority=3),
        ]
    )
    await db.commit()

    repo = MemoryItemRepository(db)
    items = await repo.list_items(user.id, category="area_to_improve", sort_by="priority", sort_direction="desc")
    keys = [i.key for i in items]
    # Descending by coalesced priority (NULL -> 9) keeps missing priority as lowest urgency.
    assert keys == ["null_prio", "p5", "p3", "p1"]


async def test_updated_at_ordering_asc(db_with_test_user):
    db, user = db_with_test_user
    base = datetime(2026, 3, 10, tzinfo=timezone.utc)
    db.add_all(
        [
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.PERSONAL_INFO.value,
                key="newer",
                content="newer",
                status=PersonalInfoStatus.ACTIVE.value,
                updated_at=base.replace(minute=10),
            ),
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.PERSONAL_INFO.value,
                key="older",
                content="older",
                status=PersonalInfoStatus.ACTIVE.value,
                updated_at=base.replace(minute=1),
            ),
        ]
    )
    await db.commit()

    repo = MemoryItemRepository(db)
    items = await repo.list_items(user.id, category="personal_info", sort_by="updated_at", sort_direction="asc")
    assert [i.key for i in items] == ["older", "newer"]


async def test_updated_at_ordering_desc(db_with_test_user):
    db, user = db_with_test_user
    base = datetime(2026, 3, 10, tzinfo=timezone.utc)
    db.add_all(
        [
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.KNOWLEDGE_STRENGTH.value,
                key="older",
                content="older",
                status="active",
                updated_at=base.replace(minute=1),
            ),
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.KNOWLEDGE_STRENGTH.value,
                key="newer",
                content="newer",
                status="active",
                updated_at=base.replace(minute=10),
            ),
        ]
    )
    await db.commit()

    repo = MemoryItemRepository(db)
    items = await repo.list_items(user.id, category="knowledge_strength", sort_by="updated_at", sort_direction="desc")
    assert [i.key for i in items] == ["newer", "older"]


async def test_service_rejects_priority_sort_for_non_area_category(db_with_test_user):
    db, user = db_with_test_user
    service = _service(db)

    with pytest.raises(ValueError, match="priority sorting is only supported"):
        await service.list_memory_items(
            user_id=user.id,
            category=MemoryCategory.PERSONAL_INFO,
            sort_by=MemorySortBy.PRIORITY,
            sort_direction=SortDirection.ASC,
        )


# ---------------------------------------------------------------------------
# Upsert with priority
# ---------------------------------------------------------------------------


async def test_upsert_sets_priority_for_area_to_improve(db_with_test_user):
    db, user = db_with_test_user
    service = _service(db)

    result = await service.upsert_memory_item(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE,
        key="verb_tense",
        content="Struggles with past tense",
        priority=2,
    )

    assert result.priority == 2

    # Update priority via upsert
    result2 = await service.upsert_memory_item(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE,
        key="verb_tense",
        content="Struggles with past tense",
        priority=0,
    )
    assert result2.priority == 0


async def test_upsert_defaults_priority_to_9_for_new_area_item(db_with_test_user):
    db, user = db_with_test_user
    service = _service(db)

    result = await service.upsert_memory_item(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE,
        key="article_usage",
        content="Misses definite article in set phrases",
    )

    assert result.priority == 9


async def test_upsert_priority_rejected_for_other_categories(db_with_test_user):
    db, user = db_with_test_user
    service = _service(db)

    with pytest.raises(ValueError, match="priority"):
        await service.upsert_memory_item(
            user_id=user.id,
            category=MemoryCategory.PERSONAL_INFO,
            key="name",
            content="Alice",
            priority=1,
        )


async def test_upsert_does_not_overwrite_priority_when_not_passed(db_with_test_user):
    """Upserting without a priority should leave existing priority unchanged."""
    db, user = db_with_test_user
    db.add(_area_item(user.id, "existing", priority=3))
    await db.commit()

    service = _service(db)
    result = await service.upsert_memory_item(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE,
        key="existing",
        content="Updated content",
    )
    assert result.priority == 3


# ---------------------------------------------------------------------------
# update_item_priority
# ---------------------------------------------------------------------------


async def test_update_item_priority_success(db_with_test_user, monkeypatch):
    db, user = db_with_test_user
    item = _area_item(user.id, "grammar")
    db.add(item)
    await db.commit()
    await db.refresh(item)

    fixed_now = datetime(2026, 3, 4, tzinfo=timezone.utc)
    service = _service(db)
    monkeypatch.setattr(service, "_utc_now", lambda: fixed_now)

    result = await service.update_item_priority(item.id, 1, user.id)

    assert result.priority == 1
    await db.refresh(item)
    assert item.priority == 1
    assert item.updated_at.replace(tzinfo=timezone.utc) == fixed_now


async def test_update_item_priority_null_maps_to_lowest(db_with_test_user):
    db, user = db_with_test_user
    item = _area_item(user.id, "grammar", priority=4)
    db.add(item)
    await db.commit()
    await db.refresh(item)

    service = _service(db)
    result = await service.update_item_priority(item.id, None, user.id)

    assert result.priority == 9


async def test_update_item_priority_wrong_category(db_with_test_user):
    db, user = db_with_test_user
    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO.value,
        key="name",
        content="Alice",
        status=PersonalInfoStatus.ACTIVE.value,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    service = _service(db)
    with pytest.raises(ValueError, match="area_to_improve"):
        await service.update_item_priority(item.id, 1, user.id)


async def test_update_item_priority_permission_denied(db_with_test_user):
    db, user = db_with_test_user
    item = _area_item(user.id, "grammar")
    db.add(item)
    await db.commit()
    await db.refresh(item)

    service = _service(db)
    with pytest.raises(PermissionDeniedError):
        await service.update_item_priority(item.id, 2, user.id + 1)


async def test_update_item_priority_not_found(db_with_test_user):
    from runestone.core.exceptions import UserNotFoundError

    db, user = db_with_test_user
    service = _service(db)

    with pytest.raises(UserNotFoundError):
        await service.update_item_priority(99999, 1, user.id)
