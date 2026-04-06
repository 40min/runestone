"""
Tests for the CoordinatorAgent.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import OutputParserException

from runestone.agents.coordinator import (
    COORDINATOR_POST_RESPONSE_PROMPT,
    COORDINATOR_PRE_RESPONSE_PROMPT,
    CoordinatorAgent,
)
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
    assert "word_keeper" in COORDINATOR_PRE_RESPONSE_PROMPT
    assert "word_keeper" in COORDINATOR_POST_RESPONSE_PROMPT
    assert "If the current student explicitly asks to save words from an earlier turn" in (
        COORDINATOR_PRE_RESPONSE_PROMPT
    )
    assert "An earlier teacher message highlighted vocabulary but the student did not request saving it." in (
        COORDINATOR_PRE_RESPONSE_PROMPT
    )
    assert "Words were already saved in earlier turns — do not re-trigger on later turns." in (
        COORDINATOR_PRE_RESPONSE_PROMPT
    )
    assert "For all normal word_keeper cases, set `chat_history_size` to `2`." in COORDINATOR_PRE_RESPONSE_PROMPT
    assert "For all normal word_keeper cases, set `chat_history_size` to `2`." in COORDINATOR_POST_RESPONSE_PROMPT


def test_memory_reader_is_absent_from_pre_prompt():
    assert "### memory_reader (pre)" not in COORDINATOR_PRE_RESPONSE_PROMPT


def test_memory_keeper_prompt_mentions_student_driven_memory_requests():
    assert "latest student `message` explicitly asks to change memory" in COORDINATOR_POST_RESPONSE_PROMPT
    assert "older `history`" in COORDINATOR_POST_RESPONSE_PROMPT
    assert 'Student: "Forget my old goal."' in COORDINATOR_POST_RESPONSE_PROMPT
    assert 'Teacher: "You have now clearly mastered this tense."' in COORDINATOR_POST_RESPONSE_PROMPT


def test_news_prompt_requires_known_topic():
    assert "### news_agent (pre)" in COORDINATOR_PRE_RESPONSE_PROMPT
    assert "The student's current message asks about a clear, specific real-time or current-events topic" in (
        COORDINATOR_PRE_RESPONSE_PROMPT
    )
    assert "Current weather for a named city or region" in COORDINATOR_PRE_RESPONSE_PROMPT
    assert "The topic is vague or unspecified" in COORDINATOR_PRE_RESPONSE_PROMPT
    assert "For all normal news_agent cases, set `chat_history_size` to `2`." in COORDINATOR_PRE_RESPONSE_PROMPT


def test_grammar_is_absent_from_coordinator_prompt():
    assert "GrammarAgent" not in COORDINATOR_PRE_RESPONSE_PROMPT
    assert "grammar specialist" not in COORDINATOR_PRE_RESPONSE_PROMPT
    assert "search_grammar" not in COORDINATOR_PRE_RESPONSE_PROMPT
    assert "GrammarAgent" not in COORDINATOR_POST_RESPONSE_PROMPT
    assert "grammar specialist" not in COORDINATOR_POST_RESPONSE_PROMPT
    assert "search_grammar" not in COORDINATOR_POST_RESPONSE_PROMPT


def test_word_keeper_prompt_does_not_allow_anticipatory_post_routing():
    assert "anticipate the teacher reply" not in COORDINATOR_POST_RESPONSE_PROMPT
    assert (
        "The actual `teacher_response` explicitly marks vocabulary as worth saving" in COORDINATOR_POST_RESPONSE_PROMPT
    )
    assert "The teacher is only asking the student to practice, answer, or write another sentence using words." in (
        COORDINATOR_POST_RESPONSE_PROMPT
    )


def test_word_keeper_prompt_limits_pre_stage_to_explicit_save_requests():
    assert "**Route when:**" in COORDINATOR_PRE_RESPONSE_PROMPT
    assert "The current student message explicitly asks to save vocabulary in this turn" in (
        COORDINATOR_PRE_RESPONSE_PROMPT
    )
    assert "An earlier teacher message highlighted vocabulary but the student did not request saving it." in (
        COORDINATOR_PRE_RESPONSE_PROMPT
    )
    assert "The student is moving to the next exercise or continuing the lesson without an explicit save request" in (
        COORDINATOR_PRE_RESPONSE_PROMPT
    )


@pytest.mark.anyio
async def test_plan_success(coordinator_agent, mock_chat_model):
    """Test successful plan generation."""
    raw_plan = CoordinatorPlan(
        pre_response=[RoutingItem(name="word_keeper", reason="Test", chat_history_size=2)],
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
        available_specialists=["word_keeper", "memory_keeper"],
    )

    assert plan == CoordinatorPlan(
        pre_response=[RoutingItem(name="word_keeper", reason="Test", chat_history_size=2)],
        post_response=[],
        audit={"trace": "ok"},
    )
    mock_llm.ainvoke.assert_called_once()

    # Verify history is passed correctly
    call_args = mock_llm.ainvoke.call_args[0][0]
    assert call_args[0].content == COORDINATOR_PRE_RESPONSE_PROMPT
    human_msg = call_args[1]
    payload = json.loads(human_msg.content)
    assert payload["message"] == "I am John"
    assert payload["history"][0]["content"] == "Hello"
    assert payload["current_stage"] == "pre_response"
    assert payload["teacher_response"] is None
    assert payload["available_specialists"] == ["word_keeper", "memory_keeper"]


@pytest.mark.anyio
async def test_plan_pre_turn_only_returns_pre_items(coordinator_agent, mock_chat_model):
    expected_plan = CoordinatorPlan(
        pre_response=[RoutingItem(name="word_keeper", reason="Test", chat_history_size=2)],
        post_response=[RoutingItem(name="word_keeper", reason="Should be dropped", chat_history_size=2)],
        audit={"trace": "ok"},
    )
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = expected_plan

    plan = await coordinator_agent.plan_pre_turn(
        message="I am John",
        history=[],
        available_specialists=["word_keeper"],
    )

    assert [item.name for item in plan.pre_response] == ["word_keeper"]
    assert plan.post_response == []


@pytest.mark.anyio
async def test_plan_post_turn_only_returns_post_items_and_passes_teacher_response(coordinator_agent, mock_chat_model):
    expected_plan = CoordinatorPlan(
        pre_response=[RoutingItem(name="word_keeper", reason="Should be dropped", chat_history_size=2)],
        post_response=[RoutingItem(name="memory_keeper", reason="Teacher confirmed mastery", chat_history_size=2)],
        audit={"trace": "ok"},
    )
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = expected_plan

    plan = await coordinator_agent.plan_post_turn(
        message="What does hejda mean?",
        history=[],
        teacher_response="Useful words to remember: hejda",
        available_specialists=["word_keeper", "memory_keeper"],
    )

    assert plan.pre_response == []
    assert [item.name for item in plan.post_response] == ["memory_keeper"]

    call_args = mock_llm.ainvoke.call_args[0][0]
    assert call_args[0].content == COORDINATOR_POST_RESPONSE_PROMPT
    payload = json.loads(call_args[1].content)
    assert payload["current_stage"] == "post_response"
    assert payload["teacher_response"] == "Useful words to remember: hejda"


@pytest.mark.anyio
async def test_plan_pre_turn_uses_pre_prompt_for_next_task_style_message(coordinator_agent, mock_chat_model):
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = CoordinatorPlan(pre_response=[], post_response=[], audit={"trace": "ok"})

    plan = await coordinator_agent.plan_pre_turn(
        message="Next task, please.",
        history=[ChatMessage(role="assistant", content="Bra jobbat.")],
        available_specialists=["word_keeper"],
    )

    assert plan.pre_response == []
    call_args = mock_llm.ainvoke.call_args[0][0]
    assert call_args[0].content == COORDINATOR_PRE_RESPONSE_PROMPT
    payload = json.loads(call_args[1].content)
    assert payload["message"] == "Next task, please."


@pytest.mark.anyio
async def test_plan_post_turn_uses_post_prompt_for_exercise_wording(coordinator_agent, mock_chat_model):
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = CoordinatorPlan(pre_response=[], post_response=[], audit={"trace": "ok"})

    teacher_response = (
        "Try one more sentence using **vadret** or **varen**: " '"Jag gillar varen eftersom vadret ar bra."'
    )
    plan = await coordinator_agent.plan_post_turn(
        message="Ok",
        history=[],
        teacher_response=teacher_response,
        available_specialists=["word_keeper"],
    )

    assert plan.post_response == []
    call_args = mock_llm.ainvoke.call_args[0][0]
    assert call_args[0].content == COORDINATOR_POST_RESPONSE_PROMPT
    payload = json.loads(call_args[1].content)
    assert payload["teacher_response"] == teacher_response


@pytest.mark.anyio
async def test_plan_output_parser_exception(coordinator_agent, mock_chat_model):
    """Test plan generation with OutputParserException."""
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.side_effect = OutputParserException("Malformed JSON")

    plan = await coordinator_agent.plan(
        message="msg",
        history=[],
        current_stage="pre_response",
        available_specialists=["word_keeper"],
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
        available_specialists=["word_keeper"],
    )

    assert plan.pre_response == []
    assert plan.post_response == []
    assert plan.audit["error"] == "generic_error"
    assert "Network error" in plan.audit["details"]


@pytest.mark.anyio
async def test_plan_post_turn_passes_student_message_for_memory_change_request(coordinator_agent, mock_chat_model):
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = CoordinatorPlan(
        pre_response=[],
        post_response=[RoutingItem(name="memory_keeper", reason="Student asked to forget memory", chat_history_size=2)],
        audit={"trace": "ok"},
    )

    await coordinator_agent.plan_post_turn(
        message="Forget my old goal.",
        history=[ChatMessage(role="user", content="Earlier memory request")],
        teacher_response="Let's continue with another exercise.",
        available_specialists=["memory_keeper"],
    )

    payload = json.loads(mock_llm.ainvoke.call_args[0][0][1].content)
    assert payload["message"] == "Forget my old goal."
    assert payload["teacher_response"] == "Let's continue with another exercise."
