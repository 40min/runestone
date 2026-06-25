import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain.agents.middleware import ModelRetryMiddleware
from langchain_core.messages import AIMessage

from runestone.agents.schemas import ChatMessage
from runestone.agents.specialists.base import SpecialistContext
from runestone.agents.specialists.personal_memory_keeper import (
    PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT,
    PersonalMemoryKeeperSpecialist,
)
from runestone.constants import RECURSION_LIMIT_PERSONAL_MEMORY_KEEPER


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.memory_keeper_provider = "openrouter"
    settings.memory_keeper_model = "test-model"
    return settings


@pytest.fixture
def specialist(mock_settings):
    with patch("runestone.agents.specialists.personal_memory_keeper.build_chat_model", return_value=MagicMock()):
        with patch("runestone.agents.specialists.personal_memory_keeper.create_agent"):
            specialist = PersonalMemoryKeeperSpecialist(mock_settings)
            specialist.agent = AsyncMock()
            return specialist


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    return user


@pytest.mark.anyio
async def test_personal_memory_keeper_returns_parsed_specialist_result(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    '{"status":"action_taken","actions":[{"tool":"append_personal_info_item","status":"success",'
                    '"summary":"Appended personal info"}],"info_for_teacher":"Appended 1 personal info item.",'
                    '"artifacts":{"trigger_source":"student","summary":"appended",'
                    '"notes":["native_language added"]}}'
                )
            )
        ]
    }

    result = await specialist.run(
        SpecialistContext(
            message="My native language is Finnish",
            history=[],
            user=mock_user,
            teacher_response="Bra!",
            routing_reason="student stated personal fact",
        )
    )

    assert result.status == "action_taken"
    assert result.actions[0].tool == "append_personal_info_item"
    assert result.artifacts["trigger_source"] == "student"


@pytest.mark.anyio
async def test_personal_memory_keeper_uses_current_student_message_for_payload(specialist, mock_user):
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
            message="I work as a nurse.",
            history=[],
            user=mock_user,
            teacher_response="Interesting job.",
            routing_reason="student stated personal fact",
        )
    )

    args, kwargs = specialist.agent.ainvoke.call_args
    payload_json = args[0]["messages"][0].content
    payload = json.loads(payload_json)
    assert payload == {
        "student_message": "I work as a nurse.",
        "teacher_response": "Interesting job.",
        "previous_teacher_message": None,
    }
    assert payload["student_message"] == "I work as a nurse."
    assert "message" not in payload
    assert kwargs["context"].user == mock_user


@pytest.mark.anyio
async def test_personal_memory_keeper_extracts_previous_teacher_message(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    '{"status":"no_action","actions":[],"info_for_teacher":"",'
                    '"artifacts":{"trigger_source":"none","summary":"noop","notes":[]}}'
                )
            )
        ]
    }

    await specialist.run(
        SpecialistContext(
            message="I like history.",
            history=[
                ChatMessage(
                    role="assistant", content="Write a sentence starting with 'Jag är...' or about what you like."
                ),
                ChatMessage(role="user", content="Jag gillar historia."),
            ],
            user=mock_user,
            teacher_response="Bra jobbat!",
            routing_reason="student stated personal fact",
        )
    )

    args, kwargs = specialist.agent.ainvoke.call_args
    payload_json = args[0]["messages"][0].content
    payload = json.loads(payload_json)
    assert payload == {
        "student_message": "I like history.",
        "teacher_response": "Bra jobbat!",
        "previous_teacher_message": "Write a sentence starting with 'Jag är...' or about what you like.",
    }


@pytest.mark.anyio
async def test_personal_memory_keeper_returns_error_when_agent_output_is_invalid(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {"messages": [AIMessage(content="not json")]}

    result = await specialist.run(
        SpecialistContext(
            message="My name is Bob.",
            history=[],
            user=mock_user,
            teacher_response="Hi Bob.",
            routing_reason="student stated personal fact",
        )
    )

    assert result.status == "error"
    assert result.artifacts["summary"] == "invalid_agent_output"


def test_personal_memory_keeper_prompt_structure():
    assert "PersonalMemoryKeeper" in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "append_personal_info_item" in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "You never read memory." in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "native_language" in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "lives_in" in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "occupation" in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "learning_goal" in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert 'status="correction"' in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert 'status="outdated"' in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Do NOT act on (not durable personal facts):" in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "I feel tired today" in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "Maybe I should study more" in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT


def test_personal_memory_keeper_builds_agent_with_expected_tools(mock_settings):
    with patch("runestone.agents.specialists.personal_memory_keeper.build_chat_model", return_value=MagicMock()):
        with patch("runestone.agents.specialists.personal_memory_keeper.create_agent") as create_agent_mock:
            PersonalMemoryKeeperSpecialist(mock_settings)

    tool_names = [tool.name for tool in create_agent_mock.call_args.kwargs["tools"]]
    assert tool_names == ["append_personal_info_item"]
    middleware = create_agent_mock.call_args.kwargs["middleware"]
    assert len(middleware) == 1
    assert isinstance(middleware[0], ModelRetryMiddleware)
    assert middleware[0].max_retries == 2


@pytest.mark.anyio
async def test_personal_memory_keeper_passes_recursion_limit(specialist, mock_user):
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
            message="I live in Stockholm.",
            history=[],
            user=mock_user,
            teacher_response="Välkommen!",
            routing_reason="student stated personal fact",
        )
    )

    _, kwargs = specialist.agent.ainvoke.call_args
    assert "config" in kwargs
    assert kwargs["config"] == {"recursion_limit": RECURSION_LIMIT_PERSONAL_MEMORY_KEEPER}
