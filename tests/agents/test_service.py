"""
Tests for AgentsManager orchestration.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from runestone.agents.manager import AgentsManager
from runestone.config import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.chat_provider = "openrouter"
    settings.chat_model = "test-model"
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


@pytest.mark.anyio
async def test_generate_response_delegates_to_teacher(mock_settings, mock_user, mock_memory_item_service):
    """AgentsManager should delegate to TeacherAgent and unpack artifacts."""
    manager = AgentsManager(mock_settings)
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = MagicMock(
        status="action_taken",
        artifacts={"response": "Hi there!", "final_messages": []},
    )

    response, sources = await manager.generate_response(
        "Hello",
        [],
        mock_user,
        mock_memory_item_service,
    )

    assert response == "Hi there!"
    assert sources is None
    manager.teacher.generate_response.assert_called_once()


@pytest.mark.anyio
async def test_generate_response_runs_cleanup_on_new_chat(mock_settings, mock_user, mock_memory_item_service):
    """Cleanup should run when history is empty."""
    manager = AgentsManager(mock_settings)
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = MagicMock(
        status="action_taken",
        artifacts={"response": "Hi there!", "final_messages": []},
    )

    await manager.generate_response(
        "Hello",
        [],
        mock_user,
        mock_memory_item_service,
    )

    mock_memory_item_service.cleanup_old_mastered_areas.assert_called_once_with(mock_user.id, older_than_days=90)


@pytest.mark.anyio
async def test_generate_response_skips_cleanup_with_history(mock_settings, mock_user, mock_memory_item_service):
    """Cleanup should not run when history is present."""
    manager = AgentsManager(mock_settings)
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = MagicMock(
        status="action_taken",
        artifacts={"response": "Hi there!", "final_messages": []},
    )

    await manager.generate_response(
        "Hello",
        [MagicMock(role="user", content="Old msg")],
        mock_user,
        mock_memory_item_service,
    )

    mock_memory_item_service.cleanup_old_mastered_areas.assert_not_called()


@pytest.mark.anyio
async def test_generate_response_extracts_sources(mock_settings, mock_user, mock_memory_item_service):
    manager = AgentsManager(mock_settings)
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = MagicMock(
        status="action_taken",
        artifacts={
            "response": "Svar med källor",
            "final_messages": [
                ToolMessage(
                    content=(
                        '{"tool":"search_news_with_dates","results":[{"title":"Nyhet","url":"https://example.com",'
                        '"date":"2026-02-05"}]}'
                    ),
                    tool_call_id="tool-call-1",
                ),
                AIMessage(content="Svar med källor"),
            ],
        },
    )

    response, sources = await manager.generate_response(
        "Nyheter",
        [],
        mock_user,
        mock_memory_item_service,
    )

    assert response == "Svar med källor"
    assert sources == [{"title": "Nyhet", "url": "https://example.com", "date": "2026-02-05"}]


@pytest.mark.anyio
async def test_generate_response_filters_unsafe_urls(mock_settings, mock_user, mock_memory_item_service):
    manager = AgentsManager(mock_settings)
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = MagicMock(
        status="action_taken",
        artifacts={
            "response": "Svar med källor",
            "final_messages": [
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
        },
    )

    _response, sources = await manager.generate_response(
        "Nyheter",
        [],
        mock_user,
        mock_memory_item_service,
    )

    assert sources == [{"title": "Safe", "url": "https://example.com", "date": "2026-02-05"}]


@pytest.mark.anyio
async def test_generate_response_does_not_cap_grammar_sources(mock_settings, mock_user, mock_memory_item_service):
    manager = AgentsManager(mock_settings)
    manager.teacher = AsyncMock()
    manager.teacher.generate_response.return_value = MagicMock(
        status="action_taken",
        artifacts={
            "response": "Svar med grammatik-källor",
            "final_messages": [
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
        },
    )

    response, sources = await manager.generate_response(
        "Grammatik",
        [],
        mock_user,
        mock_memory_item_service,
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
