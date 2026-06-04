from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, Field
from sqlalchemy import select

from runestone.agents.specialists.base import SpecialistContext
from runestone.agents.specialists.memory_maintainer import (
    BucketReviewGroup,
    BucketReviewPlan,
    BucketTopicGroup,
    BucketTopicsPlan,
    MemoryMaintainerSpecialist,
    MergeGeneration,
    MergeValidation,
    PlannedGroup,
    PriorityReviewPlan,
    PrioritySuggestion,
)
from runestone.db.memory_item_repository import MemoryItemRepository
from runestone.db.models import MemoryItem
from runestone.services.memory_item_service import MemoryItemService


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.memory_maintainer_provider = "openrouter"
    settings.memory_maintainer_model = "test-model"
    return settings


@pytest.fixture
def mock_user():
    return SimpleNamespace(id=1, mother_tongue="Finnish")


@pytest.fixture
def specialist(mock_settings):
    model = MagicMock()
    with patch("runestone.agents.specialists.memory_maintainer.build_chat_model", return_value=model):
        specialist = MemoryMaintainerSpecialist(mock_settings)
    specialist.model = model
    return specialist


def _scope_item(
    item_id: int,
    *,
    key: str,
    content: str,
    status: str,
    priority: int | None = None,
    updated_at: datetime | None = None,
    status_changed_at: datetime | None = None,
):
    fixed_time = updated_at or datetime(2026, 5, 29, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=item_id,
        key=key,
        content=content,
        status=status,
        priority=priority,
        updated_at=fixed_time,
        status_changed_at=status_changed_at or fixed_time,
    )


def _db_item(
    user_id: int,
    *,
    item_id: int,
    key: str,
    content: str,
    status: str,
    priority: int | None = None,
    updated_at: datetime | None = None,
    status_changed_at: datetime | None = None,
):
    return MemoryItem(
        id=item_id,
        user_id=user_id,
        category="area_to_improve",
        key=key,
        content=content,
        status=status,
        priority=priority,
        updated_at=updated_at or datetime(2026, 5, 29, tzinfo=timezone.utc),
        status_changed_at=status_changed_at,
    )


class BucketResolutionGroup(BaseModel):
    """Backwards-compatible test fixture shape for combined step-2 outputs."""

    item_ids: list[int] = Field(default_factory=list)
    final_key: str
    final_content: str
    final_status: str
    why: str


class BucketResolutionPlan(BaseModel):
    """Backwards-compatible test fixture shape for combined step-2 outputs."""

    groups: list[BucketResolutionGroup] = Field(default_factory=list)


def _wire_structured_models(
    model,
    *,
    bucket_plan,
    bucket_reviews=None,
    merge_generations=None,
    merge_validations=None,
    bucket_resolutions=None,
    priority_plan=None,
):
    if bucket_resolutions is not None:
        if bucket_reviews is not None or merge_generations is not None or merge_validations is not None:
            raise AssertionError(
                "Use either bucket_resolutions or explicit bucket_reviews/merge_generations/merge_validations, not both"
            )
        bucket_reviews = []
        merge_generations = []
        merge_validations = []
        for resolution in bucket_resolutions:
            review_groups = []
            for group in resolution.groups:
                review_groups.append(BucketReviewGroup(item_ids=group.item_ids, why=group.why))
                if len(group.item_ids) > 1:
                    merge_generations.append(
                        MergeGeneration(
                            final_key=group.final_key,
                            final_content=group.final_content,
                            final_status=group.final_status,
                            why=group.why,
                        )
                    )
                    merge_validations.append(MergeValidation(approved=True, why=group.why))
            bucket_reviews.append(BucketReviewPlan(groups=review_groups))

    bucket_reviews = bucket_reviews or []
    merge_generations = merge_generations or []
    merge_validations = merge_validations or [MergeValidation(approved=True, why="Approved in test fixture.")]

    bucket_model = MagicMock()
    bucket_model.ainvoke = AsyncMock(return_value=bucket_plan)

    review_model = MagicMock()
    review_model.ainvoke = AsyncMock(side_effect=bucket_reviews)

    generate_model = MagicMock()
    generate_model.ainvoke = AsyncMock(side_effect=merge_generations)

    validate_model = MagicMock()
    validate_model.ainvoke = AsyncMock(side_effect=merge_validations)

    priority_model = MagicMock()
    priority_model.ainvoke = AsyncMock(return_value=priority_plan)

    def _structured(schema):
        if schema is BucketTopicsPlan:
            return bucket_model
        if schema is BucketReviewPlan:
            return review_model
        if schema is MergeGeneration:
            return generate_model
        if schema is MergeValidation:
            return validate_model
        if schema is PriorityReviewPlan:
            return priority_model
        raise AssertionError(f"Unexpected schema {schema}")

    model.with_structured_output.side_effect = _structured
    return bucket_model, review_model, generate_model, validate_model, priority_model


@pytest.mark.anyio
async def test_memory_maintainer_uses_structured_output_and_skips_priority_review_in_background(specialist, mock_user):
    planned_item = _scope_item(
        1,
        key="word_order_v1",
        content="Problem with word order",
        status="struggling",
    )
    created_item = SimpleNamespace(id=99, key="word_order_v2")
    service = MagicMock()
    service.list_memory_items = AsyncMock(return_value=[planned_item])
    service.repo.get_by_ids = AsyncMock(
        return_value=[
            _db_item(
                mock_user.id,
                item_id=1,
                key="word_order_v1",
                content="Problem with word order",
                status="struggling",
            )
        ]
    )
    service.repo.create = AsyncMock(return_value=created_item)
    service.repo.db = SimpleNamespace(rollback=AsyncMock())
    service.delete_item = AsyncMock()

    bucket_model, _review_model, _generate_model, _validate_model, priority_model = _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Word order",
                    item_ids=[1],
                    why="Anchor item id=1 key=word_order_v1 defines this bucket.",
                )
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[1],
                        final_key="word_order_v2",
                        final_content="Har problem med svensk ordfoljd.",
                        final_status="struggling",
                        why="Anchor item id=1 key=word_order_v1 remains a singleton topic.",
                    )
                ]
            )
        ],
    )

    @asynccontextmanager
    async def fake_provider():
        yield service

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run(
            SpecialistContext(
                message="start_new_chat",
                history=[],
                user=mock_user,
                routing_reason="new_chat_session_started",
            )
        )

    assert result.status == "no_action"
    assert specialist.model.with_structured_output.call_count == 1
    bucket_model.ainvoke.assert_awaited_once()
    priority_model.ainvoke.assert_not_awaited()
    assert result.artifacts["priority_review_enabled"] is False
    assert result.artifacts["no_change_reason"] == "no_merge_candidates"


@pytest.mark.anyio
async def test_memory_maintainer_fails_safely_when_bucket_step_cannot_parse(specialist, mock_user):
    service = MagicMock()
    service.list_memory_items = AsyncMock(
        return_value=[
            _scope_item(
                1,
                key="word_order_v1",
                content="Problem with word order",
                status="struggling",
            )
        ]
    )

    bucket_model = MagicMock()
    bucket_model.ainvoke = AsyncMock(side_effect=OutputParserException("bad bucket json"))

    def _structured(schema):
        if schema is BucketTopicsPlan:
            return bucket_model
        raise AssertionError(f"Unexpected schema {schema}")

    specialist.model.with_structured_output.side_effect = _structured

    @asynccontextmanager
    async def fake_provider():
        yield service

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run(
            SpecialistContext(
                message="start_new_chat",
                history=[],
                user=mock_user,
                routing_reason="new_chat_session_started",
            )
        )

    assert result.status == "error"
    assert result.artifacts["summary"] == "bucket_plan_failed"
    assert result.artifacts["step_errors"] == ["bucket_plan_failed"]


def test_repair_bucket_plan_deduplicates_recovers_missing_and_synthesizes_why(specialist):
    first = _scope_item(1, key="agreement_a", content="A", status="struggling")
    second = _scope_item(2, key="agreement_b", content="B", status="struggling")
    third = _scope_item(3, key="date_format", content="C", status="improving")
    items_by_id = {item.id: item for item in [first, second, third]}

    repaired = specialist._repair_bucket_plan(
        BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Agreement",
                    item_ids=[1, 2],
                    why=None,
                ),
                BucketTopicGroup(
                    bucket_label="Agreement overlap",
                    item_ids=[1],
                    why=None,
                ),
            ]
        ),
        items_by_id,
    )

    assert len(repaired.buckets) == 2
    assert repaired.buckets[0].item_ids == [1, 2]
    assert repaired.buckets[0].why is not None
    assert repaired.buckets[1].bucket_label == "Recovered singleton: date_format"
    assert repaired.buckets[1].item_ids == [3]
    assert repaired.buckets[1].why is None


@pytest.mark.anyio
async def test_memory_maintainer_merges_near_duplicates_and_latest_status_wins(
    specialist, mock_user, db_with_test_user
):
    db, user = db_with_test_user
    older = datetime(2026, 5, 1, tzinfo=timezone.utc)
    newer = datetime(2026, 5, 20, tzinfo=timezone.utc)
    first = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_v1",
        content="Problem med ordfoljd i huvudsatser.",
        status="struggling",
        priority=4,
        updated_at=older,
        status_changed_at=older,
    )
    second = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_v1_repeat",
        content="Blir battre men blandar fortfarande omvand ordfoljd.",
        status="improving",
        priority=2,
        updated_at=newer,
        status_changed_at=newer,
    )
    db.add_all([first, second])
    await db.commit()
    await db.refresh(first)
    await db.refresh(second)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Word order",
                    item_ids=[first.id, second.id],
                    why=f"Anchor item id={second.id} key={second.key} best represents this bucket.",
                )
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[first.id, second.id],
                        final_key="word_order_v2",
                        final_content="Forbattrar svensk ordfoljd men blandar fortfarande huvudsatsordfoljd.",
                        final_status="improving",
                        why=f"Anchor item id={second.id} key={second.key} is the latest duplicate signal.",
                    )
                ]
            )
        ],
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run(
            SpecialistContext(
                message="start_new_chat",
                history=[],
                user=user,
                routing_reason="new_chat_session_started",
            )
        )

    remaining = (await db.execute(select(MemoryItem).where(MemoryItem.user_id == user.id))).scalars().all()
    assert result.status == "action_taken"
    assert len(remaining) == 1
    assert remaining[0].key == "word_order_v2"
    assert remaining[0].status == "improving"
    assert remaining[0].priority == 2
    assert sorted(result.artifacts["deleted_item_ids"]) == sorted([first.id, second.id])


@pytest.mark.anyio
async def test_memory_maintainer_normalizes_group_status_to_latest_source_status(specialist, db_with_test_user):
    db, user = db_with_test_user
    older = datetime(2026, 5, 1, tzinfo=timezone.utc)
    newer = datetime(2026, 5, 20, tzinfo=timezone.utc)
    first = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="reflexive_v1",
        content="Reflexive issue.",
        status="struggling",
        priority=4,
        updated_at=older,
        status_changed_at=older,
    )
    second = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="reflexive_v2",
        content="Reflexive issue improving.",
        status="improving",
        priority=2,
        updated_at=newer,
        status_changed_at=newer,
    )
    db.add_all([first, second])
    await db.commit()
    await db.refresh(first)
    await db.refresh(second)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Reflexives",
                    item_ids=[first.id, second.id],
                    why=f"Anchor item id={second.id} key={second.key} defines this bucket.",
                )
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[first.id, second.id],
                        final_key="reflexive_v3",
                        final_content="Merged reflexive issue.",
                        final_status="struggling",
                        why=(
                            f"Anchor item id={second.id} key={second.key} is the same "
                            "teachable topic and should merge."
                        ),
                    )
                ]
            )
        ],
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run(
            SpecialistContext(
                message="start_new_chat",
                history=[],
                user=user,
                routing_reason="new_chat_session_started",
            )
        )

    merged_item = (
        (await db.execute(select(MemoryItem).where(MemoryItem.user_id == user.id, MemoryItem.key == "reflexive_v3")))
        .scalars()
        .one()
    )
    assert result.status == "action_taken"
    assert merged_item.status == "improving"


@pytest.mark.anyio
async def test_memory_maintainer_leaves_singleton_groups_unmodified(specialist, mock_user, db_with_test_user):
    db, user = db_with_test_user
    first = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="time_expressions_v1",
        content="Problem with time expressions.",
        status="struggling",
    )
    second = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="subordinate_clauses_v1",
        content="Problem with subordinate clauses.",
        status="improving",
    )
    db.add_all([first, second])
    await db.commit()
    await db.refresh(first)
    await db.refresh(second)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Word order family",
                    item_ids=[first.id, second.id],
                    why=f"Anchor item id={first.id} key={first.key} keeps these close topics together for review.",
                )
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[first.id],
                        final_key="time_expressions_v2",
                        final_content="Problem with time expressions.",
                        final_status="struggling",
                        why=f"Anchor item id={first.id} key={first.key} stays separate.",
                    ),
                    BucketResolutionGroup(
                        item_ids=[second.id],
                        final_key="subordinate_clauses_v2",
                        final_content="Problem with subordinate clauses.",
                        final_status="improving",
                        why=f"Anchor item id={second.id} key={second.key} stays separate.",
                    ),
                ]
            )
        ],
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run(
            SpecialistContext(
                message="start_new_chat",
                history=[],
                user=user,
                routing_reason="new_chat_session_started",
            )
        )

    remaining = (await db.execute(select(MemoryItem).where(MemoryItem.user_id == user.id))).scalars().all()
    assert result.status == "no_action"
    assert {item.key for item in remaining} == {"time_expressions_v1", "subordinate_clauses_v1"}
    assert result.artifacts["no_change_reason"] == "no_merge_candidates"


@pytest.mark.anyio
async def test_memory_maintainer_applies_partial_results_when_one_group_fails(specialist, mock_user, db_with_test_user):
    db, user = db_with_test_user
    user_id = user.id
    base_time = datetime(2026, 5, 1, tzinfo=timezone.utc)
    items = [
        MemoryItem(
            user_id=user_id,
            category="area_to_improve",
            key="word_order_a",
            content="Word order problem A.",
            status="struggling",
            updated_at=base_time,
            status_changed_at=base_time,
        ),
        MemoryItem(
            user_id=user_id,
            category="area_to_improve",
            key="word_order_b",
            content="Word order problem B.",
            status="struggling",
            updated_at=base_time + timedelta(days=1),
            status_changed_at=base_time + timedelta(days=1),
        ),
        MemoryItem(
            user_id=user_id,
            category="area_to_improve",
            key="time_expr_a",
            content="Time expression problem A.",
            status="struggling",
            updated_at=base_time + timedelta(days=2),
            status_changed_at=base_time + timedelta(days=2),
        ),
        MemoryItem(
            user_id=user_id,
            category="area_to_improve",
            key="time_expr_b",
            content="Time expression problem B.",
            status="struggling",
            updated_at=base_time + timedelta(days=3),
            status_changed_at=base_time + timedelta(days=3),
        ),
        MemoryItem(
            user_id=user_id,
            category="area_to_improve",
            key="word_order_v2",
            content="Existing collision item.",
            status="mastered",
        ),
    ]
    db.add_all(items)
    await db.commit()
    for item in items:
        await db.refresh(item)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Word order",
                    item_ids=[items[0].id, items[1].id],
                    why=f"Anchor item id={items[0].id} key={items[0].key} groups the word-order duplicates.",
                ),
                BucketTopicGroup(
                    bucket_label="Time expressions",
                    item_ids=[items[2].id, items[3].id],
                    why=f"Anchor item id={items[2].id} key={items[2].key} groups the time-expression duplicates.",
                ),
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[items[0].id, items[1].id],
                        final_key="word order merged",
                        final_content="Merged word order issue.",
                        final_status="struggling",
                        why=f"Anchor item id={items[1].id} key={items[1].key} is the latest source item.",
                    )
                ]
            ),
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[items[2].id, items[3].id],
                        final_key="time_expressions_v2",
                        final_content="Merged time-expression issue.",
                        final_status="struggling",
                        why=f"Anchor item id={items[3].id} key={items[3].key} is the latest source item.",
                    )
                ]
            ),
        ],
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run(
            SpecialistContext(
                message="start_new_chat",
                history=[],
                user=user,
                routing_reason="new_chat_session_started",
            )
        )

    remaining_keys = {
        item.key for item in (await db.execute(select(MemoryItem).where(MemoryItem.user_id == user_id))).scalars().all()
    }
    assert result.status == "action_taken"
    assert "word_order_a" in remaining_keys
    assert "word_order_b" in remaining_keys
    assert "word_order_v2" in remaining_keys
    assert "time_expr_a" not in remaining_keys
    assert "time_expr_b" not in remaining_keys
    assert "time_expressions_v1" in remaining_keys
    assert len(result.artifacts["failed_groups"]) == 1
    assert result.artifacts["failed_groups"][0]["reason"] == "invalid_target_key:format"
    assert len(result.artifacts["merged_groups"]) == 1


@pytest.mark.anyio
async def test_memory_maintainer_repairs_bucket_duplicates_and_missing_ids_in_run(specialist, db_with_test_user):
    db, user = db_with_test_user
    first = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="agreement_a",
        content="Agreement problem A.",
        status="struggling",
        priority=4,
    )
    second = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="agreement_b",
        content="Agreement problem B.",
        status="struggling",
        priority=2,
    )
    third = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="date_format_v1",
        content="Date-format issue.",
        status="improving",
        priority=6,
    )
    db.add_all([first, second, third])
    await db.commit()
    await db.refresh(first)
    await db.refresh(second)
    await db.refresh(third)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Agreement",
                    item_ids=[first.id, second.id],
                    why=None,
                ),
                BucketTopicGroup(
                    bucket_label="Agreement overlap",
                    item_ids=[first.id],
                    why=None,
                ),
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[first.id, second.id],
                        final_key="agreement_v2",
                        final_content="Merged agreement issue.",
                        final_status="struggling",
                        why=f"Anchor item id={second.id} key={second.key} is the latest source item.",
                    )
                ]
            )
        ],
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run(
            SpecialistContext(
                message="start_new_chat",
                history=[],
                user=user,
                routing_reason="new_chat_session_started",
            )
        )

    remaining = (await db.execute(select(MemoryItem).where(MemoryItem.user_id == user.id))).scalars().all()
    remaining_keys = {item.key for item in remaining}
    assert result.status == "action_taken"
    assert "agreement_v1" in remaining_keys
    assert "date_format_v1" in remaining_keys
    assert result.artifacts["summary"].startswith("applied_merges=1")
    assert len(result.artifacts["buckets"]) == 2
    assert result.artifacts["buckets"][0]["item_ids"] == [first.id, second.id]
    assert "why" in result.artifacts["buckets"][0]
    assert result.artifacts["buckets"][1]["item_ids"] == [third.id]


@pytest.mark.anyio
async def test_memory_maintainer_skips_merge_when_validator_rejects_it(specialist, db_with_test_user):
    db, user = db_with_test_user
    first = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="reflexive_v1",
        content="Reflexive issue.",
        status="struggling",
        priority=4,
    )
    second = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="object_pronoun_v1",
        content="Object pronoun issue.",
        status="improving",
        priority=2,
    )
    db.add_all([first, second])
    await db.commit()
    await db.refresh(first)
    await db.refresh(second)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Pronouns",
                    item_ids=[first.id, second.id],
                    why=f"Anchor item id={first.id} key={first.key} keeps these pronoun topics together for review.",
                )
            ]
        ),
        bucket_reviews=[
            BucketReviewPlan(
                groups=[
                    BucketReviewGroup(
                        item_ids=[first.id, second.id],
                        why="These both involve pronouns and are superficially related.",
                    )
                ]
            )
        ],
        merge_generations=[
            MergeGeneration(
                final_key="pronoun_usage_v2",
                final_content="Merged pronoun issue.",
                final_status="struggling",
                why="Anchor item id=1 key=reflexive_v1 preserves the merged pronoun topic.",
            )
        ],
        merge_validations=[
            MergeValidation(
                approved=False,
                why="These items are related but not one exact teachable topic, so they should stay separate.",
            )
        ],
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run(
            SpecialistContext(
                message="start_new_chat",
                history=[],
                user=user,
                routing_reason="new_chat_session_started",
            )
        )

    remaining_keys = {
        item.key for item in (await db.execute(select(MemoryItem).where(MemoryItem.user_id == user.id))).scalars().all()
    }
    assert result.status == "no_action"
    assert remaining_keys == {"reflexive_v1", "object_pronoun_v1"}
    assert result.artifacts["merged_groups"] == []
    assert result.artifacts["no_change_reason"] == "no_merge_candidates"


@pytest.mark.anyio
async def test_memory_maintainer_dry_run_bumps_version_past_existing_key(specialist, db_with_test_user):
    db, user = db_with_test_user
    base_time = datetime(2026, 5, 1, tzinfo=timezone.utc)
    first = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_a",
        content="Word order problem A.",
        status="struggling",
        updated_at=base_time,
        status_changed_at=base_time,
    )
    second = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_b",
        content="Word order problem B.",
        status="struggling",
        updated_at=base_time + timedelta(days=1),
        status_changed_at=base_time + timedelta(days=1),
    )
    collision = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_v2",
        content="Existing collision item.",
        status="mastered",
    )
    db.add_all([first, second, collision])
    await db.commit()
    await db.refresh(first)
    await db.refresh(second)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Word order",
                    item_ids=[first.id, second.id],
                    why=f"Anchor item id={first.id} key={first.key} groups the word-order duplicates.",
                )
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[first.id, second.id],
                        final_key="word_order_v2",
                        final_content="Merged word-order issue.",
                        final_status="struggling",
                        why=f"Anchor item id={second.id} key={second.key} is the latest source item.",
                    )
                ]
            )
        ],
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run_cli_for_user(
            user,
            dry_run=True,
            with_priority_review=False,
        )

    assert result.status == "action_taken"
    assert result.artifacts["failed_groups"] == []
    assert len(result.artifacts["merged_groups"]) == 1
    assert result.artifacts["merged_groups"][0]["new_key"] == "word_order_v3"


@pytest.mark.anyio
async def test_memory_maintainer_dry_run_rejects_invalid_generated_final_key(specialist, db_with_test_user):
    db, user = db_with_test_user
    base_time = datetime(2026, 5, 1, tzinfo=timezone.utc)
    first = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_a",
        content="Word order problem A.",
        status="struggling",
        updated_at=base_time,
        status_changed_at=base_time,
    )
    second = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_b",
        content="Word order problem B.",
        status="struggling",
        updated_at=base_time + timedelta(days=1),
        status_changed_at=base_time + timedelta(days=1),
    )
    db.add_all([first, second])
    await db.commit()
    await db.refresh(first)
    await db.refresh(second)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Word order",
                    item_ids=[first.id, second.id],
                    why=f"Anchor item id={first.id} key={first.key} groups the word-order duplicates.",
                )
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[first.id, second.id],
                        final_key="word order merged",
                        final_content="Merged word-order issue.",
                        final_status="struggling",
                        why=f"Anchor item id={second.id} key={second.key} is the latest source item.",
                    )
                ]
            )
        ],
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run_cli_for_user(
            user,
            dry_run=True,
            with_priority_review=False,
        )

    assert result.status == "error"
    assert result.artifacts["merged_groups"] == []
    assert len(result.artifacts["failed_groups"]) == 1
    assert result.artifacts["failed_groups"][0]["reason"] == "invalid_target_key:format"


@pytest.mark.anyio
async def test_memory_maintainer_normalizes_unversioned_generated_final_key(specialist, db_with_test_user):
    db, user = db_with_test_user
    base_time = datetime(2026, 5, 1, tzinfo=timezone.utc)
    first = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_a",
        content="Word order problem A.",
        status="struggling",
        updated_at=base_time,
        status_changed_at=base_time,
    )
    second = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_b",
        content="Word order problem B.",
        status="improving",
        updated_at=base_time + timedelta(days=1),
        status_changed_at=base_time + timedelta(days=1),
    )
    db.add_all([first, second])
    await db.commit()
    await db.refresh(first)
    await db.refresh(second)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Word order",
                    item_ids=[first.id, second.id],
                    why=f"Anchor item id={first.id} key={first.key} groups the word-order duplicates.",
                )
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[first.id, second.id],
                        final_key="word_order_merged",
                        final_content="Merged word-order issue.",
                        final_status="improving",
                        why=f"Anchor item id={second.id} key={second.key} is the latest source item.",
                    )
                ]
            )
        ],
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run_cli_for_user(
            user,
            dry_run=True,
            with_priority_review=False,
        )

    assert result.status == "action_taken"
    assert result.artifacts["failed_groups"] == []
    assert len(result.artifacts["merged_groups"]) == 1
    assert result.artifacts["merged_groups"][0]["new_key"] == "word_order_merged_v1"


@pytest.mark.anyio
async def test_memory_maintainer_ignores_model_supplied_version_suffix(specialist, db_with_test_user):
    db, user = db_with_test_user
    base_time = datetime(2026, 5, 1, tzinfo=timezone.utc)
    first = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_a",
        content="Word order problem A.",
        status="struggling",
        updated_at=base_time,
        status_changed_at=base_time,
    )
    second = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_b",
        content="Word order problem B.",
        status="improving",
        updated_at=base_time + timedelta(days=1),
        status_changed_at=base_time + timedelta(days=1),
    )
    db.add_all([first, second])
    await db.commit()
    await db.refresh(first)
    await db.refresh(second)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Word order",
                    item_ids=[first.id, second.id],
                    why=f"Anchor item id={first.id} key={first.key} groups the word-order duplicates.",
                )
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[first.id, second.id],
                        final_key="word_order_merged_v3",
                        final_content="Merged word-order issue.",
                        final_status="improving",
                        why=f"Anchor item id={second.id} key={second.key} is the latest source item.",
                    )
                ]
            )
        ],
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run_cli_for_user(
            user,
            dry_run=True,
            with_priority_review=False,
        )

    assert result.status == "action_taken"
    assert result.artifacts["failed_groups"] == []
    assert len(result.artifacts["merged_groups"]) == 1
    assert result.artifacts["merged_groups"][0]["new_key"] == "word_order_merged_v1"


@pytest.mark.anyio
async def test_memory_maintainer_assigns_next_version_from_existing_keys(specialist, db_with_test_user):
    db, user = db_with_test_user
    base_time = datetime(2026, 5, 1, tzinfo=timezone.utc)
    existing = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_merged_v2",
        content="Existing merged item.",
        status="improving",
        updated_at=base_time,
        status_changed_at=base_time,
    )
    first = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_a",
        content="Word order problem A.",
        status="struggling",
        updated_at=base_time,
        status_changed_at=base_time,
    )
    second = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="word_order_b",
        content="Word order problem B.",
        status="improving",
        updated_at=base_time + timedelta(days=1),
        status_changed_at=base_time + timedelta(days=1),
    )
    db.add_all([existing, first, second])
    await db.commit()
    await db.refresh(existing)
    await db.refresh(first)
    await db.refresh(second)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Word order",
                    item_ids=[first.id, second.id],
                    why=f"Anchor item id={first.id} key={first.key} groups the word-order duplicates.",
                )
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[first.id, second.id],
                        final_key="word_order_merged",
                        final_content="Merged word-order issue.",
                        final_status="improving",
                        why=f"Anchor item id={second.id} key={second.key} is the latest source item.",
                    )
                ]
            )
        ],
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run_cli_for_user(
            user,
            dry_run=True,
            with_priority_review=False,
        )

    assert result.status == "action_taken"
    assert result.artifacts["failed_groups"] == []
    assert len(result.artifacts["merged_groups"]) == 1
    assert result.artifacts["merged_groups"][0]["new_key"] == "word_order_merged_v3"


@pytest.mark.anyio
async def test_memory_maintainer_dry_run_assigns_distinct_versions_within_plan(specialist, db_with_test_user):
    db, user = db_with_test_user
    user_id = user.id
    base_time = datetime(2026, 5, 1, tzinfo=timezone.utc)
    items = [
        MemoryItem(
            user_id=user_id,
            category="area_to_improve",
            key="word_order_a",
            content="Word order problem A.",
            status="struggling",
            updated_at=base_time,
            status_changed_at=base_time,
        ),
        MemoryItem(
            user_id=user_id,
            category="area_to_improve",
            key="word_order_b",
            content="Word order problem B.",
            status="struggling",
            updated_at=base_time + timedelta(days=1),
            status_changed_at=base_time + timedelta(days=1),
        ),
        MemoryItem(
            user_id=user_id,
            category="area_to_improve",
            key="time_expr_a",
            content="Time expression problem A.",
            status="struggling",
            updated_at=base_time + timedelta(days=2),
            status_changed_at=base_time + timedelta(days=2),
        ),
        MemoryItem(
            user_id=user_id,
            category="area_to_improve",
            key="time_expr_b",
            content="Time expression problem B.",
            status="struggling",
            updated_at=base_time + timedelta(days=3),
            status_changed_at=base_time + timedelta(days=3),
        ),
    ]
    db.add_all(items)
    await db.commit()
    for item in items:
        await db.refresh(item)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Word order",
                    item_ids=[items[0].id, items[1].id],
                    why=f"Anchor item id={items[0].id} key={items[0].key} groups word-order duplicates.",
                ),
                BucketTopicGroup(
                    bucket_label="Time expressions",
                    item_ids=[items[2].id, items[3].id],
                    why=f"Anchor item id={items[2].id} key={items[2].key} groups time-expression duplicates.",
                ),
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[items[0].id, items[1].id],
                        final_key="shared_topic_v2",
                        final_content="Merged word-order issue.",
                        final_status="struggling",
                        why=f"Anchor item id={items[1].id} key={items[1].key} is latest in group one.",
                    )
                ]
            ),
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[items[2].id, items[3].id],
                        final_key="shared_topic_v2",
                        final_content="Merged time-expression issue.",
                        final_status="struggling",
                        why=f"Anchor item id={items[3].id} key={items[3].key} is latest in group two.",
                    )
                ]
            ),
        ],
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run_cli_for_user(
            user,
            dry_run=True,
            with_priority_review=False,
        )

    assert result.status == "action_taken"
    assert result.artifacts["failed_groups"] == []
    assert len(result.artifacts["merged_groups"]) == 2
    assert [group["new_key"] for group in result.artifacts["merged_groups"]] == ["shared_topic_v1", "shared_topic_v2"]


@pytest.mark.anyio
async def test_memory_maintainer_rolls_back_merge_group_when_delete_fails(specialist, db_with_test_user):
    db, user = db_with_test_user
    user_id = user.id
    base_time = datetime(2026, 5, 1, tzinfo=timezone.utc)
    first = MemoryItem(
        user_id=user_id,
        category="area_to_improve",
        key="agreement_a",
        content="Agreement problem A.",
        status="struggling",
        updated_at=base_time,
        status_changed_at=base_time,
    )
    second = MemoryItem(
        user_id=user_id,
        category="area_to_improve",
        key="agreement_b",
        content="Agreement problem B.",
        status="struggling",
        updated_at=base_time + timedelta(days=1),
        status_changed_at=base_time + timedelta(days=1),
    )
    db.add_all([first, second])
    await db.commit()
    await db.refresh(first)
    await db.refresh(second)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Agreement",
                    item_ids=[first.id, second.id],
                    why=f"Anchor item id={first.id} key={first.key} groups agreement duplicates.",
                )
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[first.id, second.id],
                        final_key="agreement_v2",
                        final_content="Merged agreement issue.",
                        final_status="struggling",
                        why=f"Anchor item id={second.id} key={second.key} is the latest source item.",
                    )
                ]
            )
        ],
    )

    original_delete = db.delete
    delete_calls = {"count": 0}

    async def flaky_delete(item):
        delete_calls["count"] += 1
        if delete_calls["count"] == 2:
            raise RuntimeError("simulated delete failure")
        return await original_delete(item)

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with (
        patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider),
        patch.object(db, "delete", AsyncMock(side_effect=flaky_delete)),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="start_new_chat",
                history=[],
                user=user,
                routing_reason="new_chat_session_started",
            )
        )

    remaining_keys = {
        item.key for item in (await db.execute(select(MemoryItem).where(MemoryItem.user_id == user_id))).scalars().all()
    }
    assert result.status == "error"
    assert "agreement_a" in remaining_keys
    assert "agreement_b" in remaining_keys
    assert "agreement_v2" not in remaining_keys
    assert result.artifacts["created_item_ids"] == []
    assert len(result.artifacts["failed_groups"]) == 1
    assert result.artifacts["failed_groups"][0]["reason"] == "delete_failed:RuntimeError"


@pytest.mark.anyio
async def test_priority_review_skips_out_of_scope_status_drift(specialist, db_with_test_user):
    db, user = db_with_test_user
    item = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="time_expressions_v1",
        content="Problem with time expressions.",
        status="mastered",
        priority=6,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    planned_group = PlannedGroup(
        group_id="group_1",
        bucket_label="Time expressions",
        source_item_ids=[item.id],
        source_keys=[item.key],
        final_key="time_expressions_v2",
        final_content=item.content,
        final_status="struggling",
        why=f"Anchor item id={item.id} key={item.key} singleton group.",
        target_item_id=item.id,
        target_key=item.key,
    )
    suggestion = PrioritySuggestion(
        group_id="group_1",
        priority=2,
        why=f"Anchor item id={item.id} key={item.key} is important.",
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        report = await specialist._apply_priority_review(
            user_id=user.id,
            planned_groups=[planned_group],
            suggestions=[suggestion],
            dry_run=False,
        )

    await db.refresh(item)
    assert item.priority == 6
    assert report["priority_updates"] == []
    assert len(report["priority_skips"]) == 1
    assert report["priority_skips"][0]["reason"] == "priority_update_failed:ValueError"


@pytest.mark.anyio
async def test_memory_maintainer_cli_priority_review_can_apply_existing_priority(specialist, db_with_test_user):
    db, user = db_with_test_user
    first = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="time_expressions_v1",
        content="Problem with time expressions.",
        status="struggling",
        priority=6,
    )
    second = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="time_expressions_v1_repeat",
        content="Still struggles with time expressions.",
        status="struggling",
        priority=4,
    )
    db.add_all([first, second])
    await db.commit()
    await db.refresh(first)
    await db.refresh(second)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Time expressions",
                    item_ids=[first.id, second.id],
                    why=f"Anchor item id={second.id} key={second.key} defines the bucket.",
                )
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[first.id, second.id],
                        final_key="time_expressions_v2",
                        final_content="Problem with time expressions remains persistent.",
                        final_status="struggling",
                        why=f"Anchor item id={second.id} key={second.key} anchors the merged group.",
                    )
                ]
            )
        ],
        priority_plan=PriorityReviewPlan(
            suggestions=[
                PrioritySuggestion(
                    group_id="group_1",
                    priority=2,
                    why=f"Anchor item id={second.id} key={second.key} is important for YKI time-expression accuracy.",
                )
            ]
        ),
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run_cli_for_user(
            user,
            dry_run=False,
            with_priority_review=True,
        )

    merged_item = (
        (
            await db.execute(
                select(MemoryItem).where(MemoryItem.user_id == user.id, MemoryItem.key == "time_expressions_v2")
            )
        )
        .scalars()
        .one()
    )
    assert result.status == "action_taken"
    assert merged_item.priority == 2
    assert len(result.artifacts["priority_updates"]) == 1
    assert result.artifacts["priority_updates"][0]["from_priority"] == 4
    assert result.artifacts["priority_updates"][0]["to_priority"] == 2


@pytest.mark.anyio
async def test_memory_maintainer_cli_dry_run_priority_review_does_not_count_suggestions_as_applied(
    specialist, db_with_test_user
):
    db, user = db_with_test_user
    first = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="article_usage_v1",
        content="Problem with article usage.",
        status="struggling",
        priority=5,
    )
    second = MemoryItem(
        user_id=user.id,
        category="area_to_improve",
        key="article_usage_v1_repeat",
        content="Still has article usage issues.",
        status="struggling",
        priority=3,
    )
    db.add_all([first, second])
    await db.commit()
    await db.refresh(first)
    await db.refresh(second)

    _wire_structured_models(
        specialist.model,
        bucket_plan=BucketTopicsPlan(
            buckets=[
                BucketTopicGroup(
                    bucket_label="Articles",
                    item_ids=[first.id, second.id],
                    why=f"Anchor item id={second.id} key={second.key} defines this bucket.",
                )
            ]
        ),
        bucket_resolutions=[
            BucketResolutionPlan(
                groups=[
                    BucketResolutionGroup(
                        item_ids=[first.id, second.id],
                        final_key="article_usage_v2",
                        final_content="Problem with article usage remains persistent.",
                        final_status="struggling",
                        why=f"Anchor item id={second.id} key={second.key} anchors the merged article topic.",
                    )
                ]
            )
        ],
        priority_plan=PriorityReviewPlan(
            suggestions=[
                PrioritySuggestion(
                    group_id="group_1",
                    priority=1,
                    why=f"Anchor item id={second.id} key={second.key} is high-impact for YKI output accuracy.",
                )
            ]
        ),
    )

    @asynccontextmanager
    async def fake_provider():
        yield MemoryItemService(MemoryItemRepository(db))

    with patch("runestone.agents.specialists.memory_maintainer.provide_memory_item_service", fake_provider):
        result = await specialist.run_cli_for_user(
            user,
            dry_run=True,
            with_priority_review=True,
        )

    await db.refresh(first)
    await db.refresh(second)
    assert result.status == "action_taken"
    assert result.artifacts["summary"] == "dry_run planned_merges=1 suggested_priorities=1"
    assert first.priority == 5
    assert second.priority == 3
    assert len(result.artifacts["priority_updates"]) == 1
    assert result.artifacts["priority_updates"][0]["mode"] == "suggested"
