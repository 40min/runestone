"""
Tests for the CoordinatorAgent.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import OutputParserException

from runestone.agents.coordinator import CoordinatorAgent
from runestone.agents.schemas import ChatMessage, CoordinatorPlan, RoutingItem
from runestone.config import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.coordinator_provider = "openrouter"
    settings.coordinator_model = "grok-coordinator"
    settings.openrouter_api_key = "test-api-key"
    settings.openai_api_key = "test-openai-key"
    return settings


@pytest.fixture
def mock_chat_model():
    """Create a mock LangChain chat model."""
    mock_model = MagicMock()
    # Mock with_structured_output to return a mock LLM
    mock_llm_with_structure = AsyncMock()
    mock_model.with_structured_output.return_value = mock_llm_with_structure
    return mock_model


@pytest.fixture
def coordinator_agent(mock_settings, mock_chat_model):
    """Create a CoordinatorAgent instance with mocked dependencies."""
    with patch("runestone.agents.coordinator.build_chat_model", return_value=mock_chat_model):
        agent = CoordinatorAgent(mock_settings)
        return agent


def test_init_uses_coordinator_model(mock_settings, mock_chat_model):
    """Test initialization with required coordinator model."""
    with patch("runestone.agents.coordinator.build_chat_model", return_value=mock_chat_model) as mock_build:
        CoordinatorAgent(mock_settings)
        mock_build.assert_called_once_with(mock_settings, "coordinator")


def test_init_coordinator_model(mock_settings, mock_chat_model):
    """Test initialization with coordinator model override."""
    mock_settings.coordinator_model = "gpt-4o-mini"
    with patch("runestone.agents.coordinator.build_chat_model", return_value=mock_chat_model) as mock_build:
        CoordinatorAgent(mock_settings)
        mock_build.assert_called_once_with(mock_settings, "coordinator")


@pytest.mark.anyio
async def test_plan_success(coordinator_agent, mock_chat_model):
    """Test successful plan generation."""
    expected_plan = CoordinatorPlan(
        pre_response=[RoutingItem(name="memory_reader", reason="Test", chat_history_size=2)],
        post_response=[RoutingItem(name="memory_keeper", reason="Test", chat_history_size=2)],
        audit={"trace": "ok"},
    )
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = expected_plan

    history = [ChatMessage(role="user", content="Hello")]
    plan = await coordinator_agent.plan(
        message="I am John",
        history=history,
        available_specialists=["memory_reader", "memory_keeper"],
    )

    assert plan == expected_plan
    mock_llm.ainvoke.assert_called_once()

    # Verify history is passed correctly
    call_args = mock_llm.ainvoke.call_args[0][0]
    human_msg = call_args[1]
    payload = json.loads(human_msg.content)
    assert payload["message"] == "I am John"
    assert payload["history"][0]["content"] == "Hello"
    assert payload["available_specialists"] == ["memory_reader", "memory_keeper"]


@pytest.mark.anyio
async def test_plan_output_parser_exception(coordinator_agent, mock_chat_model):
    """Test plan generation with OutputParserException."""
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.side_effect = OutputParserException("Malformed JSON")

    plan = await coordinator_agent.plan(
        message="msg",
        history=[],
        available_specialists=["memory_reader"],
    )

    assert plan.pre_response == []
    assert plan.post_response == []
    assert plan.audit["error"] == "output_parsing"


@pytest.mark.anyio
async def test_plan_generic_exception(coordinator_agent, mock_chat_model):
    """Test plan generation with generic exception."""
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.side_effect = ValueError("Network error")

    plan = await coordinator_agent.plan(
        message="msg",
        history=[],
        available_specialists=["memory_reader"],
    )

    assert plan.pre_response == []
    assert plan.post_response == []
    assert plan.audit["error"] == "generic_error"
    assert "Network error" in plan.audit["details"]
