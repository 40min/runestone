"""
Tests for AgentsManager orchestration.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from runestone.agents.manager import AgentsManager
from runestone.agents.schemas import ChatMessage, CoordinatorPlan, RoutingItem, TeacherSideEffect
from runestone.agents.specialists.base import BaseSpecialist, SpecialistContext, SpecialistResult
from runestone.config import Settings
from runestone.services.agent_side_effect_service import AgentSideEffectService


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.chat_provider = "openrouter"
    settings.chat_model = "test-model"
    settings.coordinator_model = "test-coordinator-model"
    settings.agent_persona = "default"
    settings.openrouter_api_key = "test-api-key"
    settings.openai_api_key = "test-openai-key"
    settings.allowed_origins = "http://localhost:5173"
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
    service.replace_post_response_side_effects = AsyncMock(return_value=None)
    return service


@pytest.mark.anyio
async def test_generate_response_delegates_to_teacher(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan = AsyncMock(return_value=CoordinatorPlan(pre_response=[], post_response=[], audit={}))
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = ("Hi there!", [])

    response, sources = await manager.generate_response(
        "Hello",
        "chat-1",
        [],
        mock_user,
        mock_memory_item_service,
        mock_side_effect_service,
    )

    assert response == "Hi there!"
    assert sources is None
    manager.teacher.generate_response.assert_called_once()


@pytest.mark.anyio
async def test_coordinator_history_is_truncated(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan = AsyncMock(return_value=CoordinatorPlan(pre_response=[], post_response=[], audit={}))
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = ("Hi there!", [])

    history = [ChatMessage(role="user", content=f"m{i}") for i in range(10)]
    await manager.generate_response(
        "Hello", "chat-1", history, mock_user, mock_memory_item_service, mock_side_effect_service
    )

    _args, kwargs = manager.coordinator.plan.call_args
    assert len(kwargs["history"]) == manager.COORDINATOR_MAX_HISTORY_MESSAGES


@pytest.mark.anyio
async def test_generate_response_runs_cleanup_on_new_chat(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan = AsyncMock(return_value=CoordinatorPlan(pre_response=[], post_response=[], audit={}))
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = ("Hi there!", [])

    await manager.generate_response(
        "Hello",
        "chat-1",
        [],
        mock_user,
        mock_memory_item_service,
        mock_side_effect_service,
    )

    mock_memory_item_service.cleanup_old_mastered_areas.assert_called_once_with(mock_user.id, older_than_days=90)


@pytest.mark.anyio
async def test_generate_response_skips_cleanup_with_history(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan = AsyncMock(return_value=CoordinatorPlan(pre_response=[], post_response=[], audit={}))
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = ("Hi there!", [])

    await manager.generate_response(
        "Hello",
        "chat-1",
        [MagicMock(role="user", content="Old msg")],
        mock_user,
        mock_memory_item_service,
        mock_side_effect_service,
    )

    mock_memory_item_service.cleanup_old_mastered_areas.assert_not_called()


@pytest.mark.anyio
async def test_generate_response_extracts_sources(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan = AsyncMock(return_value=CoordinatorPlan(pre_response=[], post_response=[], audit={}))
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

    response, sources = await manager.generate_response(
        "Nyheter",
        "chat-1",
        [],
        mock_user,
        mock_memory_item_service,
        mock_side_effect_service,
    )

    assert response == "Svar med källor"
    assert sources == [{"title": "Nyhet", "url": "https://example.com", "date": "2026-02-05"}]


@pytest.mark.anyio
async def test_generate_response_filters_unsafe_urls(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan = AsyncMock(return_value=CoordinatorPlan(pre_response=[], post_response=[], audit={}))
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = (
        "Svar med källor",
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
            AIMessage(content="Svar med källor"),
        ],
    )

    _response, sources = await manager.generate_response(
        "Nyheter",
        "chat-1",
        [],
        mock_user,
        mock_memory_item_service,
        mock_side_effect_service,
    )

    assert sources == [{"title": "Safe", "url": "https://example.com", "date": "2026-02-05"}]


@pytest.mark.anyio
async def test_generate_response_does_not_cap_grammar_sources(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan = AsyncMock(return_value=CoordinatorPlan(pre_response=[], post_response=[], audit={}))
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = (
        "Svar med grammatik-källor",
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
            AIMessage(content="Svar med grammatik-källor"),
        ],
    )

    response, sources = await manager.generate_response(
        "Grammatik",
        "chat-1",
        [],
        mock_user,
        mock_memory_item_service,
        mock_side_effect_service,
    )

    assert response == "Svar med grammatik-källor"
    assert sources == [
        {"title": "Doc 1", "url": "https://example.com/1", "date": ""},
        {"title": "Doc 2", "url": "https://example.com/2", "date": ""},
        {"title": "Doc 3", "url": "https://example.com/3", "date": ""},
        {"title": "Doc 4", "url": "https://example.com/4", "date": ""},
        {"title": "Doc 5", "url": "https://example.com/5", "date": ""},
    ]


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
    assert "memory_reader" in manager.registry.list_names()


@pytest.mark.anyio
async def test_pre_results_passed_to_teacher(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan = AsyncMock(return_value=CoordinatorPlan(pre_response=[], post_response=[], audit={}))
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = ("Hi there!", [])

    await manager.generate_response(
        "Hello", "chat-1", [], mock_user, mock_memory_item_service, mock_side_effect_service
    )

    _args, kwargs = manager.teacher.generate_response.call_args
    assert "pre_results" in kwargs


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
    manager.coordinator.plan = AsyncMock(
        return_value=CoordinatorPlan(
            pre_response=[RoutingItem(name="capture_history", reason="test", chat_history_size=1)],
            post_response=[],
            audit={},
        )
    )
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = ("Hi there!", [])

    history = [
        ChatMessage(role="user", content="m1"),
        ChatMessage(role="assistant", content="m2"),
        ChatMessage(role="user", content="m3"),
    ]
    side_effect_service = MagicMock(spec=AgentSideEffectService)
    side_effect_service.load_recent_for_teacher = AsyncMock(return_value=[])
    side_effect_service.replace_post_response_side_effects = AsyncMock(return_value=None)

    await manager.generate_response(
        "Hello",
        "chat-1",
        history,
        mock_user,
        mock_memory_item_service,
        side_effect_service,
    )

    assert capture.seen_history is not None
    assert len(capture.seen_history) == 1
    assert capture.seen_history[0].content == "m3"


@pytest.mark.anyio
async def test_recent_side_effects_passed_to_teacher(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan = AsyncMock(return_value=CoordinatorPlan(pre_response=[], post_response=[], audit={}))
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = ("Hi there!", [])
    mock_side_effect_service.load_recent_for_teacher.return_value = [
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

    await manager.generate_response(
        "Hello", "chat-1", [], mock_user, mock_memory_item_service, mock_side_effect_service
    )

    _args, kwargs = manager.teacher.generate_response.call_args
    assert kwargs["recent_side_effects"] == mock_side_effect_service.load_recent_for_teacher.return_value


class _ActionSpecialist(BaseSpecialist):
    def __init__(self):
        super().__init__(name="word_keeper")

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        return SpecialistResult(
            status="action_taken",
            info_for_teacher="Saved 2 vocabulary items.",
            artifacts={"saved_words": ["ord", "fras"]},
        )


@pytest.mark.anyio
async def test_post_response_results_are_forwarded_to_side_effect_service(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.registry.register(_ActionSpecialist())
    manager.coordinator.plan = AsyncMock(
        return_value=CoordinatorPlan(
            pre_response=[],
            post_response=[RoutingItem(name="word_keeper", reason="save words", chat_history_size=0)],
            audit={},
        )
    )
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = ("Hi there!", [])

    await manager.generate_response(
        "Hello", "chat-1", [], mock_user, mock_memory_item_service, mock_side_effect_service
    )

    mock_side_effect_service.replace_post_response_side_effects.assert_awaited_once()
    kwargs = mock_side_effect_service.replace_post_response_side_effects.call_args.kwargs
    assert kwargs["user_id"] == mock_user.id
    assert kwargs["chat_id"] == "chat-1"
    assert kwargs["results"][0]["name"] == "word_keeper"
    assert kwargs["results"][0]["result"]["status"] == "action_taken"
    assert kwargs["results"][0]["result"]["artifacts"] == {"saved_words": ["ord", "fras"]}


@pytest.mark.anyio
async def test_manager_passes_chat_scope_to_side_effect_service(
    mock_settings, mock_user, mock_memory_item_service, mock_side_effect_service
):
    manager = AgentsManager(mock_settings)
    manager.coordinator.plan = AsyncMock(return_value=CoordinatorPlan(pre_response=[], post_response=[], audit={}))
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = ("Hi there!", [])

    await manager.generate_response(
        "Hello", "chat-1", [], mock_user, mock_memory_item_service, mock_side_effect_service
    )

    mock_side_effect_service.load_recent_for_teacher.assert_awaited_once_with(user_id=mock_user.id, chat_id="chat-1")
    mock_side_effect_service.replace_post_response_side_effects.assert_awaited_once_with(
        user_id=mock_user.id,
        chat_id="chat-1",
        results=[],
    )
