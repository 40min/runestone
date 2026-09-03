"""PostgreSQL integration tests for recall-state persistence helpers."""

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from runestone.db.models import RecallQueueItemDB, RecallUserStateDB, User, Vocabulary
from runestone.db.recall_repository import QueueRemovalResult, RecallRepository
from runestone.recall.types import RecallQueueWord


def make_user(suffix: str, *, active: bool = True, timezone_name: str = "UTC") -> User:
    """Build a valid user with stable Telegram linkage for a test."""
    return User(
        email=f"recall-{suffix}@example.com",
        hashed_password="not-used",
        name="Recall",
        telegram_username=f"recall_{suffix}",
        active=active,
        timezone=timezone_name,
    )


async def add_words(db: AsyncSession, user_id: int, *phrases: str) -> list[Vocabulary]:
    """Persist vocabulary rows and return them in phrase order."""
    words = [Vocabulary(user_id=user_id, word_phrase=phrase, translation=f"{phrase}-translation") for phrase in phrases]
    db.add_all(words)
    await db.flush()
    return words


def as_queue_entries(words: list[Vocabulary]) -> list[RecallQueueWord]:
    """Convert persisted vocabulary rows into repository queue input."""
    return [
        RecallQueueWord(
            id=word.id,
            word_phrase=word.word_phrase,
            translation=word.translation,
            example_phrase=word.example_phrase,
        )
        for word in words
    ]


@pytest.mark.anyio
async def test_upsert_for_user_creates_and_updates_without_resetting_cursor(db_session: AsyncSession):
    user = make_user("upsert")
    db_session.add(user)
    await db_session.flush()
    repository = RecallRepository(db_session)

    created = await repository.upsert_for_user(user.id, chat_id=100, is_enabled=True)
    await repository.replace_queue(user.id, [], next_word_index=3)
    locked = await repository.get_recall_state_for_update(user.id)
    assert locked is not None
    await repository.update_locked_delivery_settings(locked, 23, 7, True)
    updated = await repository.upsert_for_user(user.id, chat_id=200, is_enabled=False)

    assert created.telegram_chat_id == 100
    assert created.is_enabled is True
    assert updated.telegram_chat_id == 200
    assert updated.is_enabled is False
    assert created.recall_start_hour == 9
    assert created.recall_end_hour == 22
    assert updated.recall_start_hour == 23
    assert updated.recall_end_hour == 7
    assert updated.next_word_index == 3
    assert await db_session.scalar(select(func.count()).select_from(RecallUserStateDB)) == 1


@pytest.mark.anyio
@pytest.mark.db_schema_reset
async def test_upsert_for_user_is_safe_for_concurrent_first_link(
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as setup_db:
        user = make_user("concurrent")
        setup_db.add(user)
        await setup_db.commit()
        user_id = user.id

    async def link(chat_id: int) -> None:
        async with db_session_factory() as db:
            repository = RecallRepository(db)
            await repository.upsert_for_user(user_id, chat_id=chat_id, is_enabled=True)
            await repository.commit()

    await asyncio.gather(link(1001), link(1002))

    async with db_session_factory() as verification_db:
        rows = list((await verification_db.scalars(select(RecallUserStateDB))).all())
        assert len(rows) == 1
        assert rows[0].telegram_chat_id in {1001, 1002}
        assert rows[0].is_enabled is True


@pytest.mark.anyio
async def test_replace_and_append_queue_preserve_order(db_session: AsyncSession):
    user = make_user("replace")
    db_session.add(user)
    await db_session.flush()
    first, second, third = await add_words(db_session, user.id, "ett", "tva", "tre")
    repository = RecallRepository(db_session)
    await repository.upsert_for_user(user.id, chat_id=123, is_enabled=True)

    await repository.replace_queue(user.id, as_queue_entries([second, first]))
    await repository.append_queue_words(user.id, as_queue_entries([third]))
    state = await repository.get_recall_state(user.id)

    assert state is not None
    assert [entry.id for entry in state.daily_selection] == [second.id, first.id, third.id]
    positions = list(
        (
            await db_session.scalars(
                select(RecallQueueItemDB.position)
                .where(RecallQueueItemDB.user_id == user.id)
                .order_by(RecallQueueItemDB.position)
            )
        ).all()
    )
    assert positions == [0, 1, 2]


@pytest.mark.anyio
async def test_remove_queue_word_compacts_positions_and_adjusts_locked_cursor(db_session: AsyncSession):
    user = make_user("remove")
    db_session.add(user)
    await db_session.flush()
    first, second, third = await add_words(db_session, user.id, "ett", "tva", "tre")
    repository = RecallRepository(db_session)
    await repository.upsert_for_user(user.id, chat_id=123, is_enabled=True)
    await repository.replace_queue(user.id, as_queue_entries([first, second, third]), next_word_index=2)

    result = await repository.remove_queue_word(user.id, first.id)
    state = await repository.get_recall_state(user.id)

    assert result == QueueRemovalResult(removed_position=0, next_word_index=1)
    assert state is not None
    assert state.next_word_index == 1
    assert [entry.id for entry in state.daily_selection] == [second.id, third.id]
    rows = list(
        (
            await db_session.scalars(
                select(RecallQueueItemDB)
                .where(RecallQueueItemDB.user_id == user.id)
                .order_by(RecallQueueItemDB.position)
            )
        ).all()
    )
    assert [(row.vocabulary_id, row.position) for row in rows] == [(second.id, 0), (third.id, 1)]


@pytest.mark.anyio
async def test_remove_queue_word_is_noop_without_state_or_matching_item(db_session: AsyncSession):
    user = make_user("remove_noop")
    db_session.add(user)
    await db_session.flush()
    word = (await add_words(db_session, user.id, "ett"))[0]
    repository = RecallRepository(db_session)

    assert await repository.remove_queue_word(user.id, word.id) is None

    await repository.upsert_for_user(user.id, chat_id=123, is_enabled=True)
    assert await repository.remove_queue_word(user.id, word.id) is None


@pytest.mark.anyio
async def test_advance_cursor_wraps_and_empty_queue_stays_at_zero(db_session: AsyncSession):
    user = make_user("advance")
    empty_user = make_user("advance_empty")
    db_session.add_all([user, empty_user])
    await db_session.flush()
    first, second = await add_words(db_session, user.id, "ett", "tva")
    repository = RecallRepository(db_session)
    await repository.upsert_for_user(user.id, chat_id=123, is_enabled=True)
    await repository.upsert_for_user(empty_user.id, chat_id=456, is_enabled=True)
    await repository.replace_queue(user.id, as_queue_entries([first, second]), next_word_index=1)
    await repository.replace_queue(empty_user.id, [], next_word_index=9)

    await repository.advance_cursor(user.id)
    await repository.advance_cursor(empty_user.id)

    wrapped = await repository.get_recall_state(user.id)
    empty = await repository.get_recall_state(empty_user.id)
    assert wrapped is not None and wrapped.next_word_index == 0
    assert empty is not None and empty.next_word_index == 0


@pytest.mark.anyio
async def test_get_delivery_candidate_user_ids_is_one_lightweight_ordered_query(
    db_session: AsyncSession,
    db_engine,
):
    queued_user = make_user("enabled_queue")
    empty_user = make_user("enabled_empty")
    inactive_user = make_user("inactive", active=False)
    disabled_user = make_user("disabled")
    db_session.add_all([queued_user, empty_user, inactive_user, disabled_user])
    await db_session.flush()
    queued_word = (await add_words(db_session, queued_user.id, "ett"))[0]
    repository = RecallRepository(db_session)
    for user in (queued_user, empty_user, inactive_user):
        await repository.upsert_for_user(user.id, chat_id=user.id, is_enabled=True)
    await repository.upsert_for_user(disabled_user.id, chat_id=disabled_user.id, is_enabled=False)
    await repository.replace_queue(queued_user.id, as_queue_entries([queued_word]))
    await db_session.commit()

    select_count = 0

    def count_selects(_conn, _cursor, statement: str, _parameters, _context, _executemany) -> None:
        nonlocal select_count
        if statement.lstrip().upper().startswith("SELECT"):
            select_count += 1

    event.listen(db_engine.sync_engine, "before_cursor_execute", count_selects)
    try:
        user_ids = await repository.get_delivery_candidate_user_ids(now=datetime(2026, 1, 15, 12, tzinfo=timezone.utc))
    finally:
        event.remove(db_engine.sync_engine, "before_cursor_execute", count_selects)

    assert user_ids == [queued_user.id, empty_user.id]
    assert select_count == 1


@pytest.mark.anyio
async def test_get_delivery_state_for_update_defers_queue_loading(db_session: AsyncSession, db_engine):
    user = make_user("deferred_state")
    db_session.add(user)
    await db_session.flush()
    word = (await add_words(db_session, user.id, "ett"))[0]
    repository = RecallRepository(db_session)
    await repository.upsert_for_user(user.id, chat_id=123, is_enabled=True)
    await repository.replace_queue(user.id, as_queue_entries([word]), next_word_index=1)
    await db_session.commit()

    select_count = 0

    def count_selects(_conn, _cursor, statement: str, _parameters, _context, _executemany) -> None:
        nonlocal select_count
        if statement.lstrip().upper().startswith("SELECT"):
            select_count += 1

    event.listen(db_engine.sync_engine, "before_cursor_execute", count_selects)
    try:
        state = await repository.get_delivery_state_for_update(user.id)
    finally:
        event.remove(db_engine.sync_engine, "before_cursor_execute", count_selects)

    assert state is not None
    assert state.telegram_chat_id == 123
    assert state.next_word_index == 1
    assert state.daily_selection == []
    assert select_count == 1


@pytest.mark.anyio
async def test_load_locked_recall_queue_loads_ordered_words_into_deferred_state(db_session: AsyncSession):
    user = make_user("deferred_queue")
    db_session.add(user)
    await db_session.flush()
    first, second = await add_words(db_session, user.id, "ett", "tva")
    repository = RecallRepository(db_session)
    await repository.upsert_for_user(user.id, chat_id=123, is_enabled=True)
    await repository.replace_queue(user.id, as_queue_entries([second, first]), next_word_index=1)
    await db_session.commit()

    delivery_state = await repository.get_delivery_state_for_update(user.id)
    assert delivery_state is not None
    loaded_state = await repository.load_locked_recall_queue(delivery_state)

    assert loaded_state.telegram_chat_id == delivery_state.telegram_chat_id
    assert loaded_state.is_enabled is delivery_state.is_enabled
    assert loaded_state.next_word_index == delivery_state.next_word_index
    assert [word.id for word in loaded_state.daily_selection] == [second.id, first.id]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("timezone_name", "start_hour", "end_hour", "now", "eligible"),
    [
        ("UTC", 9, 22, datetime(2026, 1, 15, 9, tzinfo=timezone.utc), True),
        ("UTC", 9, 22, datetime(2026, 1, 15, 22, tzinfo=timezone.utc), False),
        ("UTC", 22, 7, datetime(2026, 1, 15, 22, tzinfo=timezone.utc), True),
        ("UTC", 22, 7, datetime(2026, 1, 16, 6, tzinfo=timezone.utc), True),
        ("UTC", 22, 7, datetime(2026, 1, 16, 7, tzinfo=timezone.utc), False),
        ("Europe/Helsinki", 11, 12, datetime(2026, 1, 15, 9, tzinfo=timezone.utc), True),
        ("Europe/Helsinki", 3, 4, datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc), False),
        ("Europe/Helsinki", 3, 4, datetime(2026, 3, 29, 1, 30, tzinfo=timezone.utc), False),
        ("Europe/Helsinki", 3, 4, datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc), True),
        ("Europe/Helsinki", 3, 4, datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc), True),
        ("America/New_York", 4, 5, datetime(2026, 1, 15, 9, tzinfo=timezone.utc), True),
    ],
)
async def test_get_delivery_candidate_user_ids_evaluates_local_delivery_window(
    db_session: AsyncSession,
    timezone_name: str,
    start_hour: int,
    end_hour: int,
    now: datetime,
    eligible: bool,
):
    user = make_user("window", timezone_name=timezone_name)
    db_session.add(user)
    await db_session.flush()
    repository = RecallRepository(db_session)
    await repository.upsert_for_user(user.id, chat_id=123, is_enabled=True)
    state = await repository.get_recall_state_for_update(user.id)
    assert state is not None
    await repository.update_locked_delivery_settings(state, start_hour, end_hour, True)

    user_ids = await repository.get_delivery_candidate_user_ids(now=now)

    assert (user.id in user_ids) is eligible


@pytest.mark.anyio
async def test_get_delivery_candidate_user_ids_ignores_corrupt_timezone_without_blocking_valid_users(
    db_session: AsyncSession,
):
    valid_user = make_user("valid_timezone")
    corrupt_user = make_user("corrupt_timezone", timezone_name="Europe/Not_A_Zone")
    db_session.add_all([valid_user, corrupt_user])
    await db_session.flush()
    repository = RecallRepository(db_session)
    await repository.upsert_for_user(valid_user.id, chat_id=123, is_enabled=True)
    await repository.upsert_for_user(corrupt_user.id, chat_id=456, is_enabled=True)

    user_ids = await repository.get_delivery_candidate_user_ids(now=datetime(2026, 1, 15, 12, tzinfo=timezone.utc))

    assert user_ids == [valid_user.id]


@pytest.mark.anyio
async def test_update_locked_delivery_settings_preserves_linkage_queue_and_cursor(db_session: AsyncSession):
    user = make_user("settings")
    db_session.add(user)
    await db_session.flush()
    word = (await add_words(db_session, user.id, "natt"))[0]
    repository = RecallRepository(db_session)
    await repository.upsert_for_user(user.id, chat_id=321, is_enabled=True)
    await repository.replace_queue(user.id, as_queue_entries([word]), next_word_index=4)
    locked = await repository.get_recall_state_for_update(user.id)
    assert locked is not None

    updated = await repository.update_locked_delivery_settings(locked, 23, 7, False)

    assert updated.telegram_chat_id == 321
    assert updated.is_enabled is False
    assert updated.recall_start_hour == 23
    assert updated.recall_end_hour == 7
    assert updated.next_word_index == 4
    assert [entry.id for entry in updated.daily_selection] == [word.id]
    persisted = await repository.get_recall_state(user.id)
    assert persisted == updated


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("start_hour", "end_hour"),
    [(-1, 22), (24, 22), (9, -1), (9, 24), (9, 9)],
)
async def test_recall_schedule_constraints_reject_invalid_hours(
    db_session: AsyncSession,
    start_hour: int,
    end_hour: int,
):
    user = make_user(f"invalid_hours_{start_hour}_{end_hour}")
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        RecallUserStateDB(
            user_id=user.id,
            telegram_chat_id=123,
            is_enabled=True,
            recall_start_hour=start_hour,
            recall_end_hour=end_hour,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_queue_constraints_reject_duplicate_vocabulary(db_session: AsyncSession):
    user = make_user("constraint")
    db_session.add(user)
    await db_session.flush()
    word = (await add_words(db_session, user.id, "ett"))[0]
    repository = RecallRepository(db_session)
    await repository.upsert_for_user(user.id, chat_id=123, is_enabled=True)
    db_session.add_all(
        [
            RecallQueueItemDB(user_id=user.id, vocabulary_id=word.id, position=0),
            RecallQueueItemDB(user_id=user.id, vocabulary_id=word.id, position=1),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.anyio
async def test_queue_constraints_require_vocabulary_owned_by_same_user(db_session: AsyncSession):
    queue_owner = make_user("queue_owner")
    other_user = make_user("word_owner")
    db_session.add_all([queue_owner, other_user])
    await db_session.flush()
    own_word = (await add_words(db_session, queue_owner.id, "egen"))[0]
    other_word = (await add_words(db_session, other_user.id, "annan"))[0]
    repository = RecallRepository(db_session)
    await repository.upsert_for_user(queue_owner.id, chat_id=123, is_enabled=True)

    db_session.add(RecallQueueItemDB(user_id=queue_owner.id, vocabulary_id=own_word.id, position=0))
    await db_session.flush()

    db_session.add(RecallQueueItemDB(user_id=queue_owner.id, vocabulary_id=other_word.id, position=1))
    with pytest.raises(IntegrityError):
        await db_session.flush()


def test_recall_foreign_keys_have_explicit_stable_names():
    constraints_by_table: dict[str, set[str | None]] = {}
    for table in (RecallUserStateDB.__table__, RecallQueueItemDB.__table__):
        constraints_by_table[table.name] = {constraint.name for constraint in table.foreign_key_constraints}

    assert constraints_by_table == {
        "recall_user_states": {"fk_recall_user_states_user_id_users"},
        "recall_queue_items": {
            "fk_recall_queue_items_user_id_recall_user_states",
            "fk_recall_queue_items_user_vocabulary_vocabulary",
        },
    }
