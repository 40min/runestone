from uuid import uuid4

import pytest

from runestone.db.agent_side_effect_repository import AgentSideEffectRepository


@pytest.fixture
def side_effect_repository(db_session):
    return AgentSideEffectRepository(db_session)


async def test_add_many_and_round_trip(side_effect_repository, db_with_test_user):
    _db, user = db_with_test_user
    chat_id = str(uuid4())

    await side_effect_repository.add_many(
        user_id=user.id,
        chat_id=chat_id,
        records=[
            {
                "specialist_name": "word_keeper",
                "phase": "post_response",
                "status": "action_taken",
                "info_for_teacher": "Saved 2 vocabulary items.",
                "artifacts": {"saved_words": ["ord", "fras"]},
                "routing_reason": "save request",
                "latency_ms": 11,
            }
        ],
    )

    records = await side_effect_repository.get_recent_for_teacher(user.id, chat_id)
    assert len(records) == 1
    assert records[0].specialist_name == "word_keeper"
    assert side_effect_repository.deserialize_artifacts(records[0].artifacts_json) == {"saved_words": ["ord", "fras"]}


async def test_get_recent_for_teacher_is_chat_scoped(side_effect_repository, db_with_test_user):
    _db, user = db_with_test_user
    target_chat_id = str(uuid4())
    other_chat_id = str(uuid4())

    await side_effect_repository.add_many(
        user_id=user.id,
        chat_id=other_chat_id,
        records=[
            {
                "specialist_name": "word_keeper",
                "phase": "post_response",
                "status": "action_taken",
                "info_for_teacher": "Wrong chat",
                "artifacts": {},
            }
        ],
    )
    await side_effect_repository.add_many(
        user_id=user.id,
        chat_id=target_chat_id,
        records=[
            {
                "specialist_name": "word_keeper",
                "phase": "post_response",
                "status": "action_taken",
                "info_for_teacher": "Right chat",
                "artifacts": {},
            }
        ],
    )

    records = await side_effect_repository.get_recent_for_teacher(user.id, target_chat_id)
    assert [record.info_for_teacher for record in records] == ["Right chat"]


async def test_get_recent_for_teacher_excludes_coordinator_rows(side_effect_repository, db_with_test_user):
    _db, user = db_with_test_user
    chat_id = str(uuid4())

    await side_effect_repository.create_coordinator_row(user_id=user.id, chat_id=chat_id, status="done")
    await side_effect_repository.add_many(
        user_id=user.id,
        chat_id=chat_id,
        records=[
            {
                "specialist_name": "word_keeper",
                "phase": "post_response",
                "status": "action_taken",
                "info_for_teacher": "Keep this word.",
                "artifacts": {},
            }
        ],
    )

    records = await side_effect_repository.get_recent_for_teacher(user.id, chat_id)

    assert [record.specialist_name for record in records] == ["word_keeper"]


async def test_get_recent_for_teacher_orders_oldest_to_newest(side_effect_repository, db_with_test_user):
    _db, user = db_with_test_user
    chat_id = str(uuid4())

    await side_effect_repository.add_many(
        user_id=user.id,
        chat_id=chat_id,
        records=[
            {
                "specialist_name": "word_keeper",
                "phase": "post_response",
                "status": "action_taken",
                "info_for_teacher": "First save",
                "artifacts": {},
            },
            {
                "specialist_name": "word_keeper",
                "phase": "post_response",
                "status": "action_taken",
                "info_for_teacher": "Second save",
                "artifacts": {},
            },
        ],
    )

    records = await side_effect_repository.get_recent_for_teacher(user.id, chat_id, limit=2)
    assert [record.info_for_teacher for record in records] == ["First save", "Second save"]


async def test_add_many_without_commit_flushes_for_later_commit(side_effect_repository, db_with_test_user):
    db, user = db_with_test_user
    chat_id = str(uuid4())

    created = await side_effect_repository.add_many(
        user_id=user.id,
        chat_id=chat_id,
        records=[
            {
                "specialist_name": "word_keeper",
                "phase": "post_response",
                "status": "action_taken",
                "info_for_teacher": "Deferred commit",
                "artifacts": {"saved_words": ["fika"]},
            }
        ],
        commit=False,
    )
    await db.commit()

    assert len(created) == 1
    assert created[0].id is not None

    records = await side_effect_repository.get_recent_for_teacher(user.id, chat_id)
    assert [record.info_for_teacher for record in records] == ["Deferred commit"]


async def test_create_coordinator_row_persists_tracking_record(side_effect_repository, db_with_test_user):
    _db, user = db_with_test_user
    chat_id = str(uuid4())

    row = await side_effect_repository.create_coordinator_row(user_id=user.id, chat_id=chat_id, status="pending")

    assert row.id is not None
    assert row.specialist_name == "coordinator"
    assert row.phase == "post_response"
    assert row.status == "pending"


async def test_update_coordinator_status_updates_existing_row(side_effect_repository, db_with_test_user):
    _db, user = db_with_test_user
    chat_id = str(uuid4())
    row = await side_effect_repository.create_coordinator_row(user_id=user.id, chat_id=chat_id, status="pending")

    await side_effect_repository.update_coordinator_status(row_id=row.id, status="done")

    latest = await side_effect_repository.get_latest_coordinator_row(user.id, chat_id)
    assert latest is not None
    assert latest.id == row.id
    assert latest.status == "done"


async def test_get_latest_coordinator_row_returns_newest_row(side_effect_repository, db_with_test_user):
    _db, user = db_with_test_user
    chat_id = str(uuid4())
    first = await side_effect_repository.create_coordinator_row(user_id=user.id, chat_id=chat_id, status="pending")
    second = await side_effect_repository.create_coordinator_row(user_id=user.id, chat_id=chat_id, status="running")

    latest = await side_effect_repository.get_latest_coordinator_row(user.id, chat_id)

    assert latest is not None
    assert latest.id == second.id
    assert latest.id != first.id


async def test_delete_coordinator_rows_removes_only_tracking_records(side_effect_repository, db_with_test_user):
    _db, user = db_with_test_user
    chat_id = str(uuid4())
    await side_effect_repository.create_coordinator_row(user_id=user.id, chat_id=chat_id, status="pending")
    await side_effect_repository.add_many(
        user_id=user.id,
        chat_id=chat_id,
        records=[
            {
                "specialist_name": "word_keeper",
                "phase": "post_response",
                "status": "action_taken",
                "info_for_teacher": "Saved 1 word.",
                "artifacts": {},
            }
        ],
    )

    deleted = await side_effect_repository.delete_coordinator_rows(user_id=user.id, chat_id=chat_id)

    assert deleted == 1
    latest = await side_effect_repository.get_latest_coordinator_row(user.id, chat_id)
    assert latest is None
    records = await side_effect_repository.get_recent_for_teacher(user.id, chat_id)
    assert [record.specialist_name for record in records] == ["word_keeper"]
