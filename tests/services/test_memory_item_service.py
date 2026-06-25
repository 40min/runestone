from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from runestone.agents.schemas import AgentPersonalInfoStatus
from runestone.api.memory_item_schemas import AreaToImproveStatus, MemoryCategory, PersonalInfoStatus
from runestone.core.exceptions import PermissionDeniedError
from runestone.db.memory_item_repository import MemoryItemRepository
from runestone.db.models import MemoryItem
from runestone.services.memory_item_service import MemoryItemService


async def test_cleanup_old_mastered_areas(db_with_test_user, monkeypatch):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    fixed_now = datetime(2026, 2, 11, tzinfo=timezone.utc)
    monkeypatch.setattr(service, "_utc_now", lambda: fixed_now)

    old = fixed_now - timedelta(days=120)
    recent = fixed_now - timedelta(days=10)

    db.add_all(
        [
            # Deleted: status_changed_at old (even if updated_at is recent)
            MemoryItem(
                user_id=user.id,
                category="area_to_improve",
                key="old_mastered_status_changed",
                content="Old mastered",
                status="mastered",
                status_changed_at=old,
                updated_at=recent,
            ),
            # Deleted: no status_changed_at, but updated_at old
            MemoryItem(
                user_id=user.id,
                category="area_to_improve",
                key="old_mastered_updated",
                content="Old mastered",
                status="mastered",
                status_changed_at=None,
                updated_at=old,
            ),
            # Kept: mastered but recent
            MemoryItem(
                user_id=user.id,
                category="area_to_improve",
                key="recent_mastered",
                content="Recent mastered",
                status="mastered",
                status_changed_at=recent,
                updated_at=recent,
            ),
            # Kept: old but not mastered
            MemoryItem(
                user_id=user.id,
                category="area_to_improve",
                key="old_struggling",
                content="Still struggling",
                status="struggling",
                status_changed_at=old,
                updated_at=old,
            ),
            # Kept: different category entirely
            MemoryItem(
                user_id=user.id,
                category="personal_info",
                key="old_goal",
                content="Goal",
                status="active",
                status_changed_at=old,
                updated_at=old,
            ),
        ]
    )
    await db.commit()

    deleted = await service.cleanup_old_mastered_areas(user.id, older_than_days=90)
    assert deleted == 2

    remaining = (await db.execute(select(MemoryItem).where(MemoryItem.user_id == user.id))).scalars().all()
    remaining_keys = {item.key for item in remaining}
    assert remaining_keys == {"recent_mastered", "old_struggling", "old_goal"}


async def test_upsert_memory_item_creates_with_default_status(db_with_test_user, monkeypatch):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    fixed_now = datetime(2026, 2, 11, tzinfo=timezone.utc)
    monkeypatch.setattr(service, "_utc_now", lambda: fixed_now)

    response = await service.upsert_memory_item(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO,
        key="learning_goal",
        content="Wants to practice Swedish daily",
    )

    assert response.status == "active"
    item = await repo.get_by_user_category_key(user.id, MemoryCategory.PERSONAL_INFO.value, "learning_goal")
    assert item is not None
    assert item.content == "Wants to practice Swedish daily"
    assert item.status_changed_at.replace(tzinfo=timezone.utc) == fixed_now


async def test_upsert_memory_item_updates_and_tracks_status_change(db_with_test_user, monkeypatch):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    old_time = datetime(2026, 2, 1, tzinfo=timezone.utc)
    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO.value,
        key="timezone",
        content="UTC",
        status="active",
        status_changed_at=old_time,
        updated_at=old_time,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    fixed_now = datetime(2026, 2, 11, tzinfo=timezone.utc)
    monkeypatch.setattr(service, "_utc_now", lambda: fixed_now)

    response = await service.upsert_memory_item(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO,
        key="timezone",
        content="CET",
        status="outdated",
    )

    assert response.status == "outdated"
    await db.refresh(item)
    assert item.content == "CET"
    assert item.status_changed_at.replace(tzinfo=timezone.utc) == fixed_now
    assert item.updated_at.replace(tzinfo=timezone.utc) == fixed_now


async def test_update_item_content_in_category_updates_existing_item_without_changing_status_timestamp(
    db_with_test_user, monkeypatch
):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    old_time = datetime(2026, 2, 1, tzinfo=timezone.utc)
    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO.value,
        key="mother_tongue",
        content="Finnish",
        status="active",
        status_changed_at=old_time,
        updated_at=old_time,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    fixed_now = datetime(2026, 2, 11, tzinfo=timezone.utc)
    monkeypatch.setattr(service, "_utc_now", lambda: fixed_now)

    response = await service.update_item_content_in_category(
        item_id=item.id,
        category=MemoryCategory.PERSONAL_INFO,
        content="Estonian",
        user_id=user.id,
    )

    assert response.content == "Estonian"
    await db.refresh(item)
    assert item.content == "Estonian"
    assert item.status == "active"
    assert item.status_changed_at.replace(tzinfo=timezone.utc) == old_time
    assert item.updated_at.replace(tzinfo=timezone.utc) == fixed_now


async def test_update_item_content_rejects_blank_content(db_with_test_user):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO.value,
        key="goal",
        content="Practice speaking",
        status="active",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    with pytest.raises(ValueError, match="content must not be empty"):
        await service.update_item_content_in_category(
            item_id=item.id,
            category=MemoryCategory.PERSONAL_INFO,
            content="   ",
            user_id=user.id,
        )


async def test_update_item_content_rejects_non_active_personal_info_item(db_with_test_user):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO.value,
        key="goal",
        content="Practice speaking",
        status=AgentPersonalInfoStatus.CORRECTION.value,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    with pytest.raises(ValueError, match="no longer active"):
        await service.update_item_content_in_category(
            item_id=item.id,
            category=MemoryCategory.PERSONAL_INFO,
            content="Practice reading",
            user_id=user.id,
        )


async def test_create_item_rejects_duplicate_key(db_with_test_user):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    await service.create_item(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO,
        key="goal",
        content="Practice speaking",
    )

    with pytest.raises(ValueError, match="already exists"):
        await service.create_item(
            user_id=user.id,
            category=MemoryCategory.PERSONAL_INFO,
            key="goal",
            content="Practice grammar",
        )


async def test_update_item_allows_key_and_content_change_for_active_personal_info(db_with_test_user, monkeypatch):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    old_time = datetime(2026, 2, 1, tzinfo=timezone.utc)
    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO.value,
        key="old_goal",
        content="Practice speaking",
        status=PersonalInfoStatus.ACTIVE.value,
        status_changed_at=old_time,
        updated_at=old_time,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    fixed_now = datetime(2026, 2, 11, tzinfo=timezone.utc)
    monkeypatch.setattr(service, "_utc_now", lambda: fixed_now)

    response = await service.update_item(
        item.id,
        key="new_goal",
        content="Practice grammar",
        status=None,
        priority=None,
        user_id=user.id,
    )

    assert response.key == "new_goal"
    assert response.content == "Practice grammar"
    await db.refresh(item)
    assert item.key == "new_goal"
    assert item.content == "Practice grammar"
    assert item.updated_at.replace(tzinfo=timezone.utc) == fixed_now


async def test_update_item_rejects_non_active_personal_info(db_with_test_user):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO.value,
        key="goal",
        content="Practice speaking",
        status=PersonalInfoStatus.OUTDATED.value,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    with pytest.raises(ValueError, match="only be edited while active"):
        await service.update_item(
            item.id,
            key="goal",
            content="Practice grammar",
            status=None,
            priority=None,
            user_id=user.id,
        )


async def test_update_item_content_in_category_rejects_mismatched_category(db_with_test_user):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE.value,
        key="articles",
        content="Needs practice with articles",
        status=AreaToImproveStatus.STRUGGLING.value,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    with pytest.raises(ValueError, match="content update category mismatch"):
        await service.update_item_content_in_category(
            item_id=item.id,
            category=MemoryCategory.PERSONAL_INFO,
            content="Native language is Estonian",
            user_id=user.id,
        )


async def test_list_start_area_to_improve_items_uses_single_query_and_applies_limit(db_with_test_user):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    base_time = datetime(2026, 2, 11, tzinfo=timezone.utc)

    db.add_all(
        [
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.AREA_TO_IMPROVE.value,
                key=f"topic_{idx}",
                content=f"Topic {idx}",
                status=AreaToImproveStatus.STRUGGLING.value if idx % 2 == 0 else AreaToImproveStatus.IMPROVING.value,
                priority=idx,
                updated_at=base_time + timedelta(minutes=idx),
            )
            for idx in range(8)
        ]
    )
    await db.commit()

    execute_spy = db.execute
    calls = {"count": 0}

    async def _counting_execute(*args, **kwargs):
        calls["count"] += 1
        return await execute_spy(*args, **kwargs)

    db.execute = _counting_execute
    try:
        items = await service.list_start_area_to_improve_items(
            user.id,
            area_limit=5,
        )
    finally:
        db.execute = execute_spy

    assert calls["count"] == 1
    assert [item.category for item in items] == [MemoryCategory.AREA_TO_IMPROVE.value] * 5
    assert [item.key for item in items] == [
        "topic_0",
        "topic_1",
        "topic_2",
        "topic_3",
        "topic_4",
    ]


async def test_append_personal_info_item_always_creates_new_rows(db_with_test_user):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    first = await service.append_personal_info_item(
        user.id,
        key="goal",
        content="Practice speaking",
        status=AgentPersonalInfoStatus.ACTIVE.value,
    )
    second = await service.append_personal_info_item(
        user.id,
        key="goal",
        content="Practice speaking",
        status=AgentPersonalInfoStatus.ACTIVE.value,
    )

    assert first.id != second.id
    rows = await repo.list_items(user.id, category=MemoryCategory.PERSONAL_INFO.value, sort_by="updated_at")
    assert [row.key for row in rows] == ["goal", "goal"]


async def test_list_start_area_to_improve_items_orders_by_priority_then_recency(db_with_test_user):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    base_time = datetime(2026, 2, 11, tzinfo=timezone.utc)
    db.add_all(
        [
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.AREA_TO_IMPROVE.value,
                key="priority_zero",
                content="Most urgent",
                status=AreaToImproveStatus.STRUGGLING.value,
                priority=0,
                updated_at=base_time + timedelta(minutes=1),
            ),
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.AREA_TO_IMPROVE.value,
                key="priority_one_newer",
                content="Priority one newer",
                status=AreaToImproveStatus.IMPROVING.value,
                priority=1,
                updated_at=base_time + timedelta(minutes=5),
            ),
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.AREA_TO_IMPROVE.value,
                key="priority_one_older",
                content="Priority one older",
                status=AreaToImproveStatus.STRUGGLING.value,
                priority=1,
                updated_at=base_time + timedelta(minutes=2),
            ),
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.AREA_TO_IMPROVE.value,
                key="priority_null",
                content="No explicit priority",
                status=AreaToImproveStatus.STRUGGLING.value,
                priority=None,
                updated_at=base_time + timedelta(minutes=20),
            ),
        ]
    )
    await db.commit()

    items = await service.list_start_area_to_improve_items(
        user.id,
        area_limit=4,
    )

    assert [item.key for item in items] == [
        "priority_zero",
        "priority_one_newer",
        "priority_one_older",
        "priority_null",
    ]


async def test_update_item_status_validates_and_enforces_permissions(db_with_test_user):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO.value,
        key="goal",
        content="Practice",
        status="active",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    with pytest.raises(PermissionDeniedError):
        await service.update_item_status(item.id, "outdated", user_id=user.id + 1)

    with pytest.raises(ValueError):
        await service.update_item_status(item.id, AreaToImproveStatus.MASTERED.value, user_id=user.id)

    with pytest.raises(ValueError, match="status updates are not supported"):
        await service.update_item_status(item.id, "outdated", user_id=user.id)


async def test_update_item_status_updates_timestamp(db_with_test_user, monkeypatch):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    old_time = datetime(2026, 2, 1, tzinfo=timezone.utc)
    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE.value,
        key="cases",
        content="Cases",
        status=AreaToImproveStatus.STRUGGLING.value,
        status_changed_at=old_time,
        updated_at=old_time,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    fixed_now = datetime(2026, 2, 11, tzinfo=timezone.utc)
    monkeypatch.setattr(service, "_utc_now", lambda: fixed_now)

    response = await service.update_item_status(item.id, AreaToImproveStatus.IMPROVING.value, user_id=user.id)
    assert response.status == AreaToImproveStatus.IMPROVING.value
    await db.refresh(item)
    assert item.status_changed_at.replace(tzinfo=timezone.utc) == fixed_now
    assert item.updated_at.replace(tzinfo=timezone.utc) == fixed_now


async def test_delete_item_enforces_permissions(db_with_test_user):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO.value,
        key="timezone",
        content="UTC",
        status="active",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    with pytest.raises(PermissionDeniedError):
        await service.delete_item(item.id, user_id=user.id + 1)

    await service.delete_item(item.id, user_id=user.id)
    assert await repo.get_by_id(item.id) is None


async def test_delete_item_allows_non_active_personal_info_item(db_with_test_user):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO.value,
        key="goal",
        content="Practice",
        status=AgentPersonalInfoStatus.OUTDATED.value,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    await service.delete_item(item.id, user_id=user.id)
    assert await repo.get_by_id(item.id) is None


async def test_clear_category_removes_only_matching_items(db_with_test_user):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    db.add_all(
        [
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.PERSONAL_INFO.value,
                key="goal",
                content="Daily practice",
                status="active",
            ),
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.PERSONAL_INFO.value,
                key="timezone",
                content="UTC",
                status="active",
            ),
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.AREA_TO_IMPROVE.value,
                key="articles",
                content="Basic verbs",
                status=AreaToImproveStatus.STRUGGLING.value,
            ),
        ]
    )
    await db.commit()

    deleted = await service.clear_category(user.id, MemoryCategory.PERSONAL_INFO)
    assert deleted == 2

    remaining = await repo.list_items(user.id)
    assert {item.category for item in remaining} == {MemoryCategory.AREA_TO_IMPROVE.value}
