import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain.agents.middleware import ModelRetryMiddleware
from langchain_core.messages import AIMessage

from runestone.agents.specialists.base import SpecialistContext, SpecialistResult, parse_specialist_result
from runestone.agents.specialists.learning_memory_keeper import (
    LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT,
    LearningMemoryKeeperSpecialist,
)
from runestone.agents.tools.memory import delete_memory_item, update_memory_item_content
from runestone.constants import RECURSION_LIMIT_LEARNING_MEMORY_KEEPER


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.memory_keeper_provider = "openrouter"
    settings.memory_keeper_model = "test-model"
    return settings


@pytest.fixture
def specialist(mock_settings):
    with patch("runestone.agents.specialists.learning_memory_keeper.build_chat_model", return_value=MagicMock()):
        with patch("runestone.agents.specialists.learning_memory_keeper.create_agent"):
            specialist = LearningMemoryKeeperSpecialist(mock_settings)
            specialist.agent = AsyncMock()
            return specialist


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    return user


@pytest.mark.anyio
async def test_learning_memory_keeper_returns_parsed_specialist_result(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    '{"status":"action_taken","actions":[{"tool":"update_memory_status","status":"success",'
                    '"summary":"Marked topic as improving"}],"info_for_teacher":"Updated 1 memory item.",'
                    '"artifacts":{"trigger_source":"teacher","summary":"updated",'
                    '"notes":["status changed"]}}'
                )
            )
        ]
    }

    result = await specialist.run(
        SpecialistContext(
            message="Ok",
            history=[],
            user=mock_user,
            teacher_response="You have clearly improved with articles.",
            routing_reason="teacher signaled improvement",
        )
    )

    assert result.status == "action_taken"
    assert result.actions[0].tool == "update_memory_status"
    assert result.artifacts["trigger_source"] == "teacher"


@pytest.mark.anyio
async def test_learning_memory_keeper_uses_current_student_message_for_payload(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    '{"status":"no_action","actions":[],"info_for_teacher":"",'
                    '"artifacts":{"trigger_source":"student","summary":"noop","notes":[]}}'
                )
            )
        ]
    }

    await specialist.run(
        SpecialistContext(
            message="Forget my old learning topic.",
            history=[],
            user=mock_user,
            teacher_response="Let's keep practicing.",
            routing_reason="student asked to forget memory",
        )
    )

    args, kwargs = specialist.agent.ainvoke.call_args
    payload_json = args[0]["messages"][0].content
    payload = json.loads(payload_json)
    assert payload == {
        "student_message": "Forget my old learning topic.",
        "teacher_response": "Let's keep practicing.",
    }
    assert payload["student_message"] == "Forget my old learning topic."
    assert "message" not in payload
    assert kwargs["context"].user == mock_user


@pytest.mark.anyio
async def test_learning_memory_keeper_returns_error_when_agent_output_is_invalid(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {"messages": [AIMessage(content="not json")]}

    result = await specialist.run(
        SpecialistContext(
            message="Remember this.",
            history=[],
            user=mock_user,
            teacher_response="The key issue is article usage.",
            routing_reason="teacher signaled durable issue",
        )
    )

    assert result.status == "error"
    assert result.artifacts["summary"] == "invalid_agent_output"


@pytest.mark.anyio
async def test_learning_memory_keeper_parses_fenced_json_output(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    "```json\n"
                    '{"status":"no_action","actions":[],"info_for_teacher":"",'
                    '"artifacts":{"trigger_source":"none","summary":"noop","notes":[]}}'
                    "\n```"
                )
            )
        ]
    }

    result = await specialist.run(
        SpecialistContext(
            message="Ok",
            history=[],
            user=mock_user,
            teacher_response="Good effort.",
            routing_reason="no durable signal",
        )
    )

    assert result.status == "no_action"
    assert result.artifacts["trigger_source"] == "none"


@pytest.mark.anyio
async def test_learning_memory_keeper_parses_content_blocks_with_text_and_tool_use(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=[
                    {
                        "type": "text",
                        "text": (
                            "```json\n"
                            '{"status":"no_action","actions":[],"info_for_teacher":"",'
                            '"artifacts":{"trigger_source":"none","summary":"noop","notes":[]}}'
                            "\n```"
                        ),
                    },
                    {"type": "tool_use", "name": "noop", "input": {}},
                ]
            )
        ]
    }

    result = await specialist.run(
        SpecialistContext(
            message="Ok",
            history=[],
            user=mock_user,
            teacher_response="Good effort.",
            routing_reason="no durable signal",
        )
    )

    assert result.status == "no_action"
    assert result.artifacts["summary"] == "noop"


def test_parse_specialist_result_prefers_structured_response():
    structured = SpecialistResult(
        status="action_taken",
        actions=[],
        info_for_teacher="Updated memory.",
        artifacts={"trigger_source": "teacher", "summary": "updated", "notes": []},
    )

    parsed = parse_specialist_result({"structured_response": structured, "messages": []})

    assert parsed == structured


def test_learning_memory_keeper_prompt_uses_mastered_area_items_without_promotion():
    assert "Use `area_to_improve` with status `mastered`" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Do not create a separate strength item" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "promote_to_strength" not in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT


def test_learning_memory_keeper_prompt_three_case_model():
    """Prompt must describe all three cases without a universal mandatory read-before-write."""
    assert "Case A" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Case B" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Case C" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Do NOT call read_areas_to_improve" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "[memory:area_to_improve:<id>]" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "forget this old learning topic" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "delete_memory_item" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT


def test_learning_memory_keeper_prompt_rejects_misspelled_word_pollution():
    assert (
        "A routine one-off correction, a typo, a spelling slip, or a vocabulary gap alone is NOT enough"
        in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    )
    assert "durable learning issue" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT


def test_learning_memory_keeper_prompt_separates_status_and_priority_roles():
    assert "Do not use both update_memory_status and update_memory_priority" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert (
        "Use update_memory_priority only for the single item directly implicated"
        in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    )


def test_learning_memory_keeper_builds_agent_with_expected_tools(mock_settings):
    with patch("runestone.agents.specialists.learning_memory_keeper.build_chat_model", return_value=MagicMock()):
        with patch("runestone.agents.specialists.learning_memory_keeper.create_agent") as create_agent_mock:
            LearningMemoryKeeperSpecialist(mock_settings)

    tool_names = [tool.name for tool in create_agent_mock.call_args.kwargs["tools"]]
    assert tool_names == [
        "read_areas_to_improve",
        "upsert_memory_item",
        "update_memory_item_content",
        "update_memory_status",
        "update_memory_priority",
        "delete_memory_item",
    ]
    middleware = create_agent_mock.call_args.kwargs["middleware"]
    assert len(middleware) == 4
    assert isinstance(middleware[0], ModelRetryMiddleware)
    assert middleware[0].max_retries == 3

    limit_by_tool = {m.tool_name: m for m in middleware[1:]}
    for tool_name in ("read_areas_to_improve", "update_memory_status", "update_memory_item_content"):
        assert tool_name in limit_by_tool, f"Missing ToolCallLimitMiddleware for {tool_name}"
        m = limit_by_tool[tool_name]
        assert m.run_limit == 1
        assert m.exit_behavior == "end"


def test_update_memory_item_content_tool_is_accessible():
    """update_memory_item_content must exist at the tool layer and be wired into MemoryKeeper."""
    assert update_memory_item_content.name == "update_memory_item_content"


def test_delete_memory_item_tool_is_accessible():
    """delete_memory_item must exist at the tool layer and be wired into LearningMemoryKeeper."""
    assert delete_memory_item.name == "delete_memory_item"


@pytest.mark.anyio
async def test_learning_memory_keeper_passes_recursion_limit(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    '{"status":"no_action","actions":[],"info_for_teacher":"",'
                    '"artifacts":{"trigger_source":"student","summary":"noop","notes":[]}}'
                )
            )
        ]
    }

    await specialist.run(
        SpecialistContext(
            message="Forget my old learning topic.",
            history=[],
            user=mock_user,
            teacher_response="Let's keep practicing.",
            routing_reason="student asked to forget memory",
        )
    )

    _, kwargs = specialist.agent.ainvoke.call_args
    assert "config" in kwargs
    assert kwargs["config"] == {"recursion_limit": RECURSION_LIMIT_LEARNING_MEMORY_KEEPER}


def test_learning_memory_keeper_prompt_terminal_noop_on_not_found():
    """Prompt must make missing-item failures a terminal stop, not a fallback."""
    assert "terminal_no_ops" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Memory item with id ... not found" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "content update category mismatch" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Do NOT retry, create replacements, or continue." in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
