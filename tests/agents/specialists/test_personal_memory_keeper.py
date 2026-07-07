import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from runestone.agents.schemas import ChatMessage
from runestone.agents.specialists.base import SpecialistContext
from runestone.agents.specialists.personal_memory_keeper import (
    PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT,
    PersonalMemoryKeeperExtraction,
    PersonalMemoryKeeperFact,
    PersonalMemoryKeeperSpecialist,
)


@pytest.fixture
def specialist():
    raw_model = MagicMock()
    structured_model = MagicMock()
    structured_model.ainvoke = AsyncMock()
    raw_model.with_structured_output.return_value = structured_model
    settings = MagicMock(memory_keeper_provider="test", memory_keeper_model="test")
    with patch("runestone.agents.specialists.personal_memory_keeper.build_chat_model", return_value=raw_model):
        instance = PersonalMemoryKeeperSpecialist(settings)
    instance.structured_model = structured_model
    return instance


def context(history=None):
    return SpecialistContext(
        message="I work as a nurse.",
        history=history or [],
        user=MagicMock(id=7),
        teacher_response="Trevligt!",
    )


def service_provider(service):
    @asynccontextmanager
    async def provider():
        yield service

    return provider


def test_personal_extraction_forbids_extra_fields_and_conflicts():
    with pytest.raises(ValidationError):
        PersonalMemoryKeeperFact(key="occupation", content="Nurse", surprise=True)
    with pytest.raises(ValidationError, match="conflicting_operations"):
        PersonalMemoryKeeperExtraction(
            decision="append_fact",
            facts=[
                PersonalMemoryKeeperFact(key="occupation", content="Nurse"),
                PersonalMemoryKeeperFact(key="occupation", content="Teacher"),
            ],
        )


def test_personal_extraction_enforces_decision_limit_and_practice_rules():
    with pytest.raises(ValidationError, match="decision_list_mismatch"):
        PersonalMemoryKeeperExtraction(decision="append_fact")
    with pytest.raises(ValidationError, match="over_limit"):
        PersonalMemoryKeeperExtraction(
            decision="append_fact",
            facts=[PersonalMemoryKeeperFact(key=f"k{i}", content="x") for i in range(6)],
        )
    with pytest.raises(ValidationError, match="practice_response_with_facts"):
        PersonalMemoryKeeperExtraction(
            decision="append_fact",
            is_practice_response=True,
            facts=[PersonalMemoryKeeperFact(key="likes", content="Likes history")],
        )


def test_personal_prompt_keeps_guardrail_structure():
    assert "<role>" in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "CRITICAL RULE:" in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "<decision_tree>" in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "You are PersonalMemoryKeeper. You persist durable personal facts about a student." in (
        PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    )
    assert "never call tools and never claim that data was persisted" not in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "You never read memory." not in PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT


@pytest.mark.anyio
async def test_personal_keeper_passes_previous_teacher_message_and_appends(specialist):
    specialist.structured_model.ainvoke.return_value = PersonalMemoryKeeperExtraction(
        decision="append_fact",
        trigger_source="student",
        facts=[PersonalMemoryKeeperFact(key="occupation", content="Works as a nurse")],
    )
    service = MagicMock()
    service.append_personal_info_item = AsyncMock(return_value=MagicMock(id=1, key="occupation"))
    history = [
        ChatMessage(role="assistant", content="Tell me about yourself."),
        ChatMessage(role="user", content="Okay."),
    ]

    with patch(
        "runestone.agents.specialists.personal_memory_keeper.provide_memory_item_service",
        service_provider(service),
    ):
        result = await specialist.run(context(history))

    assert result.status == "action_taken"
    service.append_personal_info_item.assert_awaited_once_with(
        7, key="occupation", content="Works as a nurse", status="active"
    )
    assert result.artifacts["appended_item_ids"] == [1]
    messages = specialist.structured_model.ainvoke.await_args.args[0]
    payload = json.loads(messages[1].content)
    assert payload["previous_teacher_message"] == "Tell me about yourself."
    specialist.model.with_structured_output.assert_called_once_with(PersonalMemoryKeeperExtraction)


@pytest.mark.anyio
async def test_personal_keeper_rejects_practice_without_writes(specialist):
    specialist.structured_model.ainvoke.return_value = PersonalMemoryKeeperExtraction(
        decision="no_action", is_practice_response=True
    )
    result = await specialist.run(context())
    assert result.status == "no_action"
    assert result.artifacts["reason"] == "practice_response"


@pytest.mark.anyio
async def test_personal_keeper_reports_partial_failure(specialist):
    specialist.structured_model.ainvoke.return_value = PersonalMemoryKeeperExtraction(
        decision="append_fact",
        facts=[
            PersonalMemoryKeeperFact(key="occupation", content="Nurse"),
            PersonalMemoryKeeperFact(key="lives_in", content="Lives in Turku"),
        ],
    )
    service = MagicMock()
    service.append_personal_info_item = AsyncMock(
        side_effect=[MagicMock(id=11, key="occupation"), RuntimeError("private payload")]
    )
    with patch(
        "runestone.agents.specialists.personal_memory_keeper.provide_memory_item_service",
        service_provider(service),
    ):
        result = await specialist.run(context())
    assert result.status == "error"
    assert [action.status for action in result.actions] == ["success", "error"]
    assert result.artifacts["appended_count"] == 1
    assert result.artifacts["appended_item_ids"] == [11]


@pytest.mark.anyio
async def test_personal_keeper_returns_bounded_model_error(specialist):
    specialist.structured_model.ainvoke.side_effect = OutputParserException("raw private output")
    result = await specialist.run(context())
    assert result.status == "error"
    assert result.artifacts == {
        "trigger_source": "none",
        "reason": "schema_validation_failed",
        "exception_type": "OutputParserException",
    }
