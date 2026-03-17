from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from runestone.agents.schemas import TeacherSideEffect
from runestone.db.agent_side_effect_repository import AgentSideEffectRepository
from runestone.services.agent_side_effect_service import AgentSideEffectService


@pytest.fixture
def mock_side_effect_repository():
    repository = MagicMock(spec=AgentSideEffectRepository)
    repository.get_recent_for_teacher = AsyncMock(return_value=[])
    repository.delete_for_chat_phase = AsyncMock(return_value=0)
    repository.add_many = AsyncMock(return_value=[])
    repository.deserialize_artifacts.return_value = {}
    return repository


@pytest.mark.anyio
async def test_load_recent_for_teacher_deserializes_records(mock_side_effect_repository):
    service = AgentSideEffectService(mock_side_effect_repository)
    mock_side_effect_repository.get_recent_for_teacher.return_value = [
        MagicMock(
            specialist_name="word_keeper",
            phase="post_response",
            status="action_taken",
            info_for_teacher="Saved 2 vocabulary items.",
            artifacts_json='{"saved_words":["ord","fras"]}',
            routing_reason="save request",
            latency_ms=12,
            created_at=datetime(2026, 3, 16, 10, 0, tzinfo=timezone.utc),
        )
    ]
    mock_side_effect_repository.deserialize_artifacts.return_value = {"saved_words": ["ord", "fras"]}

    result = await service.load_recent_for_teacher(user_id=1, chat_id="chat-1")

    assert result == [
        TeacherSideEffect(
            name="word_keeper",
            phase="post_response",
            status="action_taken",
            info_for_teacher="Saved 2 vocabulary items.",
            artifacts={"saved_words": ["ord", "fras"]},
            routing_reason="save request",
            latency_ms=12,
            created_at=datetime(2026, 3, 16, 10, 0, tzinfo=timezone.utc),
        )
    ]


@pytest.mark.anyio
async def test_replace_post_response_side_effects_cleans_previous_turn(mock_side_effect_repository):
    service = AgentSideEffectService(mock_side_effect_repository)

    await service.replace_post_response_side_effects(
        user_id=1,
        chat_id="chat-1",
        results=[
            {
                "name": "word_keeper",
                "routing_reason": "save words",
                "latency_ms": 12,
                "result": {
                    "status": "action_taken",
                    "info_for_teacher": "Saved 2 vocabulary items.",
                    "artifacts": {"saved_words": ["ord", "fras"]},
                },
            }
        ],
    )

    mock_side_effect_repository.delete_for_chat_phase.assert_awaited_once_with(
        user_id=1,
        chat_id="chat-1",
        phase="post_response",
    )
    mock_side_effect_repository.add_many.assert_awaited_once_with(
        user_id=1,
        chat_id="chat-1",
        records=[
            {
                "specialist_name": "word_keeper",
                "phase": "post_response",
                "status": "action_taken",
                "info_for_teacher": "Saved 2 vocabulary items.",
                "artifacts": {"saved_words": ["ord", "fras"]},
                "routing_reason": "save words",
                "latency_ms": 12,
            }
        ],
    )


@pytest.mark.anyio
async def test_replace_post_response_side_effects_still_cleans_when_no_results(mock_side_effect_repository):
    service = AgentSideEffectService(mock_side_effect_repository)

    await service.replace_post_response_side_effects(user_id=1, chat_id="chat-1", results=[])

    mock_side_effect_repository.delete_for_chat_phase.assert_awaited_once()
    mock_side_effect_repository.add_many.assert_not_called()
