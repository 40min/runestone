"""
Tests for the TeacherAgent specialist.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from runestone.agents.schemas import ChatMessage
from runestone.agents.specialists.teacher import TeacherAgent
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
def mock_chat_model():
    """Create a mock LangChain chat model."""
    mock_model = MagicMock()
    return mock_model


@pytest.fixture
def teacher_agent(mock_settings, mock_chat_model):
    """Create a TeacherAgent instance with mocked dependencies."""
    with patch("runestone.agents.specialists.teacher.ChatOpenAI", return_value=mock_chat_model):
        with patch("runestone.agents.specialists.teacher.create_agent"):
            agent = TeacherAgent(mock_settings)
            # Mock the agent executor
            agent.agent = AsyncMock()
            return agent


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    user.mother_tongue = None
    return user


def test_build_agent(mock_settings, mock_chat_model):
    """Test that build_agent creates a ReAct agent with tools."""
    with patch("runestone.agents.specialists.teacher.ChatOpenAI", return_value=mock_chat_model):
        with patch("runestone.agents.specialists.teacher.create_agent") as mock_create_agent:
            agent = TeacherAgent(mock_settings)
            agent.build_agent()

            mock_create_agent.assert_called()
            call_kwargs = mock_create_agent.call_args[1]
            assert call_kwargs["model"] == mock_chat_model
            tools = mock_create_agent.call_args[1]["tools"]
            assert len(tools) == 12
            assert "MEMORY PROTOCOL" in call_kwargs["system_prompt"]
            assert "TOOL TRUTHFULNESS (MANDATORY)" in call_kwargs["system_prompt"]
            assert "Never pretend persistence happened." in call_kwargs["system_prompt"]
            assert "This includes normal conversation, not only mistakes." in call_kwargs["system_prompt"]


@pytest.mark.anyio
async def test_run_orchestration(teacher_agent, mock_user):
    """Test run orchestration logic."""
    teacher_agent.agent.ainvoke.return_value = {
        "messages": [HumanMessage(content="Hello"), AIMessage(content="Hi there!")]
    }

    response, final_messages = await teacher_agent.generate_response(message="Hello", history=[], user=mock_user)

    assert response == "Hi there!"
    assert isinstance(final_messages, list)
    teacher_agent.agent.ainvoke.assert_called_once()

    invoke_args = teacher_agent.agent.ainvoke.call_args[0][0]
    messages = invoke_args["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "Hello"


@pytest.mark.anyio
async def test_run_with_history(teacher_agent, mock_user):
    """Test run with conversation history."""
    history = [
        ChatMessage(role="user", content="Old user msg"),
        ChatMessage(
            role="assistant",
            content="Old bot msg",
            sources=[{"title": "Nyhet", "url": "https://example.com", "date": "2026-02-05"}],
        ),
    ]

    teacher_agent.agent.ainvoke.return_value = {"messages": [AIMessage(content="Response")]}

    await teacher_agent.generate_response(message="Current msg", history=history, user=mock_user)

    invoke_args = teacher_agent.agent.ainvoke.call_args[0][0]
    messages = invoke_args["messages"]
    assert len(messages) == 3
    assert messages[0].content == "Old user msg"
    assert "[NEWS_SOURCES]" in messages[1].content
    assert "Old bot msg" in messages[1].content
    assert messages[2].content == "Current msg"


@pytest.mark.anyio
async def test_run_with_mother_tongue(teacher_agent, mock_user):
    """Test run injects mother tongue context."""
    mock_user.mother_tongue = "Spanish"

    teacher_agent.agent.ainvoke.return_value = {"messages": [AIMessage(content="Response")]}

    await teacher_agent.generate_response(message="msg", history=[], user=mock_user)

    invoke_args = teacher_agent.agent.ainvoke.call_args[0][0]
    messages = invoke_args["messages"]
    assert any(isinstance(m, SystemMessage) and "Spanish" in m.content for m in messages)


def test_openai_provider_configuration(mock_settings):
    """Test that OpenAI provider is configured correctly."""
    mock_settings.chat_provider = "openai"

    with patch("runestone.agents.specialists.teacher.ChatOpenAI") as mock_chat_openai:
        with patch("runestone.agents.specialists.teacher.create_agent"):
            TeacherAgent(mock_settings)

            call_kwargs = mock_chat_openai.call_args[1]
            assert call_kwargs["model"] == "test-model"
            assert call_kwargs["api_key"] is not None
    assert call_kwargs.get("base_url") is None


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

    formatted = TeacherAgent._format_sources(sources)
    assert formatted.count("\n") >= 1
    assert "[NEWS_SOURCES]" in formatted
    assert "example.com" in formatted
    assert "Title 1" in formatted
    assert "Title 20" in formatted
    assert "Title 21" not in formatted
