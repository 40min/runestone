import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from runestone.agents.schemas import LearningMemorySignal
from runestone.agents.specialists.base import SpecialistContext
from runestone.agents.specialists.learning_memory_keeper import (
    LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT,
    LearningMemoryCreate,
    LearningMemoryKeeperExtraction,
    LearningMemoryKeeperSpecialist,
    LearningMemoryMutation,
    parse_learning_memory_ids,
)
from runestone.api.memory_item_schemas import MemoryCategory, MemorySortBy, SortDirection


@pytest.fixture
def specialist():
    raw_model = MagicMock()
    structured_model = MagicMock()
    structured_model.ainvoke = AsyncMock()
    raw_model.with_structured_output.return_value = structured_model
    settings = MagicMock(memory_keeper_provider="test", memory_keeper_model="test")
    with patch("runestone.agents.specialists.learning_memory_keeper.build_chat_model", return_value=raw_model):
        instance = LearningMemoryKeeperSpecialist(settings)
    instance.structured_model = structured_model
    return instance


def context(teacher_response="Good progress.", learning_memory_signals=None):
    return SpecialistContext(
        message="Okay",
        history=[],
        user=MagicMock(id=7),
        teacher_response=teacher_response,
        learning_memory_signals=learning_memory_signals or [],
    )


def item(item_id=3, user_id=7, category="area_to_improve"):
    return MagicMock(
        id=item_id,
        user_id=user_id,
        category=category,
        key="articles",
        content="Article selection",
        status="struggling",
        priority=2,
    )


def service_provider(service):
    @asynccontextmanager
    async def provider():
        yield service

    return provider


def test_memory_id_parser_deduplicates():
    assert parse_learning_memory_ids(
        [
            LearningMemorySignal(
                signal_type="improving",
                summary="Improving with articles.",
                memory_id=3,
            ),
            LearningMemorySignal(
                signal_type="mastered",
                summary="Mastered verb order.",
                memory_id=4,
            ),
            LearningMemorySignal(
                signal_type="improving",
                summary="Improving with articles.",
                memory_id=3,
            ),
        ]
    ) == [3, 4]


def test_learning_models_reject_invalid_and_conflicting_operations():
    with pytest.raises(ValidationError):
        LearningMemoryMutation(target_id="3", status="mastered")
    with pytest.raises(ValidationError, match="delete_not_exclusive"):
        LearningMemoryMutation(target_id=3, delete=True, status="mastered")
    with pytest.raises(ValidationError, match="empty_mutation"):
        LearningMemoryMutation(target_id=3)
    with pytest.raises(ValidationError, match="conflicting_operations"):
        LearningMemoryKeeperExtraction(
            decision="update_memory",
            creates=[
                LearningMemoryCreate(key=" articles ", content="First"),
                LearningMemoryCreate(key="articles", content="Second"),
            ],
        )
    with pytest.raises(ValidationError, match="over_limit"):
        LearningMemoryKeeperExtraction(
            decision="update_memory",
            creates=[LearningMemoryCreate(key=f"k{i}", content="x") for i in range(4)],
        )


def test_learning_prompt_keeps_decision_structure():
    assert "<role>" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "<fast_path>" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "<decision_tree>" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "<conservative_bias>" in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT
    assert "never call tools and never claim that data was persisted" not in LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT


@pytest.mark.anyio
async def test_tagged_path_loads_only_tags_and_executes_in_order(specialist):
    specialist.structured_model.ainvoke.return_value = LearningMemoryKeeperExtraction(
        decision="update_memory",
        trigger_source="teacher",
        mutations=[LearningMemoryMutation(target_id=3, status="improving", content="Better articles", priority=4)],
    )
    service = MagicMock()
    service.get_item_by_id = AsyncMock(return_value=item())
    service.list_memory_items = AsyncMock()
    service.update_item_status = AsyncMock()
    service.update_item_content_in_category = AsyncMock()
    service.update_item_priority = AsyncMock()
    manager = MagicMock()
    manager.attach_mock(service.update_item_status, "status")
    manager.attach_mock(service.update_item_content_in_category, "content")
    manager.attach_mock(service.update_item_priority, "priority")

    with patch(
        "runestone.agents.specialists.learning_memory_keeper.provide_memory_item_service",
        service_provider(service),
    ):
        result = await specialist.run(
            context(
                learning_memory_signals=[
                    LearningMemorySignal(
                        signal_type="improving",
                        summary="The student is improving with articles.",
                        memory_id=3,
                    )
                ]
            )
        )

    assert result.status == "action_taken"
    service.list_memory_items.assert_not_awaited()
    assert manager.mock_calls == [
        call.status(3, "improving", 7),
        call.content(3, MemoryCategory.AREA_TO_IMPROVE, "Better articles", 7),
        call.priority(3, 4, 7),
    ]
    assert result.artifacts["changed_item_ids"] == [3]
    assert result.artifacts["updated_item_ids"] == [3]
    assert result.artifacts["upserted_item_ids"] == []
    assert result.artifacts["deleted_item_ids"] == []


@pytest.mark.anyio
async def test_untagged_path_supplies_bounded_allowlist(specialist):
    specialist.structured_model.ainvoke.return_value = LearningMemoryKeeperExtraction(decision="no_action")
    service = MagicMock()
    service.list_memory_items = AsyncMock(return_value=[item()])
    with patch(
        "runestone.agents.specialists.learning_memory_keeper.provide_memory_item_service",
        service_provider(service),
    ):
        result = await specialist.run(context())
    assert result.status == "no_action"
    service.list_memory_items.assert_awaited_once_with(
        7,
        category=MemoryCategory.AREA_TO_IMPROVE,
        statuses=["struggling", "improving", "mastered"],
        sort_by=MemorySortBy.UPDATED_AT,
        sort_direction=SortDirection.DESC,
        limit=100,
    )
    messages = specialist.structured_model.ainvoke.await_args.args[0]
    payload = json.loads(messages[1].content)
    assert payload["existing_targets"][0]["id"] == 3
    assert payload["learning_memory_signals"] == []


@pytest.mark.anyio
async def test_stale_target_id_is_terminal_without_model_or_general_read(specialist):
    service = MagicMock()
    service.get_item_by_id = AsyncMock(return_value=None)
    service.list_memory_items = AsyncMock()
    with patch(
        "runestone.agents.specialists.learning_memory_keeper.provide_memory_item_service",
        service_provider(service),
    ):
        result = await specialist.run(
            context(
                learning_memory_signals=[
                    LearningMemorySignal(
                        signal_type="mastered",
                        summary="The student has now mastered articles.",
                        memory_id=99,
                    )
                ]
            )
        )
    assert result.status == "no_action"
    assert result.artifacts["reason"] == "stale_target"
    specialist.structured_model.ainvoke.assert_not_awaited()
    service.list_memory_items.assert_not_awaited()


@pytest.mark.anyio
async def test_non_allowlisted_target_rejects_all_writes(specialist):
    specialist.structured_model.ainvoke.return_value = LearningMemoryKeeperExtraction(
        decision="update_memory", mutations=[LearningMemoryMutation(target_id=99, status="mastered")]
    )
    service = MagicMock()
    service.list_memory_items = AsyncMock(return_value=[item()])
    with patch(
        "runestone.agents.specialists.learning_memory_keeper.provide_memory_item_service",
        service_provider(service),
    ):
        result = await specialist.run(context())
    assert result.status == "error"
    assert result.artifacts["reason"] == "target_not_allowed"
    service.update_item_status.assert_not_called()


@pytest.mark.anyio
async def test_upsert_and_partial_failure_report_actual_actions(specialist):
    specialist.structured_model.ainvoke.return_value = LearningMemoryKeeperExtraction(
        decision="update_memory",
        creates=[
            LearningMemoryCreate(key="articles", content="Recurring issue"),
            LearningMemoryCreate(key="word order", content="Recurring issue"),
        ],
    )
    service = MagicMock()
    service.list_memory_items = AsyncMock(return_value=[])
    service.upsert_memory_item = AsyncMock(side_effect=[item(), RuntimeError("private payload")])
    with patch(
        "runestone.agents.specialists.learning_memory_keeper.provide_memory_item_service",
        service_provider(service),
    ):
        result = await specialist.run(context())
    assert result.status == "error"
    assert [action.status for action in result.actions] == ["success", "error"]
    assert result.artifacts["upserted"] == 1
    assert result.artifacts["changed_item_ids"] == [3]
    assert result.artifacts["upserted_item_ids"] == [3]
    assert service.upsert_memory_item.await_count == 2


@pytest.mark.anyio
async def test_exact_key_recurrence_is_reported_as_upsert_not_creation(specialist):
    specialist.structured_model.ainvoke.return_value = LearningMemoryKeeperExtraction(
        decision="update_memory",
        creates=[LearningMemoryCreate(key="articles", content="Recurring issue", status="struggling")],
    )
    existing = item()
    existing.status = "mastered"
    service = MagicMock()
    service.list_memory_items = AsyncMock(return_value=[existing])
    service.upsert_memory_item = AsyncMock(return_value=item())
    with patch(
        "runestone.agents.specialists.learning_memory_keeper.provide_memory_item_service",
        service_provider(service),
    ):
        result = await specialist.run(context())

    assert result.status == "action_taken"
    assert result.artifacts["upserted"] == 1
    assert result.artifacts["changed_item_ids"] == [3]
    assert result.artifacts["upserted_item_ids"] == [3]
    assert "created" not in result.artifacts
    assert result.actions[0].summary == "Upserted articles"


@pytest.mark.anyio
async def test_learning_keeper_returns_bounded_schema_error(specialist):
    specialist.structured_model.ainvoke.side_effect = OutputParserException("raw private output")
    service = MagicMock()
    service.list_memory_items = AsyncMock(return_value=[])
    with patch(
        "runestone.agents.specialists.learning_memory_keeper.provide_memory_item_service",
        service_provider(service),
    ):
        result = await specialist.run(context())
    assert result.status == "error"
    assert result.artifacts["reason"] == "schema_validation_failed"
