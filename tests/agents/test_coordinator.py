"""
Tests for the CoordinatorAgent.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import OutputParserException

from runestone.agents.coordinator import COORDINATOR_SYSTEM_PROMPT, CoordinatorAgent
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


def test_word_keeper_prompt_eligibility():
    """Coordinator prompt should define WordKeeper eligibility correctly."""
    assert "word_keeper" in COORDINATOR_SYSTEM_PROMPT
    assert "pre_response" in COORDINATOR_SYSTEM_PROMPT
    assert "post_response" in COORDINATOR_SYSTEM_PROMPT
    assert "actual teacher reply explicitly highlights vocabulary" in COORDINATOR_SYSTEM_PROMPT
    assert "consider only the last two messages in `history`" in COORDINATOR_SYSTEM_PROMPT
    assert "set `chat_history_size` to exactly 2" in COORDINATOR_SYSTEM_PROMPT
    assert "Do not route it just because the student reused a word" in COORDINATOR_SYSTEM_PROMPT
    assert "Do not treat analysis/comparison intents as save signals" in COORDINATOR_SYSTEM_PROMPT
    assert "current_stage" in COORDINATOR_SYSTEM_PROMPT
    assert "do not speculate about the future teacher reply" in COORDINATOR_SYSTEM_PROMPT


def test_news_prompt_requires_known_topic():
    assert "Route `news` in `pre_response` only when the student's current message names a clear topic" in (
        COORDINATOR_SYSTEM_PROMPT
    )
    assert "Do NOT route `news` when the topic is still unclear" in COORDINATOR_SYSTEM_PROMPT


def test_grammar_is_absent_from_coordinator_prompt():
    assert "GrammarAgent" not in COORDINATOR_SYSTEM_PROMPT
    assert "grammar specialist" not in COORDINATOR_SYSTEM_PROMPT
    assert "search_grammar" not in COORDINATOR_SYSTEM_PROMPT


def test_word_keeper_prompt_does_not_allow_anticipatory_post_routing():
    assert "anticipate the teacher reply" not in COORDINATOR_SYSTEM_PROMPT
    assert "actual teacher reply explicitly highlights vocabulary" in COORDINATOR_SYSTEM_PROMPT


@pytest.mark.anyio
async def test_plan_success(coordinator_agent, mock_chat_model):
    """Test successful plan generation."""
    raw_plan = CoordinatorPlan(
        pre_response=[RoutingItem(name="memory_reader", reason="Test", chat_history_size=2)],
        post_response=[RoutingItem(name="memory_keeper", reason="Test", chat_history_size=2)],
        audit={"trace": "ok"},
    )
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = raw_plan

    history = [ChatMessage(role="user", content="Hello")]
    plan = await coordinator_agent.plan(
        message="I am John",
        history=history,
        current_stage="pre_response",
        available_specialists=["memory_reader", "memory_keeper"],
    )

    assert plan == CoordinatorPlan(
        pre_response=[RoutingItem(name="memory_reader", reason="Test", chat_history_size=2)],
        post_response=[],
        audit={"trace": "ok"},
    )
    mock_llm.ainvoke.assert_called_once()

    # Verify history is passed correctly
    call_args = mock_llm.ainvoke.call_args[0][0]
    human_msg = call_args[1]
    payload = json.loads(human_msg.content)
    assert payload["message"] == "I am John"
    assert payload["history"][0]["content"] == "Hello"
    assert payload["current_stage"] == "pre_response"
    assert payload["teacher_response"] is None
    assert payload["available_specialists"] == ["memory_reader", "memory_keeper"]


@pytest.mark.anyio
async def test_plan_pre_turn_only_returns_pre_items(coordinator_agent, mock_chat_model):
    expected_plan = CoordinatorPlan(
        pre_response=[RoutingItem(name="memory_reader", reason="Test", chat_history_size=2)],
        post_response=[RoutingItem(name="word_keeper", reason="Should be dropped", chat_history_size=2)],
        audit={"trace": "ok"},
    )
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = expected_plan

    plan = await coordinator_agent.plan_pre_turn(
        message="I am John",
        history=[],
        available_specialists=["memory_reader", "word_keeper"],
    )

    assert [item.name for item in plan.pre_response] == ["memory_reader"]
    assert plan.post_response == []


@pytest.mark.anyio
async def test_plan_post_turn_only_returns_post_items_and_passes_teacher_response(coordinator_agent, mock_chat_model):
    expected_plan = CoordinatorPlan(
        pre_response=[RoutingItem(name="memory_reader", reason="Should be dropped", chat_history_size=2)],
        post_response=[RoutingItem(name="word_keeper", reason="Teacher highlighted words", chat_history_size=2)],
        audit={"trace": "ok"},
    )
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = expected_plan

    plan = await coordinator_agent.plan_post_turn(
        message="What does hejda mean?",
        history=[],
        teacher_response="Useful words to remember: hejda",
        available_specialists=["word_keeper"],
    )

    assert plan.pre_response == []
    assert [item.name for item in plan.post_response] == ["word_keeper"]

    call_args = mock_llm.ainvoke.call_args[0][0]
    payload = json.loads(call_args[1].content)
    assert payload["current_stage"] == "post_response"
    assert payload["teacher_response"] == "Useful words to remember: hejda"


@pytest.mark.anyio
async def test_plan_output_parser_exception(coordinator_agent, mock_chat_model):
    """Test plan generation with OutputParserException."""
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.side_effect = OutputParserException("Malformed JSON")

    plan = await coordinator_agent.plan(
        message="msg",
        history=[],
        current_stage="pre_response",
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
        current_stage="pre_response",
        available_specialists=["memory_reader"],
    )

    assert plan.pre_response == []
    assert plan.post_response == []
    assert plan.audit["error"] == "generic_error"
    assert "Network error" in plan.audit["details"]
