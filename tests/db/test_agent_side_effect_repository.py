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
