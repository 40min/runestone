from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy.exc import IntegrityError

from runestone.agents.specialists.base import SpecialistContext
from runestone.agents.specialists.memory_maintainer import MEMORY_MAINTAINER_SYSTEM_PROMPT, MemoryMaintainerSpecialist
from runestone.agents.tools.memory_maintainer import (
    _PENDING_MERGE_DELETIONS,
    PendingMergePlan,
    maintainer_delete_memory_item,
    maintainer_insert_memory_item,
    maintainer_update_memory_priority,
)


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.memory_maintainer_provider = "openrouter"
    settings.memory_maintainer_model = "test-model"
    return settings


@pytest.fixture
def specialist(mock_settings):
    with patch("runestone.agents.specialists.memory_maintainer.build_chat_model", return_value=MagicMock()) as build:
        with patch("runestone.agents.specialists.memory_maintainer.create_agent"):
            specialist = MemoryMaintainerSpecialist(mock_settings)
            specialist.agent = AsyncMock()
            specialist._build_chat_model_call = build.call_args
            return specialist


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    return user


@pytest.fixture(autouse=True)
def clear_pending_merge_registry():
    _PENDING_MERGE_DELETIONS.clear()
    yield
    _PENDING_MERGE_DELETIONS.clear()


@pytest.mark.anyio
async def test_memory_maintainer_returns_parsed_specialist_result(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    '{"status":"action_taken","actions":[{"tool":"delete_memory_item","status":"success",'
                    '"summary":"Deleted duplicates"}],'
                    '"artifacts":{"maintenance_type":"chat_reset_memory_maintenance",'
                    '"scope":{"category":"area_to_improve",'
                    '"statuses":["struggling","improving"]},"reviewed_item_count":4,"merged_groups":[],'
                    '"priority_updates":[],"summary":"merged","no_change_reason":null}}'
                )
            )
        ]
    }

    result = await specialist.run(
        SpecialistContext(
            message="start_new_chat",
            history=[],
            user=mock_user,
            routing_reason="new_chat_session_started",
        )
    )

    assert result.status == "action_taken"
    assert result.actions[0].tool == "delete_memory_item"
    assert result.artifacts["maintenance_type"] == "chat_reset_memory_maintenance"


@pytest.mark.anyio
async def test_memory_maintainer_uses_chat_reset_prompt(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    '{"status":"no_action","actions":[],'
                    '"artifacts":{"maintenance_type":"chat_reset_memory_maintenance",'
                    '"scope":{"category":"area_to_improve",'
                    '"statuses":["struggling","improving"]},"reviewed_item_count":0,"merged_groups":[],'
                    '"priority_updates":[],"summary":"noop","no_change_reason":"already clean"}}'
                )
            )
        ]
    }

    await specialist.run(
        SpecialistContext(
            message="start_new_chat",
            history=[],
            user=mock_user,
            routing_reason="new_chat_session_started",
        )
    )

    args, kwargs = specialist.agent.ainvoke.call_args
    prompt = args[0]["messages"][0].content
    assert prompt.startswith("Run the routine chat-reset memory maintenance check.")
    assert "Use 'English' for memory item content." in prompt
    assert "fall back to English content" in prompt
    assert "Keep all memory item keys in English only." in prompt
    assert kwargs["context"].user == mock_user


@pytest.mark.anyio
async def test_memory_maintainer_uses_user_mother_tongue_in_prompt(specialist):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    '{"status":"no_action","actions":[],'
                    '"artifacts":{"maintenance_type":"chat_reset_memory_maintenance",'
                    '"scope":{"category":"area_to_improve",'
                    '"statuses":["struggling","improving"]},"reviewed_item_count":0,"merged_groups":[],'
                    '"priority_updates":[],"summary":"noop","no_change_reason":"already clean"}}'
                )
            )
        ]
    }

    user = SimpleNamespace(id=7, mother_tongue="Finnish")
    await specialist.run(
        SpecialistContext(
            message="start_new_chat",
            history=[],
            user=user,
            routing_reason="new_chat_session_started",
        )
    )

    args, _kwargs = specialist.agent.ainvoke.call_args
    prompt = args[0]["messages"][0].content
    assert "Use 'Finnish' for memory item content." in prompt
    assert "Keep all memory item keys in English only." in prompt


@pytest.mark.anyio
async def test_memory_maintainer_returns_error_when_agent_output_is_invalid(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {"messages": [AIMessage(content="not json")]}

    result = await specialist.run(
        SpecialistContext(
            message="start_new_chat",
            history=[],
            user=mock_user,
            routing_reason="new_chat_session_started",
        )
    )

    assert result.status == "error"
    assert result.artifacts["summary"] == "invalid_agent_output"


@pytest.mark.anyio
async def test_memory_maintainer_clears_pending_merge_state_after_failed_run(specialist, mock_user):
    _PENDING_MERGE_DELETIONS[mock_user.id] = PendingMergePlan(consolidated_item_id=10, remaining_delete_ids={4, 5})
    specialist.agent.ainvoke.return_value = {"messages": [AIMessage(content="not json")]}

    await specialist.run(
        SpecialistContext(
            message="start_new_chat",
            history=[],
            user=mock_user,
            routing_reason="new_chat_session_started",
        )
    )

    assert mock_user.id not in _PENDING_MERGE_DELETIONS


@pytest.mark.anyio
async def test_memory_maintainer_parses_fenced_json_output(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    "```json\n"
                    '{"status":"no_action","actions":[],'
                    '"artifacts":{"maintenance_type":"chat_reset_memory_maintenance",'
                    '"scope":{"category":"area_to_improve",'
                    '"statuses":["struggling","improving"]},"reviewed_item_count":0,"merged_groups":[],'
                    '"priority_updates":[],"summary":"noop","no_change_reason":"already clean"}}'
                    "\n```"
                )
            )
        ]
    }

    result = await specialist.run(
        SpecialistContext(
            message="start_new_chat",
            history=[],
            user=mock_user,
            routing_reason="new_chat_session_started",
        )
    )

    assert result.status == "no_action"
    assert result.artifacts["no_change_reason"] == "already clean"


def test_memory_maintainer_prompt_defines_expected_scope_and_tools():
    assert "The default outcome of this task is NO ACTION." in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "Merging is the exception," in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "not the goal." in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "When in doubt, do not merge." in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "category `area_to_improve` with status" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "`struggling` or `improving`" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert (
        "The content target language is provided in the runtime instruction message." in MEMORY_MAINTAINER_SYSTEM_PROMPT
    )
    assert "Always keep memory item keys in English." in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "fall back to English" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "Keep Swedish example words/phrases as-is" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "- maintainer_delete_memory_item" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "- maintainer_update_memory_priority" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "key must be a new versioned key" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "never reuse any original key from the merged items" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "never delete that consolidated item id" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "maintainer_insert_memory_item" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "Do NOT create broad catch-all items" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "A merged item must still point to one coherent topic" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "vocabulary confusion vs spelling" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "time expressions vs V2 word order" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert 'one giant item like "Struggles with Swedish grammar and vocabulary"' in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "Bad merge example (prose form" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "Prose paragraph form does not change the violation." in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "five distinct grammar topics and must be kept separate" in MEMORY_MAINTAINER_SYSTEM_PROMPT
    assert "If you feel tempted to summarize several different weaknesses into one compact" in (
        MEMORY_MAINTAINER_SYSTEM_PROMPT
    )


def test_memory_maintainer_builds_agent_with_expected_tools(mock_settings):
    with patch("runestone.agents.specialists.memory_maintainer.build_chat_model", return_value=MagicMock()):
        with patch("runestone.agents.specialists.memory_maintainer.create_agent") as create_agent_mock:
            MemoryMaintainerSpecialist(mock_settings)

    tool_names = [tool.name for tool in create_agent_mock.call_args.kwargs["tools"]]
    assert tool_names == [
        "maintainer_read_memory",
        "maintainer_insert_memory_item",
        "maintainer_delete_memory_item",
        "maintainer_update_memory_priority",
    ]


def test_memory_maintainer_uses_dedicated_agent_settings(mock_settings):
    with patch("runestone.agents.specialists.memory_maintainer.build_chat_model", return_value=MagicMock()) as build:
        with patch("runestone.agents.specialists.memory_maintainer.create_agent"):
            MemoryMaintainerSpecialist(mock_settings)

    build.assert_called_once_with(
        mock_settings,
        "memory_maintainer",
        timeout_seconds=MemoryMaintainerSpecialist.MODEL_TIMEOUT_SECONDS,
    )


@pytest.mark.anyio
async def test_maintainer_delete_rejects_personal_info_item():
    user = SimpleNamespace(id=42)
    out_of_scope_item = SimpleNamespace(id=7, user_id=42, category="personal_info", status="active")
    mock_service = MagicMock()
    mock_service.repo.get_by_id = AsyncMock(return_value=out_of_scope_item)
    mock_service.delete_item = AsyncMock()
    _PENDING_MERGE_DELETIONS[user.id] = PendingMergePlan(consolidated_item_id=99, remaining_delete_ids={7})

    with patch("runestone.agents.tools.memory_maintainer.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock(return_value=False)

        runtime = SimpleNamespace(context=SimpleNamespace(user=user))
        result = await maintainer_delete_memory_item.coroutine(runtime, delete=SimpleNamespace(item_id=7))

    assert "out of memory maintainer scope" in result
    mock_service.delete_item.assert_not_awaited()


@pytest.mark.anyio
async def test_maintainer_delete_requires_active_consolidation_ids():
    user = SimpleNamespace(id=42)
    runtime = SimpleNamespace(context=SimpleNamespace(user=user))

    result = await maintainer_delete_memory_item.coroutine(runtime, delete=SimpleNamespace(item_id=7))

    assert "Delete is only allowed for ids listed in replaced_item_ids" in result


@pytest.mark.anyio
async def test_maintainer_priority_update_rejects_mastered_item():
    user = SimpleNamespace(id=42)
    out_of_scope_item = SimpleNamespace(id=9, user_id=42, category="area_to_improve", status="mastered")
    mock_service = MagicMock()
    mock_service.repo.get_by_id = AsyncMock(return_value=out_of_scope_item)
    mock_service.update_item_priority = AsyncMock()

    with patch("runestone.agents.tools.memory_maintainer.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock(return_value=False)

        runtime = SimpleNamespace(context=SimpleNamespace(user=user))
        result = await maintainer_update_memory_priority.coroutine(
            runtime,
            update=SimpleNamespace(item_id=9, priority=1),
        )

    assert "out of memory maintainer scope" in result
    mock_service.update_item_priority.assert_not_awaited()


@pytest.mark.anyio
async def test_maintainer_insert_rejects_duplicate_key_on_db_create():
    user = SimpleNamespace(id=42)
    mock_service = MagicMock()
    duplicate_exc = IntegrityError("duplicate", params={}, orig=Exception("unique_violation"))
    mock_service.repo.create = AsyncMock(side_effect=duplicate_exc)
    mock_service.repo.rollback = AsyncMock()
    mock_service.repo.db = SimpleNamespace(rollback=AsyncMock())
    mock_service._validate_status = MagicMock()
    mock_service._utc_now = MagicMock(return_value="now")

    with patch("runestone.agents.tools.memory_maintainer.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock(return_value=False)

        runtime = SimpleNamespace(context=SimpleNamespace(user=user))
        item = SimpleNamespace(
            category="area_to_improve",
            key="word_order_v2",
            content="Consolidated item",
            status="struggling",
            priority=2,
            replaced_item_ids=[],
        )
        result = await maintainer_insert_memory_item.coroutine(runtime, item=item)

    assert "Insert failed due to duplicate key" in result
    mock_service.repo.db.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_maintainer_insert_rejects_cross_status_replacements():
    user = SimpleNamespace(id=42)
    item_1 = SimpleNamespace(id=1, user_id=42, category="area_to_improve", status="struggling")
    item_2 = SimpleNamespace(id=2, user_id=42, category="area_to_improve", status="improving")
    mock_service = MagicMock()
    mock_service.repo.get_by_ids = AsyncMock(return_value=[item_1, item_2])
    mock_service.repo.create = AsyncMock()
    mock_service._validate_status = MagicMock()
    mock_service._utc_now = MagicMock(return_value="now")

    with patch("runestone.agents.tools.memory_maintainer.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock(return_value=False)

        runtime = SimpleNamespace(context=SimpleNamespace(user=user))
        item = SimpleNamespace(
            category="area_to_improve",
            key="word_order_v3",
            content="Consolidated item",
            status="struggling",
            priority=2,
            replaced_item_ids=[1, 2],
        )
        result = await maintainer_insert_memory_item.coroutine(runtime, item=item)

    assert "Cross-status consolidation is not allowed" in result
    mock_service.repo.create.assert_not_awaited()
