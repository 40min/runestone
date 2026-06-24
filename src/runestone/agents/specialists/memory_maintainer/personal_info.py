"""Structured personal-info maintainer that reconciles raw facts into one summary."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Literal

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from runestone.agents.llm import build_chat_model
from runestone.agents.schemas import AgentPersonalInfoStatus
from runestone.agents.service_providers import provide_memory_item_service, provide_user_service
from runestone.agents.specialists.base import BaseSpecialist, SpecialistAction, SpecialistContext, SpecialistResult
from runestone.api.memory_item_schemas import MemoryCategory
from runestone.config import Settings
from runestone.core.exceptions import MemoryItemNotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

PERSONAL_INFO_BUCKET_TOPICS_PROMPT = """
You are Bjorn, an internal learner-memory maintenance specialist.
You do not interact with the student.

Step 1: group the provided `personal_info` rows into candidate topic buckets for later review.

Each row has a `status` that signals its role in the workflow:
- `active`: a current fact row — the primary representation of that personal attribute.
- `correction`: a newer replacement fact — it supersedes the same-attribute active row.
- `outdated`: a removal instruction — it retires the same-attribute active row.

Grouping rules:
- Every input item must appear in exactly one bucket.
- Do not omit any item id.
- Do not repeat any item id in multiple buckets.
- Put rows in the same bucket when they refer to the same underlying personal attribute over time,
  even if the wording, key, or status differs.
- A `correction` or `outdated` row almost always belongs in the same bucket as the `active` row
  it targets — look at the key and content to identify the link.
- Prefer singleton buckets when unsure whether two rows describe the same attribute.
- Buckets must stay semantically tight. Do not create broad catch-all buckets like "background",
  "miscellaneous", or "personal facts".
- Before returning, verify that the union of all `item_ids` exactly matches the provided `all_item_ids`.

`why` field rules:
- Use the `why` field only for multi-item buckets.
- Every multi-item bucket must include a non-empty `why`.
- In `why`, name the anchor item by id and key (usually the `active` row) and briefly explain
  what shared personal attribute connects the items.
- For singleton buckets, omit `why`.

Return valid JSON matching the provided schema.
"""

PERSONAL_INFO_REVIEW_BUCKET_PROMPT = """
You are Bjorn, an internal learner-memory maintenance specialist.
You do not interact with the student.

Step 2a: review one candidate bucket and partition it into final exact same-topic groups.

Each row has a `status` that signals its role in the history of that personal attribute:
- `active`: the standing fact as it was last recorded.
- `correction`: a newer version of the same fact that should replace the active row.
- `outdated`: a removal request that should retire the same-topic active row.

Rules:
- Every supplied item in this bucket must appear in exactly one final group.
- A final group may contain one item or many items.
- Use a multi-item group only when the items are truly the same personal fact over time
  or direct corrections/removals of that same fact.
- Prefer separate groups when uncertain.
- Within a same-topic group, reason chronologically using `updated_at` and `status_changed_at`.
- A `correction` row almost always belongs in the same group as the `active` row it replaces.
- An `outdated` row almost always belongs in the same group as the `active` row it retires.
- Use the `why` field to explain why grouped items are the same fact rather than merely related.
- Before returning, verify that every supplied item id appears in exactly one final group.

Return valid JSON matching the provided schema.
"""

PERSONAL_INFO_BAKE_GROUP_PROMPT = """
You are Bjorn, an internal learner-memory maintenance specialist.
You do not interact with the student.

Step 2b: resolve one reviewed same-topic personal-info group into its final outcome.

Each row has a `status` that signals its role in the history of that personal attribute:
- `active`: the standing fact as it was last recorded.
- `correction`: a newer version of the same fact — its content is the replacement to carry forward.
- `outdated`: a removal request — it means the fact should no longer exist in memory.

Rules:
- The supplied source items already represent one exact personal fact over time.
- Reason chronologically using `updated_at` and `status_changed_at` to determine the latest intent.
- Decide whether the group should produce one final active fact or no surviving fact.
- Use `bake_active` when the latest intent is to keep or update the fact.
  - The content of the most recent `correction` row is usually the best final content.
  - If all rows are `active` with no removal signal, the newest content wins.
- Use `delete_all` when the latest intent is removal — i.e. the most recent row is `outdated`
  and no later `correction` overrides it.
- If `bake_active`, produce one final `key` and one final `content`.
- The final key should usually reuse the clearest existing topic key or a close normalized variant.
- The final content must be one concise stable English fact for teacher memory.
- Do not preserve workflow wording such as "forget", "remove", "correction", or "requested removal".
- Do not invent facts not supported by the source rows.

Return valid JSON matching the provided schema.
"""

PERSONAL_INFO_SUMMARY_PROMPT = """
You are Bjorn, an internal learner-memory maintenance specialist.
You do not interact with the student.

Step 3: synthesize one concise `personal_info_summary` from the active facts only.

Rules:
- Use only the supplied active facts.
- The supplied list already represents the final active fact set for this run, even if some
  rows still carry a pre-apply workflow status such as `correction`.
- Write a compact third-person summary for internal teacher use across future chats.
- Keep it factual and stable. Do not include speculation.
- Exclude transient expired daily-state details such as "today", "tomorrow", or expired
  date-specific work/rest status by comparing facts against the provided current datetime.
- Mention the student's current goals, preferences, or background only when present in the source facts.
- Omit raw ids, keys, and status labels.
- If the active facts are empty, return an empty summary.

Return valid JSON matching the schema.
"""


class BucketTopicGroup(BaseModel):
    """Structured output for step-1 topic bucketing."""

    bucket_label: str = Field(..., min_length=1)
    item_ids: list[int] = Field(default_factory=list)
    why: str | None = None


class BucketTopicsPlan(BaseModel):
    """Structured output for the full step-1 bucketing pass."""

    buckets: list[BucketTopicGroup] = Field(default_factory=list)


class BucketReviewGroup(BaseModel):
    """One reviewed same-topic group emitted from step 2a."""

    item_ids: list[int] = Field(default_factory=list)
    why: str = Field(..., min_length=1)


class BucketReviewPlan(BaseModel):
    """Structured output for the step-2a review of one bucket."""

    groups: list[BucketReviewGroup] = Field(default_factory=list)


class BakeGroupPlan(BaseModel):
    """Structured output for resolving one same-topic group."""

    outcome: Literal["bake_active", "delete_all"]
    final_key: str | None = None
    final_content: str | None = None
    why: str = Field(..., min_length=1)


class PersonalInfoSummaryPlan(BaseModel):
    """Structured output for derived personal-info summary synthesis."""

    summary: str = ""


@dataclass
class PersonalInfoExecutionReport:
    """Execution report for one personal-info maintenance run."""

    kept_active_item_ids: list[int]
    outdated_item_ids: list[int]
    deleted_item_ids: list[int]
    summary: str | None


@dataclass
class PlannedGroupResolution:
    """Runtime representation of one resolved multi-item personal-info group."""

    bucket_label: str
    source_item_ids: list[int]
    source_keys: list[str]
    outcome: Literal["bake_active", "delete_all"]
    final_key: str | None
    final_content: str | None
    why: str
    created_item_id: int | None = None


class PersonalInfoMemoryMaintainer(BaseSpecialist):
    """Background specialist that reconciles raw personal-info facts."""

    MODEL_TIMEOUT_SECONDS = 30.0

    def __init__(self, settings: Settings):
        super().__init__(name="memory_maintainer")
        self.settings = settings
        self.model = build_chat_model(settings, "memory_maintainer", timeout_seconds=self.MODEL_TIMEOUT_SECONDS)

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        """Run the personal-info maintainer through the shared specialist contract."""
        return await self.run_for_user(context.user)

    async def run_for_user(self, user: Any) -> SpecialistResult:
        """Run personal-info maintenance in background mode."""
        return await self.run_session(user=user, dry_run=False, trigger_source="chat_reset")

    async def run_cli_for_user(self, user: Any, *, dry_run: bool) -> SpecialistResult:
        """Run personal-info maintenance for CLI inspection or application."""
        return await self.run_session(user=user, dry_run=dry_run, trigger_source="cli")

    async def run_session(
        self,
        *,
        user: Any,
        dry_run: bool,
        trigger_source: Literal["chat_reset", "cli"],
    ) -> SpecialistResult:
        """Execute personal-info review, summary synthesis, and optional persistence."""
        started_at = perf_counter()
        user_id = int(getattr(user, "id"))
        artifacts = self._base_artifacts(trigger_source=trigger_source, dry_run=dry_run)
        logger.info(
            "[agents:memorymaintainer] personal_info run started user_id=%s trigger=%s dry_run=%s",
            user_id,
            trigger_source,
            dry_run,
        )

        try:
            scope_items = await self._load_scope_items(user_id=user_id)
        except Exception as exc:
            logger.warning("[agents:memorymaintainer] Failed to load personal_info scope: %s", exc, exc_info=True)
            artifacts["summary"] = "scope_load_failed"
            artifacts["step_errors"].append("scope_load_failed")
            return self._error_result("Failed to load personal_info scope", artifacts)

        artifacts["reviewed_item_count"] = len(scope_items)
        items_by_id = {item.id: item for item in scope_items}
        if not scope_items:
            current_summary = getattr(user, "personal_info_summary", None)
            if current_summary:
                if not dry_run:
                    async with provide_user_service() as user_service:
                        await user_service.set_personal_info_summary(user_id, None)
                artifacts["summary"] = "cleared_empty_summary" if not dry_run else "dry_run cleared_empty_summary"
                artifacts["persisted_summary"] = None
                return self._action_result(artifacts["summary"], artifacts)

            artifacts["summary"] = "noop"
            artifacts["no_change_reason"] = "no_personal_info_items"
            return self._no_action_result(artifacts)

        try:
            # Step 1: ask the model for broad candidate topic buckets, then deterministically
            # repair common output defects like duplicate ids or dropped singleton items.
            bucket_plan = await self._bucket_topics(scope_items=scope_items)
            if bucket_plan is None:
                artifacts["summary"] = "bucket_plan_failed"
                artifacts["step_errors"].append("bucket_plan_failed")
                return self._error_result("Failed to bucket personal_info items", artifacts)

            repaired_bucket_plan = self._repair_bucket_plan(bucket_plan, items_by_id)
            validated_buckets = self._validate_bucket_plan(repaired_bucket_plan, items_by_id)
            if validated_buckets is None:
                artifacts["summary"] = "invalid_bucket_plan"
                artifacts["step_errors"].append("invalid_bucket_plan")
                return self._error_result("Personal-info bucket plan was invalid", artifacts)

            logger.info(
                "[agents:memorymaintainer] personal_info bucket step completed "
                "user_id=%s bucket_count=%s elapsed_s=%.2f",
                user_id,
                len(validated_buckets),
                perf_counter() - started_at,
            )
            artifacts["buckets"] = [
                {
                    "bucket_label": bucket.bucket_label,
                    "item_ids": bucket.item_ids,
                    "item_keys": [items_by_id[item_id].key for item_id in bucket.item_ids],
                    **({} if not bucket.why else {"why": bucket.why}),
                }
                for bucket in validated_buckets
            ]

            planned_resolutions: list[PlannedGroupResolution] = []
            untouched_active_items: list[Any] = []

            # Step 2: process each bucket. Singleton buckets are resolved deterministically:
            # active rows stay untouched; correction rows are baked to active in-place;
            # outdated rows are queued for deletion without an LLM call.
            # Multi-item buckets go through a review pass followed by a bake pass per group.
            for bucket in validated_buckets:
                bucket_items = [items_by_id[item_id] for item_id in bucket.item_ids]

                if len(bucket.item_ids) == 1:
                    item = bucket_items[0]
                    status = item.status
                    if status == AgentPersonalInfoStatus.ACTIVE.value:
                        # No change needed — keep as-is.
                        untouched_active_items.append(item)
                    elif status == AgentPersonalInfoStatus.CORRECTION.value:
                        # A correction with no prior fact to supersede: bake in-place to active.
                        planned_resolutions.append(
                            PlannedGroupResolution(
                                bucket_label=bucket.bucket_label,
                                source_item_ids=[item.id],
                                source_keys=[item.key],
                                outcome="bake_active",
                                final_key=item.key,
                                final_content=item.content,
                                why="Singleton correction row baked to active in-place.",
                            )
                        )
                    elif status == AgentPersonalInfoStatus.OUTDATED.value:
                        # A retirement row with no remaining active counterpart: delete it.
                        planned_resolutions.append(
                            PlannedGroupResolution(
                                bucket_label=bucket.bucket_label,
                                source_item_ids=[item.id],
                                source_keys=[item.key],
                                outcome="delete_all",
                                final_key=None,
                                final_content=None,
                                why="Singleton outdated row deleted — no surviving fact.",
                            )
                        )
                    else:
                        # Unknown status; leave untouched conservatively.
                        untouched_active_items.append(item)
                    continue

                review = await self._review_bucket(
                    bucket_label=bucket.bucket_label,
                    bucket_why=bucket.why,
                    scope_items=bucket_items,
                )
                if review is None:
                    artifacts["step_errors"].append(f"bucket_review_failed:{bucket.bucket_label}")
                    # Fallback: preserve existing active items so they are not lost from the summary.
                    for item in bucket_items:
                        if item.status == AgentPersonalInfoStatus.ACTIVE.value:
                            untouched_active_items.append(item)
                    continue

                validated_groups = self._validate_bucket_review_plan(review, bucket_items)
                if validated_groups is None:
                    artifacts["step_errors"].append(f"invalid_bucket_review:{bucket.bucket_label}")
                    # Fallback: preserve existing active items so they are not lost from the summary.
                    for item in bucket_items:
                        if item.status == AgentPersonalInfoStatus.ACTIVE.value:
                            untouched_active_items.append(item)
                    continue

                for group in validated_groups:
                    if len(group.item_ids) == 1:
                        item = items_by_id[group.item_ids[0]]
                        status = item.status
                        if status == AgentPersonalInfoStatus.ACTIVE.value:
                            untouched_active_items.append(item)
                        else:
                            # correction or outdated singleton group → queue for deletion so
                            # it is actually removed instead of being silently dropped.
                            planned_resolutions.append(
                                PlannedGroupResolution(
                                    bucket_label=bucket.bucket_label,
                                    source_item_ids=[item.id],
                                    source_keys=[item.key],
                                    outcome="delete_all",
                                    final_key=None,
                                    final_content=None,
                                    why=f"Non-active singleton in multi-item bucket review: {group.why}",
                                )
                            )
                        continue

                    bake_plan = await self._bake_group(
                        bucket_label=bucket.bucket_label,
                        reviewed_group=group,
                        scope_items=[items_by_id[item_id] for item_id in group.item_ids],
                    )
                    if bake_plan is None:
                        artifacts["step_errors"].append(f"bake_group_failed:{bucket.bucket_label}:{group.item_ids}")
                        continue

                    planned_resolutions.append(
                        PlannedGroupResolution(
                            bucket_label=bucket.bucket_label,
                            source_item_ids=group.item_ids,
                            source_keys=[items_by_id[item_id].key for item_id in group.item_ids],
                            outcome=bake_plan.outcome,
                            final_key=bake_plan.final_key,
                            final_content=bake_plan.final_content,
                            why=bake_plan.why,
                        )
                    )

            # Step 3: synthesize summary from the final active fact set.
            synthetic_active_items = [
                self._synthetic_active_item(plan) for plan in planned_resolutions if plan.outcome == "bake_active"
            ]
            active_items = [*untouched_active_items, *synthetic_active_items]
            artifacts["summary_source_item_ids"] = [
                *[item.id for item in untouched_active_items],
                *[
                    item_id
                    for plan in planned_resolutions
                    if plan.outcome == "bake_active"
                    for item_id in plan.source_item_ids
                ],
            ]
            artifacts["baked_groups"] = [
                {
                    "bucket_label": plan.bucket_label,
                    "item_ids": plan.source_item_ids,
                    "item_keys": plan.source_keys,
                    "outcome": plan.outcome,
                    **(
                        {"final_key": plan.final_key, "final_content": plan.final_content}
                        if plan.outcome == "bake_active"
                        else {}
                    ),
                    "why": plan.why,
                }
                for plan in planned_resolutions
            ]
            artifacts["summary_excluded_item_ids"] = [
                item_id
                for plan in planned_resolutions
                if plan.outcome == "delete_all"
                for item_id in plan.source_item_ids
            ]

            summary_text: str | None = None
            if active_items:
                summary_plan = await self._synthesize_summary(active_items=active_items)
                if summary_plan is None:
                    artifacts["summary"] = "summary_failed"
                    artifacts["step_errors"].append("summary_failed")
                    return self._error_result("Failed to synthesize personal_info summary", artifacts)
                summary_text = summary_plan.summary.strip() or None
            artifacts["summary_preview"] = summary_text

            if dry_run:
                artifacts["kept_active_item_ids"] = [item.id for item in untouched_active_items]
                artifacts["outdated_item_ids"] = []
                artifacts["deleted_item_ids"] = [
                    item_id for plan in planned_resolutions for item_id in plan.source_item_ids
                ]
                artifacts["persisted_summary"] = summary_text
                artifacts["summary"] = (
                    f"dry_run kept_active={len(artifacts['kept_active_item_ids'])} "
                    f"outdated={len(artifacts['outdated_item_ids'])} deleted={len(artifacts['deleted_item_ids'])}"
                )
                return self._action_result(artifacts["summary"], artifacts)

            report = await self._apply_plan(
                user_id=user_id,
                planned_resolutions=planned_resolutions,
                untouched_active_items=untouched_active_items,
                target_summary=summary_text,
            )

            artifacts["kept_active_item_ids"] = report.kept_active_item_ids
            artifacts["outdated_item_ids"] = report.outdated_item_ids
            artifacts["deleted_item_ids"] = report.deleted_item_ids
            artifacts["persisted_summary"] = report.summary
            artifacts["summary"] = (
                f"kept_active={len(report.kept_active_item_ids)} "
                f"outdated={len(report.outdated_item_ids)} deleted={len(report.deleted_item_ids)}"
            )
            logger.info(
                "[agents:memorymaintainer] personal_info run finished user_id=%s elapsed_s=%.2f",
                user_id,
                perf_counter() - started_at,
            )
            if (
                report.kept_active_item_ids
                or report.outdated_item_ids
                or report.deleted_item_ids
                or report.summary is not None
            ):
                return self._action_result(artifacts["summary"], artifacts)
            return self._no_action_result(artifacts)
        except Exception as exc:
            logger.warning("[agents:memorymaintainer] personal_info execution failed: %s", exc, exc_info=True)
            artifacts["summary"] = "execution_failed"
            artifacts["step_errors"].append(f"execution_failed:{type(exc).__name__}")
            return self._error_result("Failed to execute personal_info maintenance", artifacts)

    async def _load_scope_items(self, *, user_id: int) -> list[Any]:
        """Load the full personal-info scope, including internal workflow rows."""
        async with provide_memory_item_service() as service:
            scope_items = await service.list_memory_items(
                user_id=user_id,
                category=MemoryCategory.PERSONAL_INFO,
                limit=None,
            )
        return scope_items

    async def _bucket_topics(self, *, scope_items: list[Any]) -> BucketTopicsPlan | None:
        """Run the step-1 topic bucketing model."""
        current_datetime = self._current_datetime_iso()
        payload = {
            "current_datetime": current_datetime,
            "all_item_ids": [item.id for item in scope_items],
            "items": [self._serialize_scope_item(item) for item in scope_items],
        }
        return await self._invoke_structured_model(
            BucketTopicsPlan,
            system_prompt=(
                f"{PERSONAL_INFO_BUCKET_TOPICS_PROMPT}\n\nCurrent datetime: {current_datetime}\n"
                "Use this timestamp when deciding whether facts are current, corrected, retired, or temporary."
            ),
            payload=payload,
            step_name="personal_info_bucket_topics",
        )

    async def _review_bucket(
        self,
        *,
        bucket_label: str,
        bucket_why: str | None,
        scope_items: list[Any],
    ) -> BucketReviewPlan | None:
        """Run the step-2a bucket review model for one candidate bucket."""
        current_datetime = self._current_datetime_iso()
        ordered_items = self._sort_items_chronologically(scope_items)
        payload = {
            "current_datetime": current_datetime,
            "bucket": {
                "bucket_label": bucket_label,
                "why": bucket_why,
                "all_item_ids": [item.id for item in ordered_items],
                "items": [self._serialize_scope_item(item) for item in ordered_items],
            },
        }
        return await self._invoke_structured_model(
            BucketReviewPlan,
            system_prompt=(
                f"{PERSONAL_INFO_REVIEW_BUCKET_PROMPT}\n\nCurrent datetime: {current_datetime}\n"
                "Use this timestamp when reasoning about chronology and temporary facts."
            ),
            payload=payload,
            step_name=f"personal_info_review_bucket:{bucket_label}",
        )

    async def _bake_group(
        self,
        *,
        bucket_label: str,
        reviewed_group: BucketReviewGroup,
        scope_items: list[Any],
    ) -> BakeGroupPlan | None:
        """Run the step-2b bake model for one reviewed same-topic group."""
        current_datetime = self._current_datetime_iso()
        ordered_items = self._sort_items_chronologically(scope_items)
        payload = {
            "current_datetime": current_datetime,
            "bucket_label": bucket_label,
            "reviewed_group": {
                "item_ids": reviewed_group.item_ids,
                "why": reviewed_group.why,
                "items": [self._serialize_scope_item(item) for item in ordered_items],
            },
        }
        return await self._invoke_structured_model(
            BakeGroupPlan,
            system_prompt=(
                f"{PERSONAL_INFO_BAKE_GROUP_PROMPT}\n\nCurrent datetime: {current_datetime}\n"
                "Use this timestamp when deciding whether the fact still survives."
            ),
            payload=payload,
            step_name=f"personal_info_bake_group:{bucket_label}:{reviewed_group.item_ids}",
        )

    async def _synthesize_summary(self, *, active_items: list[Any]) -> PersonalInfoSummaryPlan | None:
        """Run the step-3 summary synthesis model over the final active fact set."""
        current_datetime = self._current_datetime_iso()
        payload = {
            "current_datetime": current_datetime,
            "active_items": [self._serialize_scope_item(item) for item in active_items],
        }
        return await self._invoke_structured_model(
            PersonalInfoSummaryPlan,
            system_prompt=(
                f"{PERSONAL_INFO_SUMMARY_PROMPT}\n\nCurrent datetime: {current_datetime}\n"
                "Use this timestamp to avoid including expired temporary facts in the summary."
            ),
            payload=payload,
            step_name="personal_info_summary",
        )

    async def _invoke_structured_model(
        self,
        schema: type[BaseModel],
        *,
        system_prompt: str,
        payload: dict[str, Any],
        step_name: str,
    ) -> BaseModel | None:
        """Invoke the configured chat model with a structured-output schema."""
        with_structured_output = getattr(self.model, "with_structured_output", None)
        if not callable(with_structured_output):
            logger.warning("[agents:memorymaintainer] Model does not support structured output for %s", step_name)
            return None

        structured_model = with_structured_output(schema)
        call_started_at = perf_counter()
        logger.info(
            "[agents:memorymaintainer] llm step started step=%s item_count=%s",
            step_name,
            len(payload.get("items", [])) if isinstance(payload.get("items"), list) else None,
        )
        try:
            result = await structured_model.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ]
            )
            logger.info(
                "[agents:memorymaintainer] llm step finished step=%s elapsed_s=%.2f",
                step_name,
                perf_counter() - call_started_at,
            )
            return result
        except OutputParserException as exc:
            logger.warning(
                "[agents:memorymaintainer] %s schema validation failed after %.2fs: %s",
                step_name,
                perf_counter() - call_started_at,
                exc,
            )
            return None
        except Exception as exc:
            logger.warning(
                "[agents:memorymaintainer] %s failed after %.2fs: %s",
                step_name,
                perf_counter() - call_started_at,
                exc,
                exc_info=True,
            )
            return None

    @staticmethod
    def _validate_bucket_plan(
        bucket_plan: BucketTopicsPlan,
        items_by_id: dict[int, Any],
    ) -> list[BucketTopicGroup] | None:
        """Ensure step-1 buckets cover each source item exactly once."""
        seen_ids: set[int] = set()
        validated: list[BucketTopicGroup] = []

        for bucket in bucket_plan.buckets:
            if not bucket.item_ids:
                logger.warning(
                    "[agents:memorymaintainer] personal_info invalid bucket plan: empty bucket label=%s",
                    bucket.bucket_label,
                )
                return None
            unique_ids = list(dict.fromkeys(bucket.item_ids))
            if any(item_id not in items_by_id for item_id in unique_ids):
                logger.warning(
                    "[agents:memorymaintainer] personal_info invalid bucket plan: unknown ids label=%s",
                    bucket.bucket_label,
                )
                return None
            if len(unique_ids) > 1 and not bucket.why:
                logger.warning(
                    "[agents:memorymaintainer] personal_info invalid bucket plan: missing why label=%s ids=%s",
                    bucket.bucket_label,
                    unique_ids,
                )
                return None
            if seen_ids.intersection(unique_ids):
                logger.warning(
                    "[agents:memorymaintainer] personal_info invalid bucket plan: duplicate ids label=%s",
                    bucket.bucket_label,
                )
                return None
            seen_ids.update(unique_ids)
            bucket.item_ids = unique_ids
            validated.append(bucket)

        if seen_ids != set(items_by_id):
            missing = sorted(set(items_by_id) - seen_ids)
            logger.warning(
                "[agents:memorymaintainer] personal_info invalid bucket plan: missing ids=%s",
                missing,
            )
            return None
        return validated

    def _repair_bucket_plan(
        self,
        bucket_plan: BucketTopicsPlan,
        items_by_id: dict[int, Any],
    ) -> BucketTopicsPlan:
        """Repair common step-1 model issues without changing the broad taxonomy."""
        seen_ids: set[int] = set()
        repaired_buckets: list[BucketTopicGroup] = []
        removed_unknown_ids = 0
        removed_duplicate_ids = 0
        synthesized_whys = 0
        dropped_empty_buckets = 0

        for bucket in bucket_plan.buckets:
            repaired_ids: list[int] = []
            for item_id in bucket.item_ids:
                if item_id not in items_by_id:
                    removed_unknown_ids += 1
                    continue
                if item_id in seen_ids:
                    removed_duplicate_ids += 1
                    continue
                seen_ids.add(item_id)
                repaired_ids.append(item_id)
            if not repaired_ids:
                dropped_empty_buckets += 1
                continue
            repaired_why = bucket.why
            if len(repaired_ids) > 1 and not repaired_why:
                anchor_item = items_by_id[repaired_ids[0]]
                repaired_why = (
                    f"Deterministic repair anchor item id={anchor_item.id} key={anchor_item.key} "
                    "keeps this bucket together after the model omitted why."
                )
                synthesized_whys += 1
            repaired_buckets.append(
                BucketTopicGroup(
                    bucket_label=bucket.bucket_label,
                    item_ids=repaired_ids,
                    why=repaired_why,
                )
            )

        recovered_singletons = 0
        for item_id in sorted(set(items_by_id) - seen_ids):
            item = items_by_id[item_id]
            repaired_buckets.append(
                BucketTopicGroup(
                    bucket_label=f"Recovered singleton: {item.key}",
                    item_ids=[item_id],
                    why=None,
                )
            )
            recovered_singletons += 1

        if (
            removed_unknown_ids
            or removed_duplicate_ids
            or synthesized_whys
            or dropped_empty_buckets
            or recovered_singletons
        ):
            logger.info(
                "[agents:memorymaintainer] personal_info repaired bucket plan "
                "removed_unknown=%s removed_duplicate=%s synthesized_whys=%s "
                "dropped_empty=%s recovered_singletons=%s final_bucket_count=%s",
                removed_unknown_ids,
                removed_duplicate_ids,
                synthesized_whys,
                dropped_empty_buckets,
                recovered_singletons,
                len(repaired_buckets),
            )

        return BucketTopicsPlan(buckets=repaired_buckets)

    @staticmethod
    def _validate_bucket_review_plan(
        review: BucketReviewPlan,
        bucket_items: list[Any],
    ) -> list[BucketReviewGroup] | None:
        """Ensure step-2a review groups cover the bucket exactly once."""
        bucket_ids = {item.id for item in bucket_items}
        seen_ids: set[int] = set()
        validated: list[BucketReviewGroup] = []

        for group in review.groups:
            if not group.item_ids or not group.why:
                return None
            unique_ids = list(dict.fromkeys(group.item_ids))
            if any(item_id not in bucket_ids for item_id in unique_ids):
                return None
            if seen_ids.intersection(unique_ids):
                return None
            seen_ids.update(unique_ids)
            group.item_ids = unique_ids
            validated.append(group)

        if seen_ids != bucket_ids:
            return None
        return validated

    @staticmethod
    def _sort_items_chronologically(items: list[Any]) -> list[Any]:
        def _dt(value: Any) -> datetime:
            if isinstance(value, datetime):
                return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
            return datetime.min.replace(tzinfo=timezone.utc)

        return sorted(
            items,
            key=lambda item: (
                _dt(getattr(item, "updated_at", None)),
                _dt(getattr(item, "status_changed_at", None)),
                getattr(item, "id", 0),
            ),
        )

    @staticmethod
    def _current_datetime() -> datetime:
        """Return the current UTC datetime for temporal review and retention checks."""
        return datetime.now(timezone.utc)

    def _current_datetime_iso(self) -> str:
        """Return the current UTC datetime so the model can reason about temporal facts."""
        return self._current_datetime().isoformat()

    async def _apply_plan(
        self,
        *,
        user_id: int,
        planned_resolutions: list[PlannedGroupResolution],
        untouched_active_items: list[Any],
        target_summary: str | None,
    ) -> PersonalInfoExecutionReport:
        kept_active_item_ids: list[int] = [item.id for item in untouched_active_items]
        outdated_item_ids: list[int] = []
        deleted_item_ids: list[int] = []

        async with provide_memory_item_service() as service:
            all_source_ids = [item_id for plan in planned_resolutions for item_id in plan.source_item_ids]
            current_by_id = {}
            if all_source_ids:
                current_items = await service.get_items_by_ids(all_source_ids)
                current_by_id = {item.id: item for item in current_items}

            for plan in planned_resolutions:
                missing_ids = [item_id for item_id in plan.source_item_ids if item_id not in current_by_id]
                if missing_ids:
                    raise MemoryItemNotFoundError(f"Memory items with ids {missing_ids} not found")

                ordered_items = self._sort_items_chronologically(
                    [current_by_id[item_id] for item_id in plan.source_item_ids]
                )
                for item in ordered_items:
                    if item.user_id != user_id:
                        raise PermissionDeniedError("You don't have permission to update this item")
                    if item.category != MemoryCategory.PERSONAL_INFO.value:
                        raise ValueError(f"out_of_scope_category:{item.id}:{item.category}")

                if plan.outcome == "bake_active":
                    if not plan.final_key or not plan.final_content:
                        raise ValueError("invalid_bake_plan:missing_final_fields")
                    created_item_candidate = self._build_baked_item(
                        user_id=user_id,
                        final_key=plan.final_key,
                        final_content=plan.final_content,
                    )
                    created_item, deleted_ids = await service.create_item_and_delete_sources(
                        item=created_item_candidate,
                        source_items=ordered_items,
                    )
                    plan.created_item_id = created_item.id
                    kept_active_item_ids.append(created_item.id)
                    deleted_item_ids.extend(deleted_ids)
                else:
                    for item in ordered_items:
                        await service.delete_item(item.id, user_id, commit=False)
                        deleted_item_ids.append(item.id)
                    await service.repo.db.commit()

        async with provide_user_service() as user_service:
            await user_service.set_personal_info_summary(user_id, target_summary)

        return PersonalInfoExecutionReport(
            kept_active_item_ids=kept_active_item_ids,
            outdated_item_ids=outdated_item_ids,
            deleted_item_ids=deleted_item_ids,
            summary=target_summary,
        )

    @staticmethod
    def _synthetic_active_item(plan: PlannedGroupResolution) -> Any:
        return type(
            "SyntheticPersonalInfoItem",
            (),
            {
                "id": 0,
                "key": plan.final_key,
                "content": plan.final_content,
                "status": AgentPersonalInfoStatus.ACTIVE.value,
                "updated_at": None,
                "status_changed_at": None,
            },
        )()

    def _build_baked_item(self, *, user_id: int, final_key: str, final_content: str):
        from runestone.db.models import MemoryItem

        return MemoryItem(
            user_id=user_id,
            category=MemoryCategory.PERSONAL_INFO.value,
            key=final_key,
            content=final_content,
            status=AgentPersonalInfoStatus.ACTIVE.value,
            status_changed_at=self._current_datetime(),
        )

    @staticmethod
    def _serialize_datetime(value: Any) -> str | None:
        """Convert datetime-like values into ISO strings for prompt payloads."""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return None

    @staticmethod
    def _serialize_scope_item(item: Any) -> dict[str, Any]:
        """Serialize a scope item for structured prompts."""
        return {
            "id": item.id,
            "key": item.key,
            "content": item.content,
            "status": item.status,
            "updated_at": PersonalInfoMemoryMaintainer._serialize_datetime(getattr(item, "updated_at", None)),
            "status_changed_at": PersonalInfoMemoryMaintainer._serialize_datetime(
                getattr(item, "status_changed_at", None)
            ),
        }

    @staticmethod
    def _base_artifacts(*, trigger_source: str, dry_run: bool) -> dict[str, Any]:
        return {
            "maintenance_type": "personal_info_memory_maintenance",
            "scope": {"category": "personal_info"},
            "trigger_source": trigger_source,
            "dry_run": dry_run,
            "reviewed_item_count": 0,
            "buckets": [],
            "baked_groups": [],
            "kept_active_item_ids": [],
            "outdated_item_ids": [],
            "deleted_item_ids": [],
            "summary_source_item_ids": [],
            "summary_excluded_item_ids": [],
            "summary_preview": None,
            "persisted_summary": None,
            "step_errors": [],
            "summary": "",
            "no_change_reason": None,
        }

    @staticmethod
    def _action_result(summary: str, artifacts: dict[str, Any]) -> SpecialistResult:
        return SpecialistResult(
            status="action_taken",
            actions=[SpecialistAction(tool="memory_maintainer", status="success", summary=summary)],
            info_for_teacher="",
            artifacts=artifacts,
        )

    @staticmethod
    def _no_action_result(artifacts: dict[str, Any]) -> SpecialistResult:
        return SpecialistResult(status="no_action", actions=[], info_for_teacher="", artifacts=artifacts)

    @staticmethod
    def _error_result(summary: str, artifacts: dict[str, Any]) -> SpecialistResult:
        return SpecialistResult(
            status="error",
            actions=[SpecialistAction(tool="memory_maintainer", status="error", summary=summary)],
            info_for_teacher="",
            artifacts=artifacts,
        )
