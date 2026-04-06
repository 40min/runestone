"""
Tests for the TeacherAgent specialist.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from runestone.agents.schemas import ChatMessage, TeacherSideEffect
from runestone.agents.specialists.base import INFO_FOR_TEACHER_MAX_CHARS
from runestone.agents.specialists.teacher import TeacherAgent
from runestone.config import AgentLLMSettings, ReasoningLevel, Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.teacher_provider = "openrouter"
    settings.teacher_model = "test-model"
    settings.agent_persona = "default"
    settings.openrouter_api_key = "test-api-key"
    settings.openai_api_key = "test-openai-key"
    settings.allowed_origins = "http://localhost:5173"
    settings.get_agent_llm_settings.return_value = AgentLLMSettings(
        provider="openrouter",
        model="test-model",
        temperature=1.0,
        reasoning_level=ReasoningLevel.NONE,
    )
    return settings


@pytest.fixture
def mock_chat_model():
    """Create a mock LangChain chat model."""
    mock_model = MagicMock()
    return mock_model


@pytest.fixture
def teacher_agent(mock_settings, mock_chat_model):
    """Create a TeacherAgent instance with mocked dependencies."""
    with patch("runestone.agents.specialists.teacher.build_chat_model", return_value=mock_chat_model):
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
    """Test that _build_agent creates a ReAct agent with tools."""
    with patch("runestone.agents.specialists.teacher.build_chat_model", return_value=mock_chat_model):
        with patch("runestone.agents.specialists.teacher.create_agent") as mock_create_agent:
            agent = TeacherAgent(mock_settings)
            agent._build_agent()

            mock_create_agent.assert_called()
            call_kwargs = mock_create_agent.call_args[1]
            assert call_kwargs["model"] == mock_chat_model
            tools = mock_create_agent.call_args[1]["tools"]
            assert len(tools) == 4
            tool_names = {getattr(tool, "name", None) for tool in tools}
            assert {"read_memory", "search_grammar", "read_grammar_page", "read_url"} <= tool_names
            assert all(getattr(tool, "name", None) != "prioritize_words_for_learning" for tool in tools)
            assert all(getattr(tool, "name", None) != "start_student_info" for tool in tools)
            assert all(getattr(tool, "name", None) != "search_news_with_dates" for tool in tools)
            assert all(
                getattr(tool, "name", None)
                not in {
                    "upsert_memory_item",
                    "update_memory_status",
                    "update_memory_priority",
                    "promote_to_strength",
                    "delete_memory_item",
                }
                for tool in tools
            )
            assert "MEMORY PROTOCOL" in call_kwargs["system_prompt"]
            assert "TOOL TRUTHFULNESS (MANDATORY)" not in call_kwargs["system_prompt"]
            assert "Memory Writes" in call_kwargs["system_prompt"]
            assert "read-only in this phase" in call_kwargs["system_prompt"]
            assert "only say words were definitely saved" in call_kwargs["system_prompt"].lower()
            assert "WORDKEEPER SPECIALIST" in call_kwargs["system_prompt"]
            assert "The key words here are" in call_kwargs["system_prompt"]
            assert "Write a sentence with" in call_kwargs["system_prompt"]
            assert "MEMORYKEEPER POST-PHASE SIGNALS" in call_kwargs["system_prompt"]
            assert "prefer to include one short" in call_kwargs["system_prompt"]
            assert "explicit sentence" in call_kwargs["system_prompt"]
            assert "This is a recurring issue to remember" in call_kwargs["system_prompt"]
            assert "not by a tool you call directly" in call_kwargs["system_prompt"]
            assert "Topical news retrieval is handled by a pre-response specialist" in call_kwargs["system_prompt"]
            assert "Use `search_news_with_dates`" not in call_kwargs["system_prompt"]


def test_build_agent_uses_teacher_purpose(mock_settings, mock_chat_model):
    """Test teacher agent requests the teacher model profile."""
    with patch("runestone.agents.specialists.teacher.build_chat_model", return_value=mock_chat_model) as mock_build:
        with patch("runestone.agents.specialists.teacher.create_agent"):
            TeacherAgent(mock_settings)

    mock_build.assert_called_with(mock_settings, "teacher")


def test_format_pre_results_uses_info_for_teacher_only():
    formatted = TeacherAgent._format_pre_results(
        [
            {
                "name": "word_keeper",
                "result": {
                    "status": "action_taken",
                    "info_for_teacher": "Saved 2 vocabulary items.",
                    "artifacts": {"saved_words": ["ord", "fras"]},
                },
            }
        ]
    )

    assert "[PRE_RESPONSE_SPECIALISTS]" in formatted
    assert "Saved 2 vocabulary items." in formatted
    assert "saved_words" not in formatted
    assert "artifacts:" not in formatted


def test_format_pre_results_uses_no_info_fallback():
    formatted = TeacherAgent._format_pre_results(
        [
            {
                "name": "memory_keeper",
                "result": {"status": "action_taken", "info_for_teacher": "", "artifacts": {"items": ["goal"]}},
            }
        ]
    )

    assert "- memory_keeper (action_taken): no info" in formatted
    assert "items" not in formatted


def test_format_pre_results_truncates_long_summary():
    long_summary = "x" * (INFO_FOR_TEACHER_MAX_CHARS + 2000)

    formatted = TeacherAgent._format_pre_results(
        [{"name": "grammar", "result": {"status": "action_taken", "info_for_teacher": long_summary}}]
    )

    assert len(formatted) < len(long_summary)
    assert formatted.endswith("...")


def test_format_pre_results_logs_when_summary_is_truncated(caplog):
    long_summary = "x" * (INFO_FOR_TEACHER_MAX_CHARS + 2000)

    with caplog.at_level("WARNING"):
        TeacherAgent._format_pre_results(
            [{"name": "grammar", "result": {"status": "action_taken", "info_for_teacher": long_summary}}]
        )

    assert "Truncated text for pre_result:grammar" in caplog.text


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


@pytest.mark.anyio
async def test_run_with_starter_memory(teacher_agent, mock_user):
    teacher_agent.agent.ainvoke.return_value = {"messages": [AIMessage(content="Response")]}

    await teacher_agent.generate_response(
        message="msg",
        history=[],
        user=mock_user,
        starter_memory="UNTRUSTED_MEMORY_DATA (JSON).\n<memory_items_json>{}</memory_items_json>",
    )

    invoke_args = teacher_agent.agent.ainvoke.call_args[0][0]
    messages = invoke_args["messages"]
    assert any(isinstance(m, SystemMessage) and "[STARTER_MEMORY]" in m.content for m in messages)


def test_format_recent_side_effects_prefers_info_for_teacher():
    formatted = TeacherAgent._format_recent_side_effects(
        [
            TeacherSideEffect(
                name="word_keeper",
                phase="post_response",
                status="action_taken",
                info_for_teacher="Saved 2 vocabulary items.",
                artifacts={"saved_words": ["ord", "fras"]},
                routing_reason="save request",
            )
        ]
    )

    assert "[RECENT_SIDE_EFFECTS]" in formatted
    assert "Saved 2 vocabulary items." in formatted
    assert "artifacts:" not in formatted


def test_format_recent_side_effects_falls_back_to_artifacts():
    formatted = TeacherAgent._format_recent_side_effects(
        [
            TeacherSideEffect(
                name="word_keeper",
                phase="post_response",
                status="action_taken",
                info_for_teacher="",
                artifacts={"saved_words": ["ord", "fras"]},
                routing_reason="save request",
            )
        ]
    )

    assert "artifacts:" in formatted
    assert "saved_words=[ord, fras]" in formatted


def test_format_recent_side_effects_respects_budget():
    formatted = TeacherAgent._format_recent_side_effects(
        [
            TeacherSideEffect(
                name=f"specialist-{idx}",
                phase="post_response",
                status="action_taken",
                info_for_teacher="x" * 700,
                artifacts={},
                routing_reason="test",
            )
            for idx in range(10)
        ]
    )

    assert len(formatted) <= TeacherAgent.RECENT_SIDE_EFFECTS_MAX_CHARS + 200


def test_format_recent_side_effects_logs_when_limits_hit(caplog):
    items = [
        TeacherSideEffect(
            name=f"specialist-{idx}",
            phase="post_response",
            status="action_taken",
            info_for_teacher="x" * 700,
            artifacts={},
            routing_reason="test",
        )
        for idx in range(10)
    ]

    with caplog.at_level("WARNING"):
        TeacherAgent._format_recent_side_effects(items)

    assert "Truncated recent side effects from 10 to 5 items" in caplog.text
    assert "Exhausted recent side effects char budget" in caplog.text


@pytest.mark.anyio
async def test_generate_response_logs_when_history_is_truncated(teacher_agent, mock_user, caplog):
    history = [ChatMessage(role="user", content=f"m{i}") for i in range(TeacherAgent.MAX_HISTORY_MESSAGES + 3)]
    teacher_agent.agent.ainvoke.return_value = {"messages": [AIMessage(content="Response")]}

    with caplog.at_level("WARNING"):
        await teacher_agent.generate_response(message="Current msg", history=history, user=mock_user)

    assert "Truncated chat history" in caplog.text


@pytest.mark.anyio
async def test_generate_response_logs_timing_metadata(teacher_agent, mock_user, caplog):
    teacher_agent.agent.ainvoke.return_value = {"messages": [AIMessage(content="Response")]}

    with caplog.at_level("INFO"):
        await teacher_agent.generate_response(
            message="Hej",
            history=[ChatMessage(role="user", content="Tidigare")],
            user=mock_user,
            pre_results=[{"name": "memory_keeper", "result": {"status": "action_taken"}}],
            starter_memory="starter",
            recent_side_effects=[
                TeacherSideEffect(
                    name="word_keeper",
                    phase="post_response",
                    status="action_taken",
                    info_for_teacher="Saved 1 vocabulary item.",
                    artifacts={},
                    routing_reason="save request",
                )
            ],
        )

    assert "[agents:teacher] Response generated" in caplog.text
    assert "latency_ms=" in caplog.text
    assert "user_id=1" in caplog.text
    assert "history_messages=1" in caplog.text
    assert "pre_results=1" in caplog.text
    assert "starter_memory_chars=7" in caplog.text
    assert "recent_side_effects=1" in caplog.text
    assert "outcome=success" in caplog.text


@pytest.mark.anyio
async def test_generate_response_prompt_matches_fixture(teacher_agent, mock_user):
    mock_user.mother_tongue = "Spanish"
    history = [
        ChatMessage(role="user", content="Old user msg"),
        ChatMessage(
            role="assistant",
            content="Old bot msg",
            sources=[{"title": "Nyhet", "url": "https://example.com", "date": "2026-02-05"}],
        ),
    ]
    teacher_agent.agent.ainvoke.return_value = {"messages": [AIMessage(content="Response")]}

    await teacher_agent.generate_response(
        message="Please confirm what you saved yesterday.",
        history=history,
        user=mock_user,
        pre_results=[
            {
                "name": "word_keeper",
                "result": {"status": "action_taken", "info_for_teacher": "Saved 2 vocabulary items."},
            }
        ],
        recent_side_effects=[
            TeacherSideEffect(
                name="word_keeper",
                phase="post_response",
                status="action_taken",
                info_for_teacher="Saved 2 vocabulary items.",
                artifacts={"saved_words": ["ord", "fras"]},
                routing_reason="save request",
            )
        ],
    )

    invoke_args = teacher_agent.agent.ainvoke.call_args[0][0]
    actual_prompt = _serialize_messages(invoke_args["messages"])
    expected_prompt = Path("tests/agents/fixtures/teacher_prompt_full.txt").read_text(encoding="utf-8").strip()

    assert actual_prompt == expected_prompt
    assert len(actual_prompt) > 0


def test_openai_provider_configuration(mock_settings):
    """Test that OpenAI provider is configured correctly."""
    mock_settings.teacher_provider = "openai"
    mock_settings.get_agent_llm_settings.return_value = AgentLLMSettings(
        provider="openai",
        model="test-model",
        temperature=1.0,
        reasoning_level=ReasoningLevel.NONE,
    )

    with patch("runestone.agents.llm.ChatOpenAI") as mock_chat_openai:
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


def _serialize_messages(messages: list) -> str:
    blocks = []
    for message in messages:
        if isinstance(message, SystemMessage):
            role = "SYSTEM"
        elif isinstance(message, HumanMessage):
            role = "HUMAN"
        elif isinstance(message, AIMessage):
            role = "AI"
        else:
            role = message.__class__.__name__.upper()
        blocks.append(f"[{role}]\n{message.content}")
    return "\n\n".join(blocks).strip()
