from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agents.specialists.memory_maintainer.personal_info import PersonalInfoMemoryMaintainer


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.memory_maintainer_provider = "openrouter"
    settings.memory_maintainer_model = "test-model"
    return settings


@pytest.fixture
def mock_user():
    return SimpleNamespace(id=1, mother_tongue="Finnish")


@pytest.mark.anyio
async def test_personal_info_maintainer_loads_full_scope_in_one_call(mock_settings, mock_user):
    items = [
        SimpleNamespace(
            id=idx,
            key=f"fact_{idx}",
            content=f"Fact {idx}",
            status="active",
            updated_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
            status_changed_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
        )
        for idx in range(1, 201)
    ]
    service = MagicMock()
    service.cleanup_stale_personal_info_outdated = AsyncMock(return_value=0)
    service.list_memory_items = AsyncMock(return_value=items)

    @asynccontextmanager
    async def fake_provider():
        yield service

    model = MagicMock()
    review_plan = MagicMock()
    review_plan.decisions = [
        SimpleNamespace(item_id=item.id, action="keep_active", why="Keep active") for item in items
    ]
    summary_plan = SimpleNamespace(summary="Summary")

    review_model = MagicMock()
    review_model.ainvoke = AsyncMock(return_value=review_plan)
    summary_model = MagicMock()
    summary_model.ainvoke = AsyncMock(return_value=summary_plan)

    def _structured(schema):
        if schema.__name__ == "PersonalInfoReviewPlan":
            return review_model
        return summary_model

    model.with_structured_output.side_effect = _structured

    with (
        patch("runestone.agents.specialists.memory_maintainer.personal_info.build_chat_model", return_value=model),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.provide_memory_item_service", fake_provider
        ),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        result = await specialist.run_cli_for_user(mock_user, dry_run=True)

    assert result.status == "action_taken"
    service.cleanup_stale_personal_info_outdated.assert_awaited_once()
    service.list_memory_items.assert_awaited_once()
    assert service.list_memory_items.await_args.kwargs["limit"] is None
    assert result.artifacts["reviewed_item_count"] == 200


def _make_item(
    item_id: int,
    *,
    key: str,
    content: str,
    status: str = "active",
    updated_at: datetime | None = None,
):
    return SimpleNamespace(
        id=item_id,
        key=key,
        content=content,
        status=status,
        updated_at=updated_at or datetime(2026, 5, 29, tzinfo=timezone.utc),
        status_changed_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
    )


@pytest.mark.anyio
async def test_personal_info_maintainer_injects_current_datetime_into_review_and_summary(mock_settings, mock_user):
    items = [
        _make_item(1, key="current_status_working_20260526", content="The student is off work today (2026-05-26)."),
        _make_item(2, key="preferred_explanation_language", content="Prefers Russian for explanations."),
    ]
    service = MagicMock()
    service.cleanup_stale_personal_info_outdated = AsyncMock(return_value=0)
    service.list_memory_items = AsyncMock(return_value=items)

    @asynccontextmanager
    async def fake_provider():
        yield service

    review_plan = MagicMock()
    review_plan.decisions = [
        SimpleNamespace(item_id=1, action="keep_active", why="model kept temp fact"),
        SimpleNamespace(item_id=2, action="keep_active", why="stable fact"),
    ]
    summary_plan = SimpleNamespace(summary="Prefers Russian for explanations.")

    review_model = MagicMock()
    review_model.ainvoke = AsyncMock(return_value=review_plan)
    summary_model = MagicMock()
    summary_model.ainvoke = AsyncMock(return_value=summary_plan)

    model = MagicMock()
    model.with_structured_output.side_effect = lambda schema: (
        review_model if schema.__name__ == "PersonalInfoReviewPlan" else summary_model
    )

    with (
        patch("runestone.agents.specialists.memory_maintainer.personal_info.build_chat_model", return_value=model),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.provide_memory_item_service", fake_provider
        ),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info"
            ".PersonalInfoMemoryMaintainer._current_datetime_iso",
            return_value="2026-06-14T10:30:00+00:00",
        ),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        result = await specialist.run_cli_for_user(mock_user, dry_run=True)

    assert result.artifacts["kept_active_item_ids"] == [1, 2]
    assert result.artifacts["summary_source_item_ids"] == [1, 2]
    assert result.artifacts["summary_excluded_item_ids"] == []
    assert result.artifacts["stale_outdated_deleted_count"] == 0

    review_messages = review_model.ainvoke.await_args.args[0]
    summary_messages = summary_model.ainvoke.await_args.args[0]
    assert "Current datetime: 2026-06-14T10:30:00+00:00" in review_messages[0].content
    assert '"current_datetime": "2026-06-14T10:30:00+00:00"' in review_messages[1].content
    assert "Current datetime: 2026-06-14T10:30:00+00:00" in summary_messages[0].content
    assert '"current_datetime": "2026-06-14T10:30:00+00:00"' in summary_messages[1].content


@pytest.mark.anyio
async def test_personal_info_maintainer_respects_model_duplicate_resolution(mock_settings, mock_user):
    items = [
        _make_item(10, key="name", content="Andrey", updated_at=datetime(2026, 5, 26, 13, 13, tzinfo=timezone.utc)),
        _make_item(
            11,
            key="student_name",
            content="Andrey",
            updated_at=datetime(2026, 5, 26, 13, 14, tzinfo=timezone.utc),
        ),
    ]
    service = MagicMock()
    service.cleanup_stale_personal_info_outdated = AsyncMock(return_value=0)
    service.list_memory_items = AsyncMock(return_value=items)

    @asynccontextmanager
    async def fake_provider():
        yield service

    review_plan = MagicMock()
    review_plan.decisions = [
        SimpleNamespace(item_id=10, action="keep_active", why="same"),
        SimpleNamespace(item_id=11, action="keep_active", why="same"),
    ]
    summary_plan = SimpleNamespace(summary="The student's name is Andrey.")

    review_model = MagicMock()
    review_model.ainvoke = AsyncMock(return_value=review_plan)
    summary_model = MagicMock()
    summary_model.ainvoke = AsyncMock(return_value=summary_plan)

    model = MagicMock()
    model.with_structured_output.side_effect = lambda schema: (
        review_model if schema.__name__ == "PersonalInfoReviewPlan" else summary_model
    )

    with (
        patch("runestone.agents.specialists.memory_maintainer.personal_info.build_chat_model", return_value=model),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.provide_memory_item_service", fake_provider
        ),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        result = await specialist.run_cli_for_user(mock_user, dry_run=True)

    decisions = {decision["item_id"]: decision for decision in result.artifacts["decisions"]}
    assert decisions[10]["action"] == "keep_active"
    assert decisions[11]["action"] == "keep_active"
    assert result.artifacts["deleted_item_ids"] == []
    assert result.artifacts["kept_active_item_ids"] == [10, 11]


@pytest.mark.anyio
async def test_personal_info_maintainer_passes_dated_background_fact_to_model(mock_settings, mock_user):
    items = [
        _make_item(21, key="background_sweden_2020", content="The student lived in Sweden in 2020."),
    ]
    service = MagicMock()
    service.cleanup_stale_personal_info_outdated = AsyncMock(return_value=0)
    service.list_memory_items = AsyncMock(return_value=items)

    @asynccontextmanager
    async def fake_provider():
        yield service

    review_plan = MagicMock()
    review_plan.decisions = [SimpleNamespace(item_id=21, action="keep_active", why="background fact")]
    summary_plan = SimpleNamespace(summary="The student lived in Sweden in 2020.")

    review_model = MagicMock()
    review_model.ainvoke = AsyncMock(return_value=review_plan)
    summary_model = MagicMock()
    summary_model.ainvoke = AsyncMock(return_value=summary_plan)

    model = MagicMock()
    model.with_structured_output.side_effect = lambda schema: (
        review_model if schema.__name__ == "PersonalInfoReviewPlan" else summary_model
    )

    with (
        patch("runestone.agents.specialists.memory_maintainer.personal_info.build_chat_model", return_value=model),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.provide_memory_item_service", fake_provider
        ),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info"
            ".PersonalInfoMemoryMaintainer._current_datetime_iso",
            return_value="2026-06-14T10:30:00+00:00",
        ),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        result = await specialist.run_cli_for_user(mock_user, dry_run=True)

    assert result.artifacts["deleted_item_ids"] == []
    assert result.artifacts["kept_active_item_ids"] == [21]
    assert result.artifacts["summary_source_item_ids"] == [21]
    review_messages = review_model.ainvoke.await_args.args[0]
    assert "Current datetime: 2026-06-14T10:30:00+00:00" in review_messages[0].content


@pytest.mark.anyio
async def test_personal_info_maintainer_reports_precleanup_deleted_outdated_rows(mock_settings, mock_user):
    items = [
        _make_item(
            31,
            key="fresh_active_fact",
            content="Fresh active fact.",
            status="active",
            updated_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        ),
    ]
    service = MagicMock()
    service.cleanup_stale_personal_info_outdated = AsyncMock(return_value=1)
    service.list_memory_items = AsyncMock(return_value=items)

    @asynccontextmanager
    async def fake_provider():
        yield service

    review_plan = MagicMock()
    review_plan.decisions = [
        SimpleNamespace(item_id=31, action="keep_active", why="current"),
    ]
    summary_plan = SimpleNamespace(summary="Fresh active fact.")

    review_model = MagicMock()
    review_model.ainvoke = AsyncMock(return_value=review_plan)
    summary_model = MagicMock()
    summary_model.ainvoke = AsyncMock(return_value=summary_plan)

    model = MagicMock()
    model.with_structured_output.side_effect = lambda schema: (
        review_model if schema.__name__ == "PersonalInfoReviewPlan" else summary_model
    )

    with (
        patch("runestone.agents.specialists.memory_maintainer.personal_info.build_chat_model", return_value=model),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.provide_memory_item_service", fake_provider
        ),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        result = await specialist.run_cli_for_user(mock_user, dry_run=True)

    service.cleanup_stale_personal_info_outdated.assert_awaited_once_with(
        user_id=mock_user.id,
        older_than_days=14,
        dry_run=True,
    )
    assert result.artifacts["stale_outdated_deleted_count"] == 1
    assert result.artifacts["deleted_item_ids"] == []
    assert result.artifacts["summary_source_item_ids"] == [31]


@pytest.mark.anyio
async def test_personal_info_maintainer_precleanup_runs_in_apply_mode(mock_settings, mock_user):
    item = _make_item(
        41,
        key="remaining_fact",
        content="Remaining fact.",
        status="active",
        updated_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
    )
    service = MagicMock()
    service.cleanup_stale_personal_info_outdated = AsyncMock(return_value=2)
    service.list_memory_items = AsyncMock(return_value=[item])
    service.get_item_by_id = AsyncMock(return_value=SimpleNamespace(id=41, user_id=mock_user.id, status="active"))
    service.update_item_status = AsyncMock()
    service.delete_item = AsyncMock()
    service.set_personal_info_summary = AsyncMock()

    @asynccontextmanager
    async def fake_provider():
        yield service

    review_plan = MagicMock()
    review_plan.decisions = [SimpleNamespace(item_id=41, action="keep_active", why="current")]
    summary_plan = SimpleNamespace(summary="Remaining fact.")

    review_model = MagicMock()
    review_model.ainvoke = AsyncMock(return_value=review_plan)
    summary_model = MagicMock()
    summary_model.ainvoke = AsyncMock(return_value=summary_plan)

    model = MagicMock()
    model.with_structured_output.side_effect = lambda schema: (
        review_model if schema.__name__ == "PersonalInfoReviewPlan" else summary_model
    )

    with (
        patch("runestone.agents.specialists.memory_maintainer.personal_info.build_chat_model", return_value=model),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.provide_memory_item_service", fake_provider
        ),
        patch("runestone.agents.specialists.memory_maintainer.personal_info.provide_user_service", fake_provider),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        result = await specialist.run_cli_for_user(mock_user, dry_run=False)

    service.cleanup_stale_personal_info_outdated.assert_awaited_once_with(
        user_id=mock_user.id,
        older_than_days=14,
        dry_run=False,
    )
    assert result.artifacts["stale_outdated_deleted_count"] == 2


@pytest.mark.anyio
async def test_personal_info_maintainer_dry_run_clears_empty_summary(mock_settings):
    user_with_summary = SimpleNamespace(id=5, personal_info_summary="Existing summary text")
    service = MagicMock()
    service.cleanup_stale_personal_info_outdated = AsyncMock(return_value=0)
    service.list_memory_items = AsyncMock(return_value=[])
    service.set_personal_info_summary = AsyncMock()

    @asynccontextmanager
    async def fake_provider():
        yield service

    with (
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.build_chat_model", return_value=MagicMock()
        ),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.provide_memory_item_service", fake_provider
        ),
        patch("runestone.agents.specialists.memory_maintainer.personal_info.provide_user_service", fake_provider),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        result = await specialist.run_cli_for_user(user_with_summary, dry_run=True)

    assert result.status == "action_taken"
    assert result.artifacts["summary"] == "dry_run cleared_empty_summary"
    assert result.artifacts["persisted_summary"] is None
    # User service must not be called during dry run
    service.set_personal_info_summary.assert_not_called()


@pytest.mark.anyio
async def test_personal_info_maintainer_handles_execution_exceptions(mock_settings, mock_user):
    item = _make_item(
        1,
        key="fact",
        content="Some fact.",
        status="active",
    )
    service = MagicMock()
    service.cleanup_stale_personal_info_outdated = AsyncMock(return_value=0)
    service.list_memory_items = AsyncMock(return_value=[item])

    @asynccontextmanager
    async def fake_provider():
        yield service

    with (
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.build_chat_model", return_value=MagicMock()
        ),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.provide_memory_item_service", fake_provider
        ),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        specialist._review_items = AsyncMock(side_effect=Exception("Unexpected execution error"))
        result = await specialist.run_cli_for_user(mock_user, dry_run=False)

    assert result.status == "error"
    assert result.artifacts["summary"] == "execution_failed"
    assert "execution_failed:Exception" in result.artifacts["step_errors"]
