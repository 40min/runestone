"""
Tests for AgentsManager orchestration.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from runestone.agents.manager import AgentsManager
from runestone.agents.schemas import ChatMessage, CoordinatorPlan, RoutingItem, TeacherSideEffect
from runestone.agents.specialists.base import BaseSpecialist, SpecialistContext, SpecialistResult
from runestone.config import AgentLLMSettings, ReasoningLevel, Settings
from runestone.services.agent_side_effect_service import AgentSideEffectService


@pytest.fixture
def mock_settings():
    settings = MagicMock(spec=Settings)
    settings.teacher_provider = "openrouter"
    settings.teacher_model = "test-model"
    settings.coordinator_model = "test-coordinator-model"
    settings.coordinator_provider = "openrouter"
    settings.word_keeper_provider = "openrouter"
    settings.word_keeper_model = "test-model"
    settings.agent_persona = "default"
    settings.openrouter_api_key = "test-api-key"
    settings.openai_api_key = "test-openai-key"
    settings.allowed_origins = "http://localhost:5173"
    settings.get_agent_llm_settings.side_effect = lambda agent_name: {
        "teacher": AgentLLMSettings(
            provider="openrouter",
            model="test-model",
            temperature=1.0,
            reasoning_level=ReasoningLevel.NONE,
        ),
        "coordinator": AgentLLMSettings(
            provider="openrouter",
            model="test-coordinator-model",
            temperature=0.0,
            reasoning_level=ReasoningLevel.NONE,
        ),
        "word_keeper": AgentLLMSettings(
            provider="openrouter",
            model="test-model",
            temperature=0.0,
            reasoning_level=ReasoningLevel.NONE,
        ),
    }[agent_name]
    return settings


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    user.mother_tongue = None
    return user


@pytest.fixture
def mock_memory_item_service():
    return AsyncMock()


@pytest.fixture
def mock_side_effect_service():
    service = MagicMock(spec=AgentSideEffectService)
    service.load_recent_for_teacher = AsyncMock(return_value=[])
    service.create_post_coordinator_row = AsyncMock(return_value=42)
    service.replace_post_specialist_results = AsyncMock(return_value=True)
    service.mark_coordinator_running = AsyncMock(return_value=None)
    service.mark_coordinator_done = AsyncMock(return_value=None)
    service.mark_coordinator_failed = AsyncMock(return_value=None)
    service.mark_coordinator_done_if_current = AsyncMock(return_value=True)
    service.mark_coordinator_failed_if_current = AsyncMock(return_value=True)
    return service


def _make_plan(pre=None, post=None):
    return CoordinatorPlan(pre_response=pre or [], post_response=post or [], audit={})


# ---------------------------------------------------------------------------
# process_turn tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_process_turn_returns_teacher_reply_and_starts_background_post(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.handle_stale_post_task = AsyncMock()
    manager.prepare_pre_turn = AsyncMock(return_value=(_make_plan(), [{"name": "pre"}], []))
    manager.generate_teacher_response = AsyncMock(return_value=("Teacher says hi", [{"title": "Src"}]))
    manager.start_background_post_turn = AsyncMock()

    response, sources = await manager.process_turn(
        message="Hello",
        chat_id="chat-1",
        history=[ChatMessage(role="assistant", content="Earlier")],
        user=mock_user,
        memory_item_service=mock_memory_item_service,
        side_effect_service=mock_side_effect_service,
    )

    assert response == "Teacher says hi"
    assert sources == [{"title": "Src"}]
    manager.handle_stale_post_task.assert_awaited_once_with(
        user_id=mock_user.id,
        chat_id="chat-1",
        side_effect_service=mock_side_effect_service,
    )
    mock_side_effect_service.create_post_coordinator_row.assert_awaited_once_with(
        user_id=mock_user.id,
        chat_id="chat-1",
    )
    manager.start_background_post_turn.assert_awaited_once_with(
        message="Hello",
        chat_id="chat-1",
        history=[ChatMessage(role="assistant", content="Earlier")],
        user=mock_user,
        teacher_response="Teacher says hi",
        pre_results=[{"name": "pre"}],
        side_effect_service=mock_side_effect_service,
        coordinator_row_id=42,
    )


@pytest.mark.anyio
async def test_process_turn_skips_stale_check_on_first_turn(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.handle_stale_post_task = AsyncMock()
    manager.prepare_pre_turn = AsyncMock(return_value=(_make_plan(), [], []))
    manager.generate_teacher_response = AsyncMock(return_value=("Teacher says hi", None))
    manager.start_background_post_turn = AsyncMock()

    await manager.process_turn(
        message="Hello",
        chat_id="chat-1",
        history=[],
        user=mock_user,
        memory_item_service=mock_memory_item_service,
        side_effect_service=mock_side_effect_service,
    )

    manager.handle_stale_post_task.assert_not_awaited()


# ---------------------------------------------------------------------------
# prepare_pre_turn tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_prepare_pre_turn_delegates_to_coordinator(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan_pre_turn = AsyncMock(return_value=_make_plan())
    manager.teacher = AsyncMock()

    plan, pre_results, recent_effects = await manager.prepare_pre_turn(
        message="Hello",
        chat_id="chat-1",
        history=[],
        user=mock_user,
        memory_item_service=mock_memory_item_service,
        side_effect_service=mock_side_effect_service,
    )

    manager.coordinator.plan_pre_turn.assert_awaited_once()
    assert pre_results == []
    assert recent_effects is not None


@pytest.mark.anyio
async def test_prepare_pre_turn_runs_cleanup_on_first_turn(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan_pre_turn = AsyncMock(return_value=_make_plan())
    manager.teacher = AsyncMock()

    await manager.prepare_pre_turn(
        message="Hello",
        chat_id="chat-1",
        history=[],
        user=mock_user,
        memory_item_service=mock_memory_item_service,
        side_effect_service=mock_side_effect_service,
    )

    mock_memory_item_service.cleanup_old_mastered_areas.assert_called_once_with(mock_user.id, older_than_days=90)


@pytest.mark.anyio
async def test_prepare_pre_turn_skips_cleanup_with_history(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan_pre_turn = AsyncMock(return_value=_make_plan())
    manager.teacher = AsyncMock()

    await manager.prepare_pre_turn(
        message="Hello",
        chat_id="chat-1",
        history=[ChatMessage(role="user", content="prev")],
        user=mock_user,
        memory_item_service=mock_memory_item_service,
        side_effect_service=mock_side_effect_service,
    )

    mock_memory_item_service.cleanup_old_mastered_areas.assert_not_called()


@pytest.mark.anyio
async def test_coordinator_history_is_truncated(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan_pre_turn = AsyncMock(return_value=_make_plan())

    history = [ChatMessage(role="user", content=f"m{i}") for i in range(10)]
    await manager.prepare_pre_turn(
        message="Hello",
        chat_id="chat-1",
        history=history,
        user=mock_user,
        memory_item_service=mock_memory_item_service,
        side_effect_service=mock_side_effect_service,
    )

    _args, kwargs = manager.coordinator.plan_pre_turn.call_args
    assert len(kwargs["history"]) == manager.COORDINATOR_MAX_HISTORY_MESSAGES


@pytest.mark.anyio
async def test_coordinator_history_truncation_logs_warning(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service, caplog
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan_pre_turn = AsyncMock(return_value=_make_plan())

    history = [ChatMessage(role="user", content=f"m{i}") for i in range(10)]
    with caplog.at_level("WARNING"):
        await manager.prepare_pre_turn(
            message="Hello",
            chat_id="chat-1",
            history=history,
            user=mock_user,
            memory_item_service=mock_memory_item_service,
            side_effect_service=mock_side_effect_service,
        )

    assert "Truncated coordinator history" in caplog.text


# ---------------------------------------------------------------------------
# generate_teacher_response tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_generate_teacher_response_returns_text_and_sources(mock_settings, mock_user):
    manager = AgentsManager(mock_settings)
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = ("Hi there!", [])

    response, sources = await manager.generate_teacher_response(
        message="Hello",
        history=[],
        user=mock_user,
        pre_results=[],
        recent_side_effects=[],
    )

    assert response == "Hi there!"
    assert sources is None


@pytest.mark.anyio
async def test_generate_teacher_response_extracts_news_sources(mock_settings, mock_user):
    manager = AgentsManager(mock_settings)
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = (
        "Svar med källor",
        [
            ToolMessage(
                content=(
                    '{"tool":"search_news_with_dates","results":[{"title":"Nyhet","url":"https://example.com",'
                    '"date":"2026-02-05"}]}'
                ),
                tool_call_id="tool-call-1",
            ),
            AIMessage(content="Svar med källor"),
        ],
    )

    response, sources = await manager.generate_teacher_response(
        message="Nyheter",
        history=[],
        user=mock_user,
        pre_results=[],
        recent_side_effects=[],
    )

    assert response == "Svar med källor"
    assert sources == [{"title": "Nyhet", "url": "https://example.com", "date": "2026-02-05"}]


@pytest.mark.anyio
async def test_generate_teacher_response_filters_unsafe_urls(mock_settings, mock_user):
    manager = AgentsManager(mock_settings)
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = (
        "Svar",
        [
            ToolMessage(
                content=(
                    '{"tool":"search_news_with_dates","results":['
                    '{"title":"Safe","url":"https://example.com","date":"2026-02-05"},'
                    '{"title":"Unsafe","url":"javascript:alert(1)","date":"2026-02-05"}'
                    "]}"
                ),
                tool_call_id="tool-call-2",
            ),
        ],
    )

    _response, sources = await manager.generate_teacher_response(
        message="Nyheter", history=[], user=mock_user, pre_results=[], recent_side_effects=[]
    )

    assert sources == [{"title": "Safe", "url": "https://example.com", "date": "2026-02-05"}]


@pytest.mark.anyio
async def test_generate_teacher_response_does_not_cap_grammar_sources(mock_settings, mock_user):
    manager = AgentsManager(mock_settings)
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = (
        "Grammatik",
        [
            ToolMessage(
                content=(
                    '{"tool":"search_grammar","results":['
                    '{"title":"Doc 1","url":"https://example.com/1"},'
                    '{"title":"Doc 2","url":"https://example.com/2"},'
                    '{"title":"Doc 3","url":"https://example.com/3"},'
                    '{"title":"Doc 4","url":"https://example.com/4"},'
                    '{"title":"Doc 5","url":"https://example.com/5"}'
                    "]}"
                ),
                tool_call_id="tool-call-3",
            ),
        ],
    )

    _response, sources = await manager.generate_teacher_response(
        message="Grammatik", history=[], user=mock_user, pre_results=[], recent_side_effects=[]
    )

    assert sources == [
        {"title": "Doc 1", "url": "https://example.com/1", "date": ""},
        {"title": "Doc 2", "url": "https://example.com/2", "date": ""},
        {"title": "Doc 3", "url": "https://example.com/3", "date": ""},
        {"title": "Doc 4", "url": "https://example.com/4", "date": ""},
        {"title": "Doc 5", "url": "https://example.com/5", "date": ""},
    ]


@pytest.mark.anyio
async def test_generate_teacher_response_passes_pre_results(mock_settings, mock_user):
    manager = AgentsManager(mock_settings)
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = ("Hi!", [])

    pre_results = [{"name": "word_keeper", "result": {"status": "action_taken"}}]
    await manager.generate_teacher_response(
        message="Hello",
        history=[],
        user=mock_user,
        pre_results=pre_results,
        recent_side_effects=[],
    )

    _args, kwargs = manager.teacher.generate_response.call_args
    assert kwargs["pre_results"] == pre_results


# ---------------------------------------------------------------------------
# run_post_turn tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_run_post_turn_runs_post_specialists(mock_settings, mock_user, mock_side_effect_service):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan_post_turn = AsyncMock(
        return_value=_make_plan(post=[RoutingItem(name="word_keeper", reason="save words", chat_history_size=0)])
    )

    class _ActionSpecialist(BaseSpecialist):
        def __init__(self):
            super().__init__(name="word_keeper")

        async def run(self, context: SpecialistContext) -> SpecialistResult:
            return SpecialistResult(status="action_taken", info_for_teacher="Saved words.")

    manager.registry.register(_ActionSpecialist(), overwrite=True)

    await manager.run_post_turn(
        message="Hello",
        chat_id="chat-1",
        history=[],
        user=mock_user,
        teacher_response="Great words!",
        pre_results=[],
        side_effect_service=mock_side_effect_service,
        coordinator_row_id=99,
    )

    mock_side_effect_service.mark_coordinator_running.assert_awaited_once_with(99)
    mock_side_effect_service.replace_post_specialist_results.assert_awaited_once()
    kwargs = mock_side_effect_service.replace_post_specialist_results.call_args.kwargs
    assert kwargs["user_id"] == mock_user.id
    assert kwargs["chat_id"] == "chat-1"
    assert kwargs["coordinator_row_id"] == 99
    assert kwargs["results"][0]["name"] == "word_keeper"
    assert kwargs["results"][0]["result"]["status"] == "action_taken"
    manager.coordinator.plan_post_turn.assert_awaited_once()
    mock_side_effect_service.mark_coordinator_done_if_current.assert_awaited_once_with(
        row_id=99, user_id=mock_user.id, chat_id="chat-1"
    )


@pytest.mark.anyio
async def test_run_post_turn_marks_failed_on_exception(mock_settings, mock_user, mock_side_effect_service):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan_post_turn = AsyncMock(return_value=_make_plan())
    mock_side_effect_service.replace_post_specialist_results.side_effect = RuntimeError("db error")

    with pytest.raises(RuntimeError, match="db error"):
        await manager.run_post_turn(
            message="Hello",
            chat_id="chat-1",
            history=[],
            user=mock_user,
            teacher_response="Hi!",
            pre_results=[],
            side_effect_service=mock_side_effect_service,
            coordinator_row_id=99,
        )

    mock_side_effect_service.mark_coordinator_failed_if_current.assert_awaited_once_with(
        row_id=99, user_id=mock_user.id, chat_id="chat-1"
    )
    mock_side_effect_service.mark_coordinator_done_if_current.assert_not_awaited()


@pytest.mark.anyio
async def test_run_post_turn_skips_done_mark_when_persistence_is_stale(
    mock_settings, mock_user, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan_post_turn = AsyncMock(return_value=_make_plan())
    mock_side_effect_service.replace_post_specialist_results.return_value = False

    await manager.run_post_turn(
        message="Hello",
        chat_id="chat-1",
        history=[],
        user=mock_user,
        teacher_response="Hi!",
        pre_results=[],
        side_effect_service=mock_side_effect_service,
        coordinator_row_id=99,
    )

    mock_side_effect_service.mark_coordinator_done_if_current.assert_not_awaited()


@pytest.mark.anyio
async def test_handle_stale_post_task_cancels_live_task_and_marks_failed(mock_settings, mock_side_effect_service):
    manager = AgentsManager(mock_settings)
    stale_row = MagicMock()
    stale_row.status = "pending"
    stale_row.id = 456
    mock_side_effect_service.load_latest_coordinator_row.return_value = stale_row
    mock_side_effect_service.repository = AsyncMock()
    mock_side_effect_service.repository.get_latest_coordinator_row.return_value = stale_row
    manager.cancel_post_task = MagicMock(return_value=True)

    await manager.handle_stale_post_task(
        user_id=1,
        chat_id="chat-123",
        side_effect_service=mock_side_effect_service,
    )

    manager.cancel_post_task.assert_called_once_with("chat-123")
    mock_side_effect_service.mark_coordinator_failed.assert_awaited_once_with(456)


@pytest.mark.anyio
async def test_handle_stale_post_task_ignores_done_row(mock_settings, mock_side_effect_service):
    manager = AgentsManager(mock_settings)
    done_row = MagicMock()
    done_row.status = "done"
    mock_side_effect_service.load_latest_coordinator_row.return_value = done_row
    manager.cancel_post_task = MagicMock(return_value=False)

    await manager.handle_stale_post_task(
        user_id=1,
        chat_id="chat-123",
        side_effect_service=mock_side_effect_service,
    )

    manager.cancel_post_task.assert_not_called()
    mock_side_effect_service.mark_coordinator_failed.assert_not_awaited()


# ---------------------------------------------------------------------------
# Background task registry tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_register_and_cancel_post_task(mock_settings):
    manager = AgentsManager(mock_settings)

    async def dummy():
        await asyncio.sleep(10)

    task = asyncio.create_task(dummy())
    manager._register_post_task("chat-1", task)
    assert "chat-1" in manager._post_task_registry.tasks

    cancelled = manager.cancel_post_task("chat-1")
    assert cancelled is True
    assert "chat-1" not in manager._post_task_registry.tasks
    # Give the event loop a tick to process the cancellation
    await asyncio.sleep(0)
    assert task.cancelled()


def test_cancel_post_task_returns_false_when_no_task(mock_settings):
    manager = AgentsManager(mock_settings)
    assert manager.cancel_post_task("non-existent-chat") is False


def test_unregister_removes_task(mock_settings):
    manager = AgentsManager(mock_settings)
    task = MagicMock()
    manager._post_task_registry.tasks["chat-1"] = task
    manager._unregister_post_task("chat-1")
    assert "chat-1" not in manager._post_task_registry.tasks


def test_register_post_task_cancels_existing_live_task(mock_settings):
    manager = AgentsManager(mock_settings)
    old_task = MagicMock()
    old_task.done.return_value = False
    new_task = MagicMock()

    manager._post_task_registry.tasks["chat-1"] = old_task
    manager._register_post_task("chat-1", new_task)

    old_task.cancel.assert_called_once_with()
    assert manager._post_task_registry.tasks["chat-1"] is new_task


@pytest.mark.anyio
async def test_start_background_post_turn_creates_task(mock_settings, mock_user, mock_side_effect_service):
    manager = AgentsManager(mock_settings)
    manager.run_post_turn = AsyncMock()

    await manager.start_background_post_turn(
        message="Hello",
        chat_id="chat-1",
        history=[],
        user=mock_user,
        teacher_response="Hi!",
        pre_results=[],
        side_effect_service=mock_side_effect_service,
        coordinator_row_id=42,
    )

    # Allow the task to run
    await asyncio.sleep(0)

    manager.run_post_turn.assert_awaited_once()
    # Task should be cleaned up after completion
    await asyncio.sleep(0.05)
    assert "chat-1" not in manager._post_task_registry.tasks


@pytest.mark.anyio
async def test_start_background_post_turn_returns_before_slow_post_finishes(
    mock_settings, mock_user, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    gate = asyncio.Event()

    async def slow_post_turn(**_kwargs):
        await gate.wait()

    manager.run_post_turn = slow_post_turn

    await manager.start_background_post_turn(
        message="Hello",
        chat_id="chat-1",
        history=[],
        user=mock_user,
        teacher_response="Hi!",
        pre_results=[],
        side_effect_service=mock_side_effect_service,
        coordinator_row_id=42,
    )

    assert "chat-1" in manager._post_task_registry.tasks
    assert not manager._post_task_registry.tasks["chat-1"].done()

    gate.set()
    await asyncio.sleep(0.05)
    assert "chat-1" not in manager._post_task_registry.tasks


@pytest.mark.anyio
async def test_start_background_post_turn_marks_failed_on_timeout(mock_settings, mock_user, mock_side_effect_service):
    manager = AgentsManager(mock_settings)
    manager.POST_TASK_TIMEOUT_SECONDS = 0.01  # very short timeout

    async def slow_post_turn(**_kwargs):
        await asyncio.sleep(5)

    manager.run_post_turn = slow_post_turn

    await manager.start_background_post_turn(
        message="Hello",
        chat_id="chat-1",
        history=[],
        user=mock_user,
        teacher_response="Hi!",
        pre_results=[],
        side_effect_service=mock_side_effect_service,
        coordinator_row_id=42,
    )

    await asyncio.sleep(0.1)  # wait for timeout to fire

    mock_side_effect_service.mark_coordinator_failed_if_current.assert_awaited_once_with(
        row_id=42, user_id=mock_user.id, chat_id="chat-1"
    )
    assert "chat-1" not in manager._post_task_registry.tasks


# ---------------------------------------------------------------------------
# Specialist history window tests (use prepare_pre_turn)
# ---------------------------------------------------------------------------


class _CaptureHistorySpecialist(BaseSpecialist):
    def __init__(self):
        super().__init__(name="capture_history")
        self.seen_history = None

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        self.seen_history = context.history
        return SpecialistResult(status="no_action")


@pytest.mark.anyio
async def test_specialist_history_is_truncated(mock_settings, mock_user, mock_memory_item_service):
    manager = AgentsManager(mock_settings)
    capture = _CaptureHistorySpecialist()
    manager.registry.register(capture)
    manager.coordinator.plan_pre_turn = AsyncMock(
        return_value=_make_plan(pre=[RoutingItem(name="capture_history", reason="test", chat_history_size=1)])
    )

    side_effect_service = MagicMock(spec=AgentSideEffectService)
    side_effect_service.load_recent_for_teacher = AsyncMock(return_value=[])

    history = [
        ChatMessage(role="user", content="m1"),
        ChatMessage(role="assistant", content="m2"),
        ChatMessage(role="user", content="m3"),
    ]
    await manager.prepare_pre_turn(
        message="Hello",
        chat_id="chat-1",
        history=history,
        user=mock_user,
        memory_item_service=mock_memory_item_service,
        side_effect_service=side_effect_service,
    )

    assert capture.seen_history is not None
    assert len(capture.seen_history) == 1
    assert capture.seen_history[0].content == "m3"


@pytest.mark.anyio
async def test_specialist_history_truncation_logs_warning(mock_settings, mock_user, mock_memory_item_service, caplog):
    manager = AgentsManager(mock_settings)
    capture = _CaptureHistorySpecialist()
    manager.registry.register(capture)
    manager.coordinator.plan_pre_turn = AsyncMock(
        return_value=_make_plan(pre=[RoutingItem(name="capture_history", reason="test", chat_history_size=1)])
    )

    side_effect_service = MagicMock(spec=AgentSideEffectService)
    side_effect_service.load_recent_for_teacher = AsyncMock(return_value=[])

    history = [
        ChatMessage(role="user", content="m1"),
        ChatMessage(role="assistant", content="m2"),
        ChatMessage(role="user", content="m3"),
    ]
    with caplog.at_level("WARNING"):
        await manager.prepare_pre_turn(
            message="Hello",
            chat_id="chat-1",
            history=history,
            user=mock_user,
            memory_item_service=mock_memory_item_service,
            side_effect_service=side_effect_service,
        )

    assert "Truncated specialist history for 'capture_history'" in caplog.text


@pytest.mark.anyio
async def test_word_keeper_history_is_capped_to_two_messages(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    capture = _CaptureHistorySpecialist()
    capture.name = "word_keeper"
    manager.registry.register(capture, overwrite=True)
    manager.coordinator.plan_pre_turn = AsyncMock(
        return_value=_make_plan(pre=[RoutingItem(name="word_keeper", reason="save words", chat_history_size=6)])
    )

    history = [
        ChatMessage(role="user", content="m1"),
        ChatMessage(role="assistant", content="m2"),
        ChatMessage(role="user", content="m3"),
        ChatMessage(role="assistant", content="m4"),
    ]

    await manager.prepare_pre_turn(
        message="Hello",
        chat_id="chat-1",
        history=history,
        user=mock_user,
        memory_item_service=mock_memory_item_service,
        side_effect_service=mock_side_effect_service,
    )

    assert capture.seen_history is not None
    assert len(capture.seen_history) == 2
    assert [msg.content for msg in capture.seen_history] == ["m3", "m4"]


@pytest.mark.anyio
async def test_recent_side_effects_loaded_in_pre_turn(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan_pre_turn = AsyncMock(return_value=_make_plan())
    side_effects = [
        TeacherSideEffect(
            name="word_keeper",
            phase="post_response",
            status="action_taken",
            info_for_teacher="Saved 2 vocabulary items.",
            artifacts={"saved_words": ["ord", "fras"]},
            routing_reason="save request",
            latency_ms=12,
            created_at=None,
        )
    ]
    mock_side_effect_service.load_recent_for_teacher.return_value = side_effects

    _plan, _pre, recent = await manager.prepare_pre_turn(
        message="Hello",
        chat_id="chat-1",
        history=[],
        user=mock_user,
        memory_item_service=mock_memory_item_service,
        side_effect_service=mock_side_effect_service,
    )

    assert recent == side_effects
    mock_side_effect_service.load_recent_for_teacher.assert_awaited_once_with(user_id=mock_user.id, chat_id="chat-1")


# ---------------------------------------------------------------------------
# URL safety tests (static)
# ---------------------------------------------------------------------------


def test_is_safe_url(mock_settings):
    manager = AgentsManager(mock_settings)

    assert manager._is_safe_url("https://example.com") is True
    assert manager._is_safe_url("http://example.com") is True
    assert manager._is_safe_url("javascript:alert(1)") is False
    assert manager._is_safe_url("ftp://example.com") is False
    assert manager._is_safe_url("http://localhost:5173/?view=grammar") is True
    assert manager._is_safe_url("http://localhost:8080") is False
    assert manager._is_safe_url("http://[invalid-ip]") is False
    assert manager._is_safe_url("http://user:pass@example.com") is False


def test_manager_registers_default_specialists(mock_settings):
    manager = AgentsManager(mock_settings)
    assert manager.registry.list_names() == ["word_keeper"]
