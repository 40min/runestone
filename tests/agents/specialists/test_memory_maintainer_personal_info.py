from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agents.specialists.memory_maintainer.personal_info import (
    PERSONAL_INFO_BAKE_GROUP_PROMPT,
    PERSONAL_INFO_BUCKET_TOPICS_PROMPT,
    PERSONAL_INFO_REVIEW_BUCKET_PROMPT,
    PERSONAL_INFO_SUMMARY_MAX_CHARS,
    PERSONAL_INFO_SUMMARY_PROMPT,
    BakeGroupPlan,
    BucketReviewGroup,
    BucketReviewPlan,
    BucketTopicGroup,
    BucketTopicsPlan,
    PersonalInfoMemoryMaintainer,
    PersonalInfoSummaryPlan,
)


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.memory_maintainer_provider = "openrouter"
    settings.memory_maintainer_model = "test-model"
    return settings


@pytest.fixture
def mock_user():
    return SimpleNamespace(id=1, mother_tongue="Finnish")


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
        user_id=1,
        category="personal_info",
        key=key,
        content=content,
        status=status,
        updated_at=updated_at or datetime(2026, 5, 29, tzinfo=timezone.utc),
        status_changed_at=updated_at or datetime(2026, 5, 29, tzinfo=timezone.utc),
    )


def _build_model(*, bucket_plan, summary_plan, review_plan=None, bake_plan=None):
    bucket_model = MagicMock()
    bucket_model.ainvoke = AsyncMock(return_value=bucket_plan)

    summary_model = MagicMock()
    summary_model.ainvoke = AsyncMock(return_value=summary_plan)

    review_model = MagicMock()
    review_model.ainvoke = AsyncMock(return_value=review_plan)

    bake_model = MagicMock()
    bake_model.ainvoke = AsyncMock(return_value=bake_plan)

    model = MagicMock()

    def _structured(schema):
        if schema.__name__ == "BucketTopicsPlan":
            return bucket_model
        if schema.__name__ == "BucketReviewPlan":
            return review_model
        if schema.__name__ == "BakeGroupPlan":
            return bake_model
        if schema.__name__ == "PersonalInfoSummaryPlan":
            return summary_model
        raise AssertionError(f"Unexpected schema: {schema.__name__}")

    model.with_structured_output.side_effect = _structured
    return model, bucket_model, review_model, bake_model, summary_model


@pytest.mark.anyio
async def test_personal_info_maintainer_loads_full_scope_in_one_call(mock_settings, mock_user):
    items = [_make_item(idx, key=f"fact_{idx}", content=f"Fact {idx}") for idx in range(1, 201)]
    service = MagicMock()
    service.list_memory_items = AsyncMock(return_value=items)

    @asynccontextmanager
    async def fake_provider():
        yield service

    bucket_plan = BucketTopicsPlan(
        buckets=[BucketTopicGroup(bucket_label=f"fact_{item.id}", item_ids=[item.id]) for item in items]
    )
    summary_plan = PersonalInfoSummaryPlan(summary="Summary")
    model, *_ = _build_model(bucket_plan=bucket_plan, summary_plan=summary_plan)

    with (
        patch("runestone.agents.specialists.memory_maintainer.personal_info.build_chat_model", return_value=model),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.provide_memory_item_service", fake_provider
        ),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        result = await specialist.run_cli_for_user(mock_user, dry_run=True)

    assert result.status == "action_taken"
    service.list_memory_items.assert_awaited_once()
    assert service.list_memory_items.await_args.kwargs["limit"] is None
    assert result.artifacts["reviewed_item_count"] == 200
    assert result.artifacts["kept_active_item_ids"] == [item.id for item in items]


@pytest.mark.anyio
async def test_personal_info_maintainer_injects_current_datetime_into_bucket_review_bake_and_summary(
    mock_settings, mock_user
):
    items = [
        _make_item(
            1, key="lives_in", content="Lives in Stockholm.", updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc)
        ),
        _make_item(
            2,
            key="lives_in",
            content="Lives in Uppsala.",
            status="correction",
            updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        ),
    ]
    service = MagicMock()
    service.list_memory_items = AsyncMock(return_value=items)

    @asynccontextmanager
    async def fake_provider():
        yield service

    bucket_plan = BucketTopicsPlan(
        buckets=[BucketTopicGroup(bucket_label="location", item_ids=[1, 2], why="same location fact")]
    )
    review_plan = BucketReviewPlan(groups=[BucketReviewGroup(item_ids=[1, 2], why="same fact over time")])
    bake_plan = BakeGroupPlan(
        outcome="bake_active",
        final_key="lives_in",
        final_content="Lives in Uppsala.",
        why="newer correction wins",
    )
    summary_plan = PersonalInfoSummaryPlan(summary="The student lives in Uppsala.")
    model, bucket_model, review_model, bake_model, summary_model = _build_model(
        bucket_plan=bucket_plan,
        review_plan=review_plan,
        bake_plan=bake_plan,
        summary_plan=summary_plan,
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

    assert result.artifacts["deleted_item_ids"] == [1, 2]
    assert result.artifacts["summary_source_item_ids"] == [1, 2]

    bucket_messages = bucket_model.ainvoke.await_args.args[0]
    review_messages = review_model.ainvoke.await_args.args[0]
    bake_messages = bake_model.ainvoke.await_args.args[0]
    summary_messages = summary_model.ainvoke.await_args.args[0]

    assert "Current datetime: 2026-06-14T10:30:00+00:00" in bucket_messages[0].content
    assert '"current_datetime": "2026-06-14T10:30:00+00:00"' in bucket_messages[1].content
    assert "Current datetime: 2026-06-14T10:30:00+00:00" in review_messages[0].content
    assert '"current_datetime": "2026-06-14T10:30:00+00:00"' in review_messages[1].content
    assert "Current datetime: 2026-06-14T10:30:00+00:00" in bake_messages[0].content
    assert '"current_datetime": "2026-06-14T10:30:00+00:00"' in bake_messages[1].content
    assert "Current datetime: 2026-06-14T10:30:00+00:00" in summary_messages[0].content
    assert '"current_datetime": "2026-06-14T10:30:00+00:00"' in summary_messages[1].content


def test_personal_info_summary_normalization_caps_long_output_deterministically():
    long_sentence = "A" * (PERSONAL_INFO_SUMMARY_MAX_CHARS + 25)

    normalized = PersonalInfoMemoryMaintainer._normalize_summary_text(f"  {long_sentence}\n\n")

    assert normalized is not None
    assert len(normalized) == PERSONAL_INFO_SUMMARY_MAX_CHARS
    assert normalized.endswith("...")


def test_personal_info_summary_normalization_prefers_sentence_boundary_when_available():
    sentence = "Andrei is a B1 Swedish learner who prefers independent practice. "
    summary = sentence * 20

    normalized = PersonalInfoMemoryMaintainer._normalize_summary_text(summary)

    assert normalized is not None
    assert len(normalized) <= PERSONAL_INFO_SUMMARY_MAX_CHARS
    assert normalized.endswith(".")


@pytest.mark.anyio
async def test_personal_info_maintainer_deletes_consumed_outdated_group_in_dry_run(mock_settings, mock_user):
    items = [
        _make_item(
            31,
            key="learning_goal",
            content="Goal: conversational fluency.",
            updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        ),
        _make_item(
            32,
            key="learning_goal",
            content="Forget the learning goal.",
            status="outdated",
            updated_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        ),
    ]
    service = MagicMock()
    service.list_memory_items = AsyncMock(return_value=items)

    @asynccontextmanager
    async def fake_provider():
        yield service

    bucket_plan = BucketTopicsPlan(
        buckets=[BucketTopicGroup(bucket_label="goal", item_ids=[31, 32], why="same goal fact")]
    )
    review_plan = BucketReviewPlan(groups=[BucketReviewGroup(item_ids=[31, 32], why="same fact over time")])
    bake_plan = BakeGroupPlan(outcome="delete_all", why="removal request retires the fact")
    summary_plan = PersonalInfoSummaryPlan(summary="")
    model, *_ = _build_model(
        bucket_plan=bucket_plan,
        review_plan=review_plan,
        bake_plan=bake_plan,
        summary_plan=summary_plan,
    )

    with (
        patch("runestone.agents.specialists.memory_maintainer.personal_info.build_chat_model", return_value=model),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.provide_memory_item_service", fake_provider
        ),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        result = await specialist.run_cli_for_user(mock_user, dry_run=True)

    assert result.artifacts["deleted_item_ids"] == [31, 32]
    assert result.artifacts["summary_source_item_ids"] == []
    assert result.artifacts["summary_excluded_item_ids"] == [31, 32]
    assert result.artifacts["summary_preview"] is None


@pytest.mark.anyio
async def test_personal_info_maintainer_bakes_multi_item_bucket_in_apply_mode(mock_settings, mock_user):
    items = [
        _make_item(
            41, key="lives_in", content="Lives in Stockholm.", updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc)
        ),
        _make_item(
            42,
            key="lives_in",
            content="Lives in Uppsala.",
            status="correction",
            updated_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        ),
    ]
    listed_service = MagicMock()
    listed_service.list_memory_items = AsyncMock(return_value=items)
    listed_service.get_items_by_ids = AsyncMock(return_value=items)
    listed_service.create_item_and_delete_sources = AsyncMock(return_value=(SimpleNamespace(id=99), [41, 42]))

    user_service = MagicMock()
    user_service.set_personal_info_summary = AsyncMock()

    @asynccontextmanager
    async def fake_memory_provider():
        yield listed_service

    @asynccontextmanager
    async def fake_user_provider():
        yield user_service

    bucket_plan = BucketTopicsPlan(
        buckets=[BucketTopicGroup(bucket_label="location", item_ids=[41, 42], why="same location fact")]
    )
    review_plan = BucketReviewPlan(groups=[BucketReviewGroup(item_ids=[41, 42], why="same fact over time")])
    bake_plan = BakeGroupPlan(
        outcome="bake_active",
        final_key="lives_in",
        final_content="Lives in Uppsala.",
        why="newer correction wins",
    )
    summary_plan = PersonalInfoSummaryPlan(summary="The student lives in Uppsala.")
    model, *_ = _build_model(
        bucket_plan=bucket_plan,
        review_plan=review_plan,
        bake_plan=bake_plan,
        summary_plan=summary_plan,
    )

    with (
        patch("runestone.agents.specialists.memory_maintainer.personal_info.build_chat_model", return_value=model),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.provide_memory_item_service",
            fake_memory_provider,
        ),
        patch("runestone.agents.specialists.memory_maintainer.personal_info.provide_user_service", fake_user_provider),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        result = await specialist.run_cli_for_user(mock_user, dry_run=False)

    listed_service.create_item_and_delete_sources.assert_awaited_once()
    user_service.set_personal_info_summary.assert_awaited_once_with(
        mock_user.id,
        "The student lives in Uppsala.",
    )
    assert result.artifacts["kept_active_item_ids"] == [99]
    assert result.artifacts["deleted_item_ids"] == [41, 42]


@pytest.mark.anyio
async def test_personal_info_maintainer_handles_execution_exceptions(mock_settings, mock_user):
    item = _make_item(1, key="fact", content="Some fact.")
    service = MagicMock()
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
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.PersonalInfoMemoryMaintainer._bucket_topics",
            AsyncMock(side_effect=Exception("Unexpected execution error")),
        ),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        result = await specialist.run_cli_for_user(mock_user, dry_run=False)

    assert result.status == "error"
    assert result.artifacts["summary"] == "execution_failed"
    assert "execution_failed:Exception" in result.artifacts["step_errors"]


@pytest.mark.anyio
async def test_personal_info_maintainer_bakes_singleton_correction_bucket_deterministically(mock_settings, mock_user):
    """A singleton bucket with status=correction must be baked to active without an LLM call."""
    item = _make_item(
        10,
        key="name",
        content="Name is Anna.",
        status="correction",
        updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    service = MagicMock()
    service.list_memory_items = AsyncMock(return_value=[item])

    @asynccontextmanager
    async def fake_provider():
        yield service

    bucket_plan = BucketTopicsPlan(buckets=[BucketTopicGroup(bucket_label="name", item_ids=[10])])
    summary_plan = PersonalInfoSummaryPlan(summary="The student's name is Anna.")
    model, bucket_model, review_model, bake_model, summary_model = _build_model(
        bucket_plan=bucket_plan, summary_plan=summary_plan
    )

    with (
        patch("runestone.agents.specialists.memory_maintainer.personal_info.build_chat_model", return_value=model),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.provide_memory_item_service", fake_provider
        ),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        result = await specialist.run_cli_for_user(mock_user, dry_run=True)

    # Bake and review models must NOT have been called — singleton is resolved deterministically.
    bake_model.ainvoke.assert_not_awaited()
    review_model.ainvoke.assert_not_awaited()

    assert result.status == "action_taken"
    # Source item is consumed by the bake resolution (queued for deletion).
    assert 10 in result.artifacts["deleted_item_ids"]
    # The baked synthetic item is counted as a summary source.
    assert 10 in result.artifacts["summary_source_item_ids"]
    baked_groups = result.artifacts["baked_groups"]
    assert len(baked_groups) == 1
    assert baked_groups[0]["outcome"] == "bake_active"
    assert baked_groups[0]["final_key"] == "name"
    assert baked_groups[0]["final_content"] == "Name is Anna."


@pytest.mark.anyio
async def test_personal_info_maintainer_deletes_singleton_outdated_bucket_deterministically(mock_settings, mock_user):
    """A singleton bucket with status=outdated must be deleted without an LLM call."""
    item = _make_item(
        20,
        key="work_schedule",
        content="Off work today.",
        status="outdated",
        updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    service = MagicMock()
    service.list_memory_items = AsyncMock(return_value=[item])

    @asynccontextmanager
    async def fake_provider():
        yield service

    bucket_plan = BucketTopicsPlan(buckets=[BucketTopicGroup(bucket_label="work_schedule", item_ids=[20])])
    summary_plan = PersonalInfoSummaryPlan(summary="")
    model, bucket_model, review_model, bake_model, summary_model = _build_model(
        bucket_plan=bucket_plan, summary_plan=summary_plan
    )

    with (
        patch("runestone.agents.specialists.memory_maintainer.personal_info.build_chat_model", return_value=model),
        patch(
            "runestone.agents.specialists.memory_maintainer.personal_info.provide_memory_item_service", fake_provider
        ),
    ):
        specialist = PersonalInfoMemoryMaintainer(mock_settings)
        result = await specialist.run_cli_for_user(mock_user, dry_run=True)

    # Neither bake nor review models should be called for a singleton outdated bucket.
    bake_model.ainvoke.assert_not_awaited()
    review_model.ainvoke.assert_not_awaited()

    assert result.status == "action_taken"
    assert result.artifacts["deleted_item_ids"] == [20]
    assert result.artifacts["summary_source_item_ids"] == []
    assert result.artifacts["summary_excluded_item_ids"] == [20]
    assert result.artifacts["summary_preview"] is None


def test_personal_info_prompts_require_bucket_review_and_baking_contract():
    assert "group the provided `personal_info` rows into candidate topic buckets" in PERSONAL_INFO_BUCKET_TOPICS_PROMPT
    assert "reason chronologically" in PERSONAL_INFO_REVIEW_BUCKET_PROMPT
    assert "produce one final active fact or no surviving fact" in PERSONAL_INFO_BAKE_GROUP_PROMPT
    assert f"at most {PERSONAL_INFO_SUMMARY_MAX_CHARS} characters" in PERSONAL_INFO_SUMMARY_PROMPT
    assert "Omit low-value or overly narrow details" in PERSONAL_INFO_SUMMARY_PROMPT
