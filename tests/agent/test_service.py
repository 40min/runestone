"""
Tests for the agent service.

This module tests the AgentService class, including prompt formatting,
history management, and LLM interaction via LangChain agent.
"""

from unittest.mock import AsyncMock, MagicMock, patch

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
    settings.chat_model = "test-model"
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
def mock_user():
    return MagicMock()


def test_build_agent(mock_settings, mock_chat_model, mock_user_service):
    """Test that build_agent creates a ReAct agent with tools."""
    with patch("runestone.agent.service.ChatOpenAI", return_value=mock_chat_model):
        with patch("runestone.agent.service.create_agent") as mock_create_agent:
            service = AgentService(mock_settings)
            service.build_agent()

            mock_create_agent.assert_called()
            call_kwargs = mock_create_agent.call_args[1]
            assert call_kwargs["model"] == mock_chat_model
            assert len(call_kwargs["tools"]) == 1
            assert "AVAILABLE TOOLS" in call_kwargs["system_prompt"]


@pytest.mark.anyio
async def test_generate_response_orchestration(agent_service, mock_user_service, mock_user):
    """Test generate_response orchestration logic."""
    message = "Hello"
    history = []

    agent_service.agent.ainvoke.return_value = {
        "messages": [HumanMessage(content="Hello"), AIMessage(content="Hi there!")]
    }

    response = await agent_service.generate_response(message, history, mock_user, mock_user_service)

    assert response == "Hi there!"
    agent_service.agent.ainvoke.assert_called_once()

    # Verify context injection (via AgentContext)
    call_kwargs = agent_service.agent.ainvoke.call_args[1]
    context = call_kwargs.get("context")
    assert context.user == mock_user
    assert context.user_service == mock_user_service

    # Verify inputs to invoke
    invoke_args = agent_service.agent.ainvoke.call_args[0][0]
    messages = invoke_args["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "Hello"


@pytest.mark.anyio
async def test_generate_response_with_history(agent_service, mock_user_service, mock_user):
    """Test generate_response with conversation history."""
    message = "Current msg"
    history = [ChatMessage(role="user", content="Old user msg"), ChatMessage(role="assistant", content="Old bot msg")]

    agent_service.agent.ainvoke.return_value = {"messages": [AIMessage(content="Response")]}

    await agent_service.generate_response(message, history, mock_user, mock_user_service)

    invoke_args = agent_service.agent.ainvoke.call_args[0][0]
    messages = invoke_args["messages"]
    # History (2) + Current (1) = 3
    assert len(messages) == 3
    assert messages[0].content == "Old user msg"
    assert messages[1].content == "Old bot msg"
    assert messages[2].content == "Current msg"


@pytest.mark.anyio
async def test_generate_response_with_memory(agent_service, mock_user_service, mock_user):
    """Test generate_response injects memory context."""
    memory_context = {"personal_info": {"name": "Alice"}}

    agent_service.agent.ainvoke.return_value = {"messages": [AIMessage(content="R")]}

    await agent_service.generate_response("msg", [], mock_user, mock_user_service, memory_context)

    invoke_args = agent_service.agent.ainvoke.call_args[0][0]
    messages = invoke_args["messages"]
    # System (Memory) + Current (1) = 2
    assert isinstance(messages[0], SystemMessage)
    assert "STUDENT MEMORY" in messages[0].content
    assert "Alice" in messages[0].content


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
