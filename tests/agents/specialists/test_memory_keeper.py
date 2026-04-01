from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from runestone.agents.specialists.base import SpecialistContext
from runestone.agents.specialists.memory_keeper import MemoryKeeperSpecialist


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
                    '"artifacts":{"trigger_source":"teacher_response","summary":"updated",'
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
    assert result.artifacts["trigger_source"] == "teacher_response"


@pytest.mark.anyio
async def test_memory_keeper_uses_current_student_message_for_payload(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    '{"status":"no_action","actions":[],"info_for_teacher":"",'
                    '"artifacts":{"trigger_source":"student_message","summary":"noop","notes":[]}}'
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
    assert "Forget my old goal." in args[0]["messages"][0].content
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
