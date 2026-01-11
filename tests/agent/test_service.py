"""
Tests for the agent service.

This module tests the AgentService class, including prompt formatting,
history management, and LLM interaction via LangChain agent.
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from runestone.agent.schemas import ChatMessage
from runestone.agent.service import AgentService
from runestone.config import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.chat_provider = "openrouter"
    settings.chat_model = "x-ai/grok-2-1212"
    settings.agent_persona = "default"
    settings.openrouter_api_key = "test-api-key"
    settings.openai_api_key = "test-openai-key"
    return settings


@pytest.fixture
def mock_chat_model():
    """Create a mock LangChain chat model."""
    mock_model = MagicMock()
    return mock_model


@pytest.fixture
def agent_service(mock_settings, mock_chat_model):
    """Create an AgentService instance with mocked dependencies."""
    with patch("runestone.agent.service.ChatOpenAI", return_value=mock_chat_model):
        service = AgentService(mock_settings)
        service.chat_model = mock_chat_model
        return service


@pytest.fixture
def mock_user_service():
    return MagicMock()


@pytest.fixture
def mock_user():
    return MagicMock()


def test_build_agent(agent_service, mock_user_service, mock_user):
    """Test that build_agent creates a ReAct agent with tools."""
    with patch("runestone.agent.service.create_react_agent") as mock_create_agent:
        with patch("runestone.agent.service.create_update_memory_tool") as mock_create_tool:
            agent_service.build_agent(mock_user_service, mock_user)

            mock_create_tool.assert_called_once_with(mock_user_service, mock_user)
            mock_create_agent.assert_called_once()

            call_kwargs = mock_create_agent.call_args[1]
            assert call_kwargs["model"] == agent_service.chat_model
            assert len(call_kwargs["tools"]) > 0
            assert "AVAILABLE TOOLS" in call_kwargs["prompt"]


def test_generate_response_orchestration(agent_service, mock_user_service, mock_user):
    """Test generate_response orchestration logic."""
    message = "Hello"
    history = []

    # Mock the agent executor
    mock_agent_executor = MagicMock()
    mock_agent_executor.invoke.return_value = {
        "messages": [HumanMessage(content="Hello"), AIMessage(content="Hi there!")]
    }

    with patch.object(agent_service, "build_agent", return_value=mock_agent_executor) as mock_build:
        response = agent_service.generate_response(message, history, mock_user_service, mock_user)

        assert response == "Hi there!"
        mock_build.assert_called_once_with(mock_user_service, mock_user)
        mock_agent_executor.invoke.assert_called_once()

        # Verify inputs to invoke
        invoke_args = mock_agent_executor.invoke.call_args[0][0]
        messages = invoke_args["messages"]
        assert len(messages) == 1
        assert isinstance(messages[0], HumanMessage)
        assert messages[0].content == "Hello"


def test_generate_response_with_history(agent_service, mock_user_service, mock_user):
    """Test generate_response with conversation history."""
    message = "Current msg"
    history = [ChatMessage(role="user", content="Old user msg"), ChatMessage(role="assistant", content="Old bot msg")]

    mock_agent_executor = MagicMock()
    mock_agent_executor.invoke.return_value = {"messages": [AIMessage(content="Response")]}

    with patch.object(agent_service, "build_agent", return_value=mock_agent_executor):
        agent_service.generate_response(message, history, mock_user_service, mock_user)

        invoke_args = mock_agent_executor.invoke.call_args[0][0]
        messages = invoke_args["messages"]
        # History (2) + Current (1) = 3
        assert len(messages) == 3
        assert messages[0].content == "Old user msg"
        assert messages[1].content == "Old bot msg"
        assert messages[2].content == "Current msg"


def test_generate_response_with_memory(agent_service, mock_user_service, mock_user):
    """Test generate_response injects memory context."""
    memory_context = {"personal_info": {"name": "Alice"}}

    mock_agent_executor = MagicMock()
    mock_agent_executor.invoke.return_value = {"messages": [AIMessage(content="R")]}

    with patch.object(agent_service, "build_agent", return_value=mock_agent_executor):
        agent_service.generate_response("msg", [], mock_user_service, mock_user, memory_context)

        invoke_args = mock_agent_executor.invoke.call_args[0][0]
        messages = invoke_args["messages"]
        # System (Memory) + Current (1) = 2
        assert isinstance(messages[0], SystemMessage)
        assert "STUDENT MEMORY" in messages[0].content
        assert "Alice" in messages[0].content


def test_openai_provider_configuration(mock_settings):
    """Test that OpenAI provider is configured correctly."""
    mock_settings.chat_provider = "openai"

    with patch("runestone.agent.service.ChatOpenAI") as mock_chat_openai:
        AgentService(mock_settings)

        # Verify ChatOpenAI was called with correct parameters
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["model"] == "x-ai/grok-2-1212"
        assert call_kwargs["openai_api_key"] == "test-openai-key"
        assert call_kwargs["openai_api_base"] is None  # No custom base for OpenAI
