from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from runestone.api.memory_item_schemas import AreaToImproveStatus, MemoryCategory
from runestone.db.chat_session_learning_focus_repository import ChatSessionLearningFocusRepository
from runestone.db.memory_item_repository import MemoryItemRepository
from runestone.db.models import ChatSessionLearningFocus, MemoryItem
from runestone.services.chat_session_learning_focus_service import ChatSessionLearningFocusService
from runestone.services.memory_item_service import MemoryItemService


async def test_get_chat_session_learning_focus_reuses_frozen_ids_across_turns(db_with_test_user):
    db, user = db_with_test_user
    memory_repo = MemoryItemRepository(db)
    focus_repo = ChatSessionLearningFocusRepository(db)
    memory_item_service = MemoryItemService(memory_repo)
    service = ChatSessionLearningFocusService(focus_repo, memory_item_service)

    older = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE.value,
        key="older_priority_zero",
        content="Older priority zero",
        status=AreaToImproveStatus.STRUGGLING.value,
        priority=0,
    )
    newer = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE.value,
        key="newer_priority_zero",
        content="Newer priority zero",
        status=AreaToImproveStatus.STRUGGLING.value,
        priority=0,
    )
    other = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE.value,
        key="priority_one",
        content="Priority one",
        status=AreaToImproveStatus.IMPROVING.value,
        priority=1,
    )
    db.add_all([older, newer, other])
    await db.commit()
    await db.refresh(older)
    await db.refresh(newer)
    await db.refresh(other)

    first_items, was_reseeded = await service.get_chat_session_learning_focus(user.id, "chat-1", area_limit=2)
    assert [item.id for item in first_items] == [older.id, newer.id]
    assert was_reseeded is False

    newcomer = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE.value,
        key="priority_negative_equivalent",
        content="Highest urgency but added later",
        status=AreaToImproveStatus.STRUGGLING.value,
        priority=0,
    )
    db.add(newcomer)
    await db.commit()
    await db.refresh(newcomer)

    second_items, was_reseeded = await service.get_chat_session_learning_focus(user.id, "chat-1", area_limit=2)
    assert [item.id for item in second_items] == [older.id, newer.id]
    assert was_reseeded is False


async def test_get_chat_session_learning_focus_rotates_when_all_items_mastered(db_with_test_user):
    db, user = db_with_test_user
    memory_repo = MemoryItemRepository(db)
    focus_repo = ChatSessionLearningFocusRepository(db)
    memory_item_service = MemoryItemService(memory_repo)
    service = ChatSessionLearningFocusService(focus_repo, memory_item_service)

    first = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE.value,
        key="first_batch",
        content="First batch",
        status=AreaToImproveStatus.STRUGGLING.value,
        priority=0,
    )
    second = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE.value,
        key="second_batch",
        content="Second batch",
        status=AreaToImproveStatus.IMPROVING.value,
        priority=1,
    )
    db.add_all([first, second])
    await db.commit()
    await db.refresh(first)
    await db.refresh(second)

    initial_items, was_reseeded = await service.get_chat_session_learning_focus(user.id, "chat-1", area_limit=1)
    assert [item.id for item in initial_items] == [first.id]
    assert was_reseeded is False

    first.status = AreaToImproveStatus.MASTERED.value
    await db.commit()

    rotated_items, was_reseeded = await service.get_chat_session_learning_focus(user.id, "chat-1", area_limit=1)
    assert [item.id for item in rotated_items] == [second.id]
    assert was_reseeded is True


async def test_get_chat_session_learning_focus_trims_missing_ids_without_replacing_batch(db_with_test_user):
    db, user = db_with_test_user
    memory_repo = MemoryItemRepository(db)
    focus_repo = ChatSessionLearningFocusRepository(db)
    memory_item_service = MemoryItemService(memory_repo)
    service = ChatSessionLearningFocusService(focus_repo, memory_item_service)

    survivor = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE.value,
        key="survivor",
        content="Still active",
        status=AreaToImproveStatus.STRUGGLING.value,
        priority=1,
    )
    replacement_candidate = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE.value,
        key="replacement_candidate",
        content="Should not be injected mid-session",
        status=AreaToImproveStatus.IMPROVING.value,
        priority=0,
    )
    db.add_all([survivor, replacement_candidate])
    await db.commit()
    await db.refresh(survivor)
    await db.refresh(replacement_candidate)

    await focus_repo.upsert_item_ids(user.id, "chat-1", [999999, survivor.id])

    items, was_reseeded = await service.get_chat_session_learning_focus(user.id, "chat-1", area_limit=2)
    assert [item.id for item in items] == [survivor.id]
    assert was_reseeded is False

    focus_row = await db.scalar(
        select(ChatSessionLearningFocus).where(
            ChatSessionLearningFocus.user_id == user.id,
            ChatSessionLearningFocus.chat_id == "chat-1",
        )
    )
    assert focus_row is not None
    assert focus_row.memory_item_ids_json == f"[{survivor.id}]"


async def test_cleanup_old_chat_session_learning_focus_deletes_rows_for_older_chat_ids(db_with_test_user):
    db, user = db_with_test_user
    memory_repo = MemoryItemRepository(db)
    focus_repo = ChatSessionLearningFocusRepository(db)
    memory_item_service = MemoryItemService(memory_repo)
    service = ChatSessionLearningFocusService(focus_repo, memory_item_service)

    await focus_repo.upsert_item_ids(user.id, "chat-old-1", [1, 2])
    await focus_repo.upsert_item_ids(user.id, "chat-old-2", [3])
    await focus_repo.upsert_item_ids(user.id, "chat-current", [4, 5])

    deleted = await service.cleanup_old_chat_session_learning_focus(user.id, "chat-current")

    assert deleted == 2
    remaining_rows = (
        (await db.execute(select(ChatSessionLearningFocus).where(ChatSessionLearningFocus.user_id == user.id)))
        .scalars()
        .all()
    )
    assert [row.chat_id for row in remaining_rows] == ["chat-current"]


async def test_get_chat_session_learning_focus_rotates_to_empty_when_no_active_topics_remain(db_with_test_user):
    db, user = db_with_test_user
    memory_repo = MemoryItemRepository(db)
    focus_repo = ChatSessionLearningFocusRepository(db)
    memory_item_service = MemoryItemService(memory_repo)
    service = ChatSessionLearningFocusService(focus_repo, memory_item_service)

    first = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.AREA_TO_IMPROVE.value,
        key="first_batch",
        content="First batch",
        status=AreaToImproveStatus.STRUGGLING.value,
        priority=0,
    )
    db.add(first)
    await db.commit()
    await db.refresh(first)

    # First turn loads the item
    initial_items, was_reseeded = await service.get_chat_session_learning_focus(user.id, "chat-1", area_limit=1)
    assert [item.id for item in initial_items] == [first.id]
    assert was_reseeded is False

    # Mark as mastered; no other eligible items in the database
    first.status = AreaToImproveStatus.MASTERED.value
    await db.commit()

    # Second turn rotates. Since no items remain, it should return ([], True)
    rotated_items, was_reseeded = await service.get_chat_session_learning_focus(user.id, "chat-1", area_limit=1)
    assert rotated_items == []
    assert was_reseeded is True

    # Double check that [] is persisted
    focus_row = await db.scalar(
        select(ChatSessionLearningFocus).where(
            ChatSessionLearningFocus.user_id == user.id,
            ChatSessionLearningFocus.chat_id == "chat-1",
        )
    )
    assert focus_row is not None
    assert focus_row.memory_item_ids_json == "[]"

    # Third turn should load the empty list from DB and return ([], False) without reseeding
    subsequent_items, was_reseeded = await service.get_chat_session_learning_focus(user.id, "chat-1", area_limit=1)
    assert subsequent_items == []
    assert was_reseeded is False


async def test_upsert_item_ids_recovers_from_concurrent_insert_race(db_with_test_user, monkeypatch):
    db, user = db_with_test_user
    focus_repo = ChatSessionLearningFocusRepository(db)

    existing = await focus_repo.upsert_item_ids(user.id, "chat-1", [11, 12])
    real_get_by_user_chat = focus_repo.get_by_user_chat
    real_commit = db.commit
    state = {"first_lookup": True, "first_commit": True}

    async def _racing_get_by_user_chat(user_id: int, chat_id: str):
        if state["first_lookup"]:
            state["first_lookup"] = False
            return None
        return await real_get_by_user_chat(user_id, chat_id)

    async def _flaky_commit():
        if state["first_commit"]:
            state["first_commit"] = False
            raise IntegrityError("insert", {}, Exception("duplicate key"))
        return await real_commit()

    monkeypatch.setattr(focus_repo, "get_by_user_chat", _racing_get_by_user_chat)
    monkeypatch.setattr(db, "commit", _flaky_commit)

    row = await focus_repo.upsert_item_ids(user.id, "chat-1", [11, 12])

    assert row.id == existing.id
    assert row.memory_item_ids_json == "[11, 12]"
