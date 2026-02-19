"""
Tests for the agent service.

This module tests the AgentService class, including prompt formatting,
history management, and LLM interaction via LangChain agent.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from runestone.agent.schemas import ChatMessage
from runestone.agent.service import AgentService
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
    settings.app_base_url = "http://localhost:5173"
    return settings


@pytest.fixture
def mock_chat_model():
    """Create a mock LangChain chat model."""
    mock_model = MagicMock()
    return mock_model


@pytest.fixture
def agent_service(mock_settings, mock_user_service, mock_chat_model):
    """Create an AgentService instance with mocked dependencies."""
    with patch("runestone.agent.service.ChatOpenAI", return_value=mock_chat_model):
        with patch("runestone.agent.service.create_agent"):
            service = AgentService(mock_settings)
            # Mock the agent executor
            service.agent = AsyncMock()
            return service


@pytest.fixture
def mock_user_service():
    return MagicMock()


@pytest.fixture
def mock_memory_item_service():
    return MagicMock()


@pytest.fixture
def mock_vocabulary_service():
    return MagicMock()


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    user.mother_tongue = None
    return user


def test_build_agent(mock_settings, mock_chat_model, mock_user_service):
    """Test that build_agent creates a ReAct agent with tools."""
    with patch("runestone.agent.service.ChatOpenAI", return_value=mock_chat_model):
        with patch("runestone.agent.service.create_agent") as mock_create_agent:
            service = AgentService(mock_settings)
            service.build_agent()

            mock_create_agent.assert_called()
            call_kwargs = mock_create_agent.call_args[1]
            assert call_kwargs["model"] == mock_chat_model
            # Verify tools were passed to create_agent
            tools = mock_create_agent.call_args[1]["tools"]
            # read_memory, upsert_memory_item, update_memory_status, promote_to_strength,
            # delete_memory_item, start_student_info, prioritize_words_for_learning,
            # search_news_with_dates, search_grammar, read_grammar_page, read_url
            assert len(tools) == 11
            assert "MEMORY PROTOCOL" in call_kwargs["system_prompt"]


@pytest.mark.anyio
async def test_generate_response_orchestration(
    agent_service, mock_user, mock_vocabulary_service, mock_memory_item_service
):
    """Test generate_response orchestration logic."""
    message = "Hello"
    history = []

    agent_service.agent.ainvoke.return_value = {
        "messages": [HumanMessage(content="Hello"), AIMessage(content="Hi there!")]
    }

    response, sources = await agent_service.generate_response(
        message, history, mock_user, mock_vocabulary_service, mock_memory_item_service
    )

    assert response == "Hi there!"
    assert sources is None
    agent_service.agent.ainvoke.assert_called_once()
    mock_memory_item_service.cleanup_old_mastered_areas.assert_called_once_with(mock_user.id, older_than_days=90)

    # Verify context injection (via AgentContext)
    call_kwargs = agent_service.agent.ainvoke.call_args[1]
    context = call_kwargs.get("context")
    assert context.user == mock_user
    assert context.vocabulary_service == mock_vocabulary_service
    assert context.memory_item_service == mock_memory_item_service

    # Verify inputs to invoke
    invoke_args = agent_service.agent.ainvoke.call_args[0][0]
    messages = invoke_args["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "Hello"


@pytest.mark.anyio
async def test_generate_response_with_history(
    agent_service, mock_user, mock_vocabulary_service, mock_memory_item_service
):
    """Test generate_response with conversation history."""
    message = "Current msg"
    history = [
        ChatMessage(role="user", content="Old user msg"),
        ChatMessage(
            role="assistant",
            content="Old bot msg",
            sources=[{"title": "Nyhet", "url": "https://example.com", "date": "2026-02-05"}],
        ),
    ]

    agent_service.agent.ainvoke.return_value = {"messages": [AIMessage(content="Response")]}

    await agent_service.generate_response(
        message, history, mock_user, mock_vocabulary_service, mock_memory_item_service
    )
    mock_memory_item_service.cleanup_old_mastered_areas.assert_not_called()

    invoke_args = agent_service.agent.ainvoke.call_args[0][0]
    messages = invoke_args["messages"]
    # History (2) + Current (1) = 3
    assert len(messages) == 3
    assert messages[0].content == "Old user msg"
    assert "[NEWS_SOURCES]" in messages[1].content
    assert "Old bot msg" in messages[1].content
    assert messages[2].content == "Current msg"


@pytest.mark.anyio
async def test_generate_response_with_mother_tongue(
    agent_service, mock_user, mock_vocabulary_service, mock_memory_item_service
):
    """Test generate_response injects mother tongue context."""
    mock_user.mother_tongue = "Spanish"

    agent_service.agent.ainvoke.return_value = {"messages": [AIMessage(content="Response")]}

    await agent_service.generate_response("msg", [], mock_user, mock_vocabulary_service, mock_memory_item_service)

    invoke_args = agent_service.agent.ainvoke.call_args[0][0]
    messages = invoke_args["messages"]

    # We expect the mother tongue system message to be present
    # Depending on implementation, it might be the only system message or one of them.
    # Based on code: if no memory_context, only this system message.
    assert any(isinstance(m, SystemMessage) and "Spanish" in m.content for m in messages)


def test_openai_provider_configuration(mock_settings, mock_user_service):
    """Test that OpenAI provider is configured correctly."""
    mock_settings.chat_provider = "openai"

    with patch("runestone.agent.service.ChatOpenAI") as mock_chat_openai:
        with patch("runestone.agent.service.create_agent"):
            AgentService(mock_settings)

            # Verify ChatOpenAI was called with correct parameters
            call_kwargs = mock_chat_openai.call_args[1]
            assert call_kwargs["model"] == "test-model"
            # The implementation uses api_key parameter, not openai_api_key
            assert call_kwargs["api_key"] is not None
    assert call_kwargs.get("base_url") is None  # No custom base for OpenAI


def test_format_sources():
    """Test that sources are formatted with cap and domain metadata."""
    sources = []
    for idx in range(1, 25):
        sources.append(
            {
                "title": f"Title {idx}",
                "url": f"https://example.com/article-{idx}",
                "date": "2026-02-05",
            }
        )

    formatted = AgentService._format_sources(sources)
    assert formatted.count("\n") >= 1
    assert "[NEWS_SOURCES]" in formatted
    assert "example.com" in formatted
    assert "Title 1" in formatted
    assert "Title 20" in formatted
    assert "Title 21" not in formatted


@pytest.mark.anyio
async def test_generate_response_extracts_sources(
    agent_service, mock_user, mock_vocabulary_service, mock_memory_item_service
):
    """Test that news tool output is converted into sources."""
    agent_service.agent.ainvoke.return_value = {
        "messages": [
            ToolMessage(
                content=(
                    '{"tool":"search_news_with_dates","results":[{"title":"Nyhet","url":"https://example.com",'
                    '"date":"2026-02-05"}]}'
                ),
                tool_call_id="tool-call-1",
            ),
            AIMessage(content="Svar med källor"),
        ]
    }

    response, sources = await agent_service.generate_response(
        "Nyheter", [], mock_user, mock_vocabulary_service, mock_memory_item_service
    )

    assert response == "Svar med källor"
    assert sources == [{"title": "Nyhet", "url": "https://example.com", "date": "2026-02-05"}]


@pytest.mark.anyio
async def test_generate_response_filters_unsafe_urls(
    agent_service, mock_user, mock_vocabulary_service, mock_memory_item_service
):
    """Test that unsafe URLs are excluded from sources."""
    agent_service.agent.ainvoke.return_value = {
        "messages": [
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
        ]
    }

    _response, sources = await agent_service.generate_response(
        "Nyheter", [], mock_user, mock_vocabulary_service, mock_memory_item_service
    )

    assert sources == [{"title": "Safe", "url": "https://example.com", "date": "2026-02-05"}]


def test_is_safe_url(agent_service):
    """Test URL safety validation."""
    # Standard ports
    assert agent_service._is_safe_url("https://example.com") is True
    assert agent_service._is_safe_url("http://example.com") is True

    # Blocked schemes
    assert agent_service._is_safe_url("javascript:alert(1)") is False
    assert agent_service._is_safe_url("ftp://example.com") is False

    # App port (5173 from mock_settings)
    assert agent_service._is_safe_url("http://localhost:5173/?view=grammar") is True

    # Other ports still blocked
    assert agent_service._is_safe_url("http://localhost:8080") is False

    # Invalid URLs
    assert agent_service._is_safe_url("http://[invalid-ip]") is False
    assert agent_service._is_safe_url("http://user:pass@example.com") is False
