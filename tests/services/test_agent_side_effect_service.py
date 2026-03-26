from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from runestone.agents.schemas import CoordinatorRow, TeacherSideEffect
from runestone.db.agent_side_effect_repository import AgentSideEffectRepository
from runestone.services.agent_side_effect_service import AgentSideEffectService


@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=AgentSideEffectRepository)
    repo.get_recent_for_teacher = AsyncMock(return_value=[])
    repo.delete_for_chat_phase = AsyncMock(return_value=0)
    repo.delete_coordinator_rows = AsyncMock(return_value=0)
    repo.add_many = AsyncMock(return_value=[])
    repo.create_coordinator_row = AsyncMock()
    repo.update_coordinator_status = AsyncMock()
    repo.get_latest_coordinator_row = AsyncMock(return_value=None)
    repo.db = MagicMock()
    repo.db.commit = AsyncMock()
    repo.db.rollback = AsyncMock()
    repo.deserialize_artifacts.return_value = {}
    return repo


# ---------------------------------------------------------------------------
# load_recent_for_teacher
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_load_recent_for_teacher_deserializes_records(mock_repo):
    service = AgentSideEffectService(mock_repo)
    mock_repo.get_recent_for_teacher.return_value = [
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
    mock_repo.deserialize_artifacts.return_value = {"saved_words": ["ord", "fras"]}

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
async def test_load_recent_for_teacher_returns_empty_list_on_error(mock_repo):
    service = AgentSideEffectService(mock_repo)
    mock_repo.get_recent_for_teacher.side_effect = RuntimeError("db error")

    result = await service.load_recent_for_teacher(user_id=1, chat_id="chat-1")

    assert result == []


# ---------------------------------------------------------------------------
# replace_post_specialist_results (formerly replace_post_response_side_effects)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_replace_post_specialist_results_deletes_then_inserts(mock_repo):
    service = AgentSideEffectService(mock_repo)
    latest = MagicMock()
    latest.id = 99
    mock_repo.get_latest_coordinator_row.return_value = latest

    result = await service.replace_post_specialist_results(
        user_id=1,
        chat_id="chat-1",
        coordinator_row_id=99,
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

    assert result is True
    mock_repo.delete_for_chat_phase.assert_awaited_once_with(
        user_id=1,
        chat_id="chat-1",
        phase="post_response",
        commit=False,
    )
    mock_repo.add_many.assert_awaited_once_with(
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
        commit=False,
    )
    mock_repo.db.commit.assert_awaited_once()
    mock_repo.db.rollback.assert_not_called()


@pytest.mark.anyio
async def test_replace_post_specialist_results_still_deletes_when_no_results(mock_repo):
    service = AgentSideEffectService(mock_repo)
    latest = MagicMock()
    latest.id = 99
    mock_repo.get_latest_coordinator_row.return_value = latest

    result = await service.replace_post_specialist_results(
        user_id=1, chat_id="chat-1", coordinator_row_id=99, results=[]
    )

    assert result is True
    mock_repo.delete_for_chat_phase.assert_awaited_once_with(
        user_id=1, chat_id="chat-1", phase="post_response", commit=False
    )
    mock_repo.add_many.assert_not_called()
    mock_repo.db.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_replace_post_specialist_results_rolls_back_on_failure(mock_repo):
    service = AgentSideEffectService(mock_repo)
    latest = MagicMock()
    latest.id = 99
    mock_repo.get_latest_coordinator_row.return_value = latest
    mock_repo.add_many.side_effect = RuntimeError("insert failed")

    with pytest.raises(RuntimeError, match="insert failed"):
        await service.replace_post_specialist_results(
            user_id=1,
            chat_id="chat-1",
            coordinator_row_id=99,
            results=[
                {
                    "name": "word_keeper",
                    "routing_reason": "save words",
                    "latency_ms": 12,
                    "result": {
                        "status": "action_taken",
                        "info_for_teacher": "Saved.",
                        "artifacts": {},
                    },
                }
            ],
        )

    mock_repo.db.rollback.assert_awaited_once()
    mock_repo.db.commit.assert_not_called()


@pytest.mark.anyio
async def test_replace_post_specialist_results_skips_stale_write(mock_repo):
    service = AgentSideEffectService(mock_repo)
    latest = MagicMock()
    latest.id = 100
    mock_repo.get_latest_coordinator_row.return_value = latest

    result = await service.replace_post_specialist_results(
        user_id=1,
        chat_id="chat-1",
        coordinator_row_id=99,
        results=[],
    )

    assert result is False
    mock_repo.delete_for_chat_phase.assert_not_called()
    mock_repo.add_many.assert_not_called()
    mock_repo.db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Coordinator row lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_post_coordinator_row_cleans_up_old_then_creates(mock_repo):
    service = AgentSideEffectService(mock_repo)
    created_row = MagicMock()
    created_row.id = 99
    mock_repo.create_coordinator_row.return_value = created_row

    row_id = await service.create_post_coordinator_row(user_id=1, chat_id="chat-1")

    mock_repo.delete_coordinator_rows.assert_awaited_once_with(user_id=1, chat_id="chat-1", commit=False)
    mock_repo.create_coordinator_row.assert_awaited_once_with(user_id=1, chat_id="chat-1", status="pending")
    assert row_id == 99


@pytest.mark.anyio
async def test_mark_coordinator_running_calls_update(mock_repo):
    service = AgentSideEffectService(mock_repo)
    await service.mark_coordinator_running(42)
    mock_repo.update_coordinator_status.assert_awaited_once_with(row_id=42, status="running")


@pytest.mark.anyio
async def test_mark_coordinator_done_calls_update(mock_repo):
    service = AgentSideEffectService(mock_repo)
    await service.mark_coordinator_done(42)
    mock_repo.update_coordinator_status.assert_awaited_once_with(row_id=42, status="done")


@pytest.mark.anyio
async def test_mark_coordinator_failed_calls_update(mock_repo):
    service = AgentSideEffectService(mock_repo)
    await service.mark_coordinator_failed(42)
    mock_repo.update_coordinator_status.assert_awaited_once_with(row_id=42, status="failed")


@pytest.mark.anyio
async def test_mark_coordinator_done_if_current_updates_only_latest_row(mock_repo):
    service = AgentSideEffectService(mock_repo)
    latest = MagicMock()
    latest.id = 42
    mock_repo.get_latest_coordinator_row.return_value = latest

    result = await service.mark_coordinator_done_if_current(row_id=42, user_id=1, chat_id="chat-1")

    assert result is True
    mock_repo.update_coordinator_status.assert_awaited_once_with(row_id=42, status="done")


@pytest.mark.anyio
async def test_mark_coordinator_done_if_current_skips_stale_row(mock_repo):
    service = AgentSideEffectService(mock_repo)
    latest = MagicMock()
    latest.id = 43
    mock_repo.get_latest_coordinator_row.return_value = latest

    result = await service.mark_coordinator_done_if_current(row_id=42, user_id=1, chat_id="chat-1")

    assert result is False
    mock_repo.update_coordinator_status.assert_not_called()


@pytest.mark.anyio
async def test_mark_coordinator_failed_if_current_skips_stale_row(mock_repo):
    service = AgentSideEffectService(mock_repo)
    latest = MagicMock()
    latest.id = 43
    mock_repo.get_latest_coordinator_row.return_value = latest

    result = await service.mark_coordinator_failed_if_current(row_id=42, user_id=1, chat_id="chat-1")

    assert result is False
    mock_repo.update_coordinator_status.assert_not_called()


@pytest.mark.anyio
async def test_load_latest_coordinator_row_returns_none_when_not_found(mock_repo):
    service = AgentSideEffectService(mock_repo)
    mock_repo.get_latest_coordinator_row.return_value = None

    result = await service.load_latest_coordinator_row(user_id=1, chat_id="chat-1")

    assert result is None


@pytest.mark.anyio
async def test_load_latest_coordinator_row_deserializes_record(mock_repo):
    service = AgentSideEffectService(mock_repo)
    record = MagicMock()
    record.id = 42
    record.specialist_name = "coordinator"
    record.phase = "post_response"
    record.status = "pending"
    record.info_for_teacher = ""
    record.artifacts_json = None
    record.routing_reason = ""
    record.latency_ms = None
    record.created_at = None
    mock_repo.get_latest_coordinator_row.return_value = record
    mock_repo.deserialize_artifacts.return_value = {}

    result = await service.load_latest_coordinator_row(user_id=1, chat_id="chat-1")

    assert result == CoordinatorRow(id=42, status="pending", created_at=None)


@pytest.mark.anyio
async def test_load_latest_coordinator_row_returns_none_on_error(mock_repo):
    service = AgentSideEffectService(mock_repo)
    mock_repo.get_latest_coordinator_row.side_effect = RuntimeError("db error")

    result = await service.load_latest_coordinator_row(user_id=1, chat_id="chat-1")

    assert result is None
