"""
Tests for the agent service.

This module tests the AgentService class, including prompt formatting,
history management, and LLM interaction.
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

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
    mock_model.invoke.return_value = AIMessage(content="This is a test response")
    return mock_model


@pytest.fixture
def agent_service(mock_settings, mock_chat_model):
    """Create an AgentService instance with mocked dependencies."""
    with patch("runestone.agent.service.ChatOpenAI", return_value=mock_chat_model):
        service = AgentService(mock_settings)
        service.chat_model = mock_chat_model
        return service


def test_generate_response_with_empty_history(agent_service, mock_chat_model):
    """Test generating a response with no conversation history."""
    message = "Hej! Hur mår du?"
    history = []

    response = agent_service.generate_response(message, history)

    assert response == "This is a test response"
    mock_chat_model.invoke.assert_called_once()

    # Verify the messages passed to the model
    call_args = mock_chat_model.invoke.call_args[0][0]
    assert len(call_args) == 2  # System message + user message
    assert call_args[0].content  # System prompt exists
    assert call_args[1].content == message


def test_generate_response_with_history(agent_service, mock_chat_model):
    """Test generating a response with conversation history."""
    message = "What is my name?"
    history = [
        ChatMessage(role="user", content="My name is Alice"),
        ChatMessage(role="assistant", content="Nice to meet you, Alice!"),
    ]

    response = agent_service.generate_response(message, history)

    assert response == "This is a test response"
    mock_chat_model.invoke.assert_called_once()

    # Verify the messages include history
    call_args = mock_chat_model.invoke.call_args[0][0]
    assert len(call_args) == 4  # System + 2 history + user message
    assert call_args[1].content == "My name is Alice"
    assert call_args[2].content == "Nice to meet you, Alice!"
    assert call_args[3].content == message


def test_history_truncation(agent_service, mock_chat_model):
    """Test that long conversation history is truncated."""
    # Create history longer than MAX_HISTORY_MESSAGES
    long_history = [
        ChatMessage(role="user" if i % 2 == 0 else "assistant", content=f"Message {i}")
        for i in range(AgentService.MAX_HISTORY_MESSAGES + 10)
    ]

    message = "Latest message"
    response = agent_service.generate_response(message, long_history)

    assert response == "This is a test response"

    # Verify history was truncated
    call_args = mock_chat_model.invoke.call_args[0][0]
    # System message + truncated history + current message
    assert len(call_args) == AgentService.MAX_HISTORY_MESSAGES + 2


def test_generate_response_error_handling(agent_service, mock_chat_model):
    """Test error handling when LLM call fails."""
    mock_chat_model.invoke.side_effect = Exception("API Error")

    message = "Test message"
    history = []

    with pytest.raises(Exception, match="API Error"):
        agent_service.generate_response(message, history)


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


def test_openrouter_provider_configuration(mock_settings):
    """Test that OpenRouter provider is configured correctly."""
    with patch("runestone.agent.service.ChatOpenAI") as mock_chat_openai:
        AgentService(mock_settings)

        # Verify ChatOpenAI was called with OpenRouter configuration
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["model"] == "x-ai/grok-2-1212"
        assert call_kwargs["openai_api_key"] == "test-api-key"
        assert call_kwargs["openai_api_base"] == "https://openrouter.ai/api/v1"
