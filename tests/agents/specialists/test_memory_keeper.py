import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from runestone.agents.specialists.base import SpecialistContext, SpecialistResult, parse_specialist_result
from runestone.agents.specialists.memory_keeper import MEMORY_KEEPER_SYSTEM_PROMPT, MemoryKeeperSpecialist
from runestone.agents.tools.memory import delete_memory_item


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.memory_keeper_provider = "openrouter"
    settings.memory_keeper_model = "test-model"
    return settings


@pytest.fixture
def specialist(mock_settings):
    with patch("runestone.agents.specialists.memory_keeper.build_chat_model", return_value=MagicMock()):
        with patch("runestone.agents.specialists.memory_keeper.create_agent"):
            specialist = MemoryKeeperSpecialist(mock_settings)
            specialist.agent = AsyncMock()
            return specialist


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    return user


@pytest.mark.anyio
async def test_memory_keeper_returns_parsed_specialist_result(specialist, mock_user):
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
async def test_memory_keeper_uses_current_student_message_for_payload(specialist, mock_user):
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
            message="Forget my old goal.",
            history=[],
            user=mock_user,
            teacher_response="Let's keep practicing.",
            routing_reason="student asked to forget memory",
        )
    )

    args, kwargs = specialist.agent.ainvoke.call_args
    payload_json = args[0]["messages"][0].content
    payload = json.loads(payload_json)
    assert payload["student_message"] == "Forget my old goal."
    assert "message" not in payload
    assert kwargs["context"].user == mock_user


@pytest.mark.anyio
async def test_memory_keeper_returns_error_when_agent_output_is_invalid(specialist, mock_user):
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
async def test_memory_keeper_parses_fenced_json_output(specialist, mock_user):
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
async def test_memory_keeper_parses_content_blocks_with_text_and_tool_use(specialist, mock_user):
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


def test_memory_keeper_prompt_uses_mastered_area_items_without_promotion():
    assert "Use `area_to_improve` with status `mastered`" in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Do not create a separate strength item" in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "promote_to_strength" not in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "or lower urgency for one item only when the Teacher explicitly frames it as less urgent." in (
        MEMORY_KEEPER_SYSTEM_PROMPT
    )


def test_memory_keeper_prompt_three_case_model():
    """Prompt must describe all three cases without a universal mandatory read-before-write."""
    assert "Three-Case Execution Model" in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Case A" in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Case B" in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Case C" in MEMORY_KEEPER_SYSTEM_PROMPT
    # No universal "MUST complete ALL steps" read-first mandate
    assert "Mandatory Execution Pipeline" not in MEMORY_KEEPER_SYSTEM_PROMPT
    # Case B: teacher-driven new issue must say no pre-read required
    assert "Do NOT call `read_memory` first" in MEMORY_KEEPER_SYSTEM_PROMPT
    # Case C: [memory:ID] tag path
    assert "[memory:ID]" in MEMORY_KEEPER_SYSTEM_PROMPT


def test_memory_keeper_prompt_delete_tool_in_case_a():
    """Case A (student edit) must expose delete_memory_item for forget/remove."""
    assert "`delete_memory_item` for explicit forget/remove requests" in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "delete_memory_item" in MEMORY_KEEPER_SYSTEM_PROMPT


def test_memory_keeper_prompt_rejects_misspelled_word_pollution():
    assert "Treat spelling corrections, nonexistent-word feedback" in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Do not create `area_to_improve` items for misspelled" in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "leave it to WordKeeper unless a recurring durable pattern is named" in MEMORY_KEEPER_SYSTEM_PROMPT


def test_memory_keeper_prompt_excludes_broad_startup_compaction():
    assert "Broad start-of-session consolidation, duplicate cleanup" in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "handled by a separate `memory_maintainer`" in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Never use priority changes to rebalance unrelated items or tidy the broader memory set;" in (
        MEMORY_KEEPER_SYSTEM_PROMPT
    )


def test_memory_keeper_prompt_separates_status_and_priority_roles():
    assert "Choose one write intent per item for ordinary learning signals:" in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Improvement, degradation, mastery, or outdating of an existing item" in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Explicit importance/urgency signal such as a repeated recurring error" in MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Do not use both `update_memory_status` and `update_memory_priority` on the same item" in (
        MEMORY_KEEPER_SYSTEM_PROMPT
    )


def test_memory_keeper_builds_agent_with_expected_tools(mock_settings):
    with patch("runestone.agents.specialists.memory_keeper.build_chat_model", return_value=MagicMock()):
        with patch("runestone.agents.specialists.memory_keeper.create_agent") as create_agent_mock:
            MemoryKeeperSpecialist(mock_settings)

    tool_names = [tool.name for tool in create_agent_mock.call_args.kwargs["tools"]]
    assert tool_names == [
        "read_memory",
        "upsert_memory_item",
        "update_memory_status",
        "update_memory_priority",
        "delete_memory_item",
    ]


def test_delete_memory_item_tool_is_accessible():
    """delete_memory_item must exist at the tool layer and be wired into MemoryKeeper."""
    assert delete_memory_item.name == "delete_memory_item"


@pytest.mark.anyio
async def test_memory_keeper_passes_recursion_limit(specialist, mock_user):
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
            message="Forget my old goal.",
            history=[],
            user=mock_user,
            teacher_response="Let's keep practicing.",
            routing_reason="student asked to forget memory",
        )
    )

    _, kwargs = specialist.agent.ainvoke.call_args
    assert "config" in kwargs
    assert kwargs["config"] == {"recursion_limit": 50}
