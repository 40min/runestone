"""Structured multi-pass maintainer for area_to_improve memory cleanup."""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Literal

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from runestone.agents.llm import build_chat_model
from runestone.agents.service_providers import provide_memory_item_service
from runestone.agents.specialists.base import BaseSpecialist, SpecialistAction, SpecialistContext, SpecialistResult
from runestone.api.memory_item_schemas import AreaToImproveStatus, MemoryCategory
from runestone.config import Settings
from runestone.constants import MEMORY_DEFAULT_AREA_TO_IMPROVE_PRIORITY
from runestone.core.exceptions import MemoryItemNotFoundError, PermissionDeniedError
from runestone.db.models import MemoryItem

logger = logging.getLogger(__name__)

MAINTAINER_STATUSES = (
    AreaToImproveStatus.STRUGGLING.value,
    AreaToImproveStatus.IMPROVING.value,
)
UNVERSIONED_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
MERGED_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*_v[0-9]+$")
VERSIONED_OR_UNVERSIONED_KEY_PATTERN = re.compile(r"^(?P<base>[a-z0-9]+(?:_[a-z0-9]+)*?)(?:_v(?P<version>[0-9]+))?$")

BUCKET_TOPICS_PROMPT = """
You are Bjorn, an internal Swedish-learning memory maintenance specialist.
You do not interact with the student.

Step 1: group the provided memory items into candidate topic buckets for later review.

Rules:
- Review only the supplied `area_to_improve` items with status `struggling` or `improving`.
- Every input item must appear in exactly one bucket.
- Do not omit any item id.
- Do not repeat any item id in multiple buckets.
- If one item could fit multiple themes, choose its single dominant teachable topic and assign it once.
- Prefer more buckets over fewer when unsure.
- Buckets must stay semantically tight and teachable.
- A bucket with more than 15 items is almost certainly too broad and should be split into smaller buckets.
- Do not create broad catch-all buckets such as "other grammar", "mixed vocabulary", or
  "prepositions and other issues".
- Do not create generic buckets such as "advanced constructions", "edge cases", "miscellaneous",
  or "other vocabulary".
- Do not mix unrelated domains into one bucket. In particular, avoid combining vocabulary,
  spelling, word order, prepositions, and general grammar unless they are clearly the same
  teachable topic.
- A broad "vocabulary" bucket is not valid. Vocabulary items must be split into smaller buckets
  based on one exact confusion pair, one lexical distinction, one construction, or one semantic field.
- If a bucket would become too broad, split it into smaller buckets.
- If an item is hard to place, put it into a small dedicated edge-case bucket instead of
  dropping it or forcing it into an unrelated bucket.
- Edge-case buckets are valid for topics such as adjective comparison, date formatting or
  ordinal numbers, pronoun consistency across clauses, or a narrow adjective-ending nuance.
- An edge-case bucket should usually contain 1 to 3 items, not dozens of unrelated leftovers.
- Use the `why` field only for buckets that contain multiple items.
- Every multi-item bucket must include a non-empty `why`. Null or empty `why` is invalid for multi-item buckets.
- In `why`, mention the main anchor/base item by id and key that best represents the bucket.
- For singleton buckets, omit `why` to save tokens.
- Keep the response conservative. If two items are not clearly related, keep them in separate buckets.
- Before returning, perform a final coverage sweep: if any id from `all_item_ids` is not yet assigned,
  create a small dedicated bucket for it instead of omitting it.
- Before returning, verify that the union of all `item_ids` exactly matches the provided
  `all_item_ids` list, with no missing ids and no duplicates.

Return valid JSON matching the provided schema.
"""

REVIEW_BUCKET_PROMPT = """
You are Bjorn, an internal Swedish-learning memory maintenance specialist.
You do not interact with the student.

Step 2a: review one candidate bucket and partition it into final same-topic groups.

Rules:
- Every supplied item in this bucket must appear in exactly one final group.
- A final group may contain one item or many items.
- Use a multi-item group only when the items are nearly the same teachable topic.
- Prefer separate groups when uncertain.
- A multi-item group should usually contain 2 to 4 items. Groups larger than 4 are suspicious and
  should be split unless the items are obvious near-duplicates of one exact teachable rule.
- If similar items have different statuses, merge them only when they are truly near-duplicates.
- When a multi-item group contains status changes over time, the latest status must win.
- Never group items just because they are all "grammar", all "vocabulary", or all "advanced".
- Do not create merged topics like "grammar and usage", "advanced syntax", "vocabulary distinctions",
  or other umbrella summaries that mix many subtopics.
- For vocabulary-related items, merge only one exact confusion pair, one fixed construction, one
  word-family issue, or one tiny semantic cluster at a time.
- For grammar-related items, merge only one exact rule or one very tight rule family at a time.
- If items are merely related but not the same topic, split them into separate final groups
  instead of forcing one status.
- Use the `why` field to justify the grouping choice and explain which source item is the
  anchor/base item.
- In `why`, explicitly state why the grouped items are the same teachable topic rather than
  merely related.
- `why` is validation-only and is not persisted, so be explicit.
- Before returning, verify that every supplied item id appears in exactly one final group.

Return valid JSON matching the provided schema.
"""

GENERATE_MERGE_PROMPT = """
You are Bjorn, an internal Swedish-learning memory maintenance specialist.
You do not interact with the student.

Step 2b: generate one merged memory item for one reviewed same-topic group.

Rules:
- The supplied source items have already been reviewed as one exact teachable topic.
- Write one fresh final content text in the target language while preserving the key meaning.
- The final content must describe the student's recurring error or weakness, not give direct study instructions.
- Write it as an observation about the student, for example:
  - "The student often makes errors with ..."
  - "The student confuses ..."
  - "The student still struggles with ..."
- The content should sound like a concise memory note for a teacher or agent,
  not like homework instructions for the student.
- Do not write imperative coaching text such as "practice", "remember", "master", "use", or "learn".
- Do not write broad textbook explanations unless they are tied back to the student's observed error pattern.
- Include at least one short concrete example of the student's error or
  confusion when the source items contain such an example.
- Prefer wording that summarizes the student's error pattern first, then briefly mentions the relevant rule or contrast.
- Keep Swedish study examples unchanged when they are part of the learning content.
- Final keys must be fresh English snake_case key stems using ASCII letters, digits, and underscores only.
- Do not add any version suffix such as `_v1` or `_v2`; Python will assign versions later.
- Never reuse any original key.
- The final status must reflect the latest status across the supplied source items.
- Use the `why` field to explain the anchor/base item and what shared rule or concept is preserved.

Return valid JSON matching the provided schema.
"""

VALIDATE_MERGE_PROMPT = """
You are Bjorn, an internal Swedish-learning memory maintenance specialist.
You do not interact with the student.

Step 2c: validate one proposed merged memory item before it can be accepted.

Rules:
- Approve the merge only if all supplied source items clearly represent one exact teachable topic.
- Reject the merge if the items are merely related, broader than one teachable rule, or should
  stay separate for practice clarity.
- Reject umbrella merges that mix different rules, different lexical distinctions, or unrelated
  examples under one summary.
- Be conservative. If you are uncertain, reject the merge.
- Use the `why` field to explain the approval or rejection in concrete teaching terms.

Return valid JSON matching the provided schema.
"""

PRIORITY_REVIEW_PROMPT = """
You are Bjorn, an internal Swedish-learning memory maintenance specialist.
You do not interact with the student.

Step 3: review the final maintenance groups and suggest priorities.

Rules:
- Suggest priorities only for the supplied final groups.
- Lower numbers mean higher urgency.
- Consider:
  1. how important the topic is for YKI exam success
  2. how much friction is visible from the number of merged source items
- Be conservative and keep the scale stable.
- Use the `why` field to explain the decision and mention the main anchor/base item in the group.

Return valid JSON matching the provided schema.
"""


class BucketTopicGroup(BaseModel):
    """Structured output for step-1 topic bucketing."""

    bucket_label: str = Field(..., min_length=1, description="Short human-readable label for the bucket")
    item_ids: list[int] = Field(default_factory=list, description="Source item ids included in this bucket")
    why: str | None = Field(default=None, description="Validation-only explanation for multi-item buckets")


class BucketTopicsPlan(BaseModel):
    """Structured output for the full step-1 bucketing pass."""

    buckets: list[BucketTopicGroup] = Field(default_factory=list)


class BucketReviewGroup(BaseModel):
    """One reviewed same-topic group emitted from step 2a."""

    item_ids: list[int] = Field(default_factory=list, description="Source item ids covered by this reviewed group")
    why: str = Field(..., min_length=1, description="Validation-only reasoning for this reviewed group")


class BucketReviewPlan(BaseModel):
    """Structured output for the step-2a review of one bucket."""

    groups: list[BucketReviewGroup] = Field(default_factory=list)


class MergeGeneration(BaseModel):
    """Structured output for one generated merged item in step 2b."""

    final_key: str = Field(..., min_length=1, max_length=100, description="Fresh English snake_case key stem")
    final_content: str = Field(..., min_length=1, max_length=1000, description="Fresh final content text")
    final_status: Literal["struggling", "improving"] = Field(..., description="Winning final status")
    why: str = Field(..., min_length=1, description="Validation-only reasoning for this final group")


class MergeValidation(BaseModel):
    """Structured output for validating one generated merge proposal."""

    approved: bool = Field(..., description="Whether the proposed merge is one exact teachable topic")
    why: str = Field(..., min_length=1, description="Validation-only approval or rejection reason")


class PrioritySuggestion(BaseModel):
    """Optional CLI-only priority review for one final group."""

    group_id: str = Field(..., min_length=1, description="Stable runtime group id")
    priority: int = Field(..., ge=0, le=9, description="Suggested priority where 0 is highest urgency")
    why: str = Field(..., min_length=1, description="Validation-only explanation for the priority")


class PriorityReviewPlan(BaseModel):
    """Structured output for the step-3 priority review."""

    suggestions: list[PrioritySuggestion] = Field(default_factory=list)


@dataclass
class PlannedGroup:
    """Runtime representation of one resolved final group."""

    group_id: str
    bucket_label: str
    source_item_ids: list[int]
    source_keys: list[str]
    final_key: str
    final_content: str
    final_status: str
    why: str
    target_item_id: int | None = None
    target_key: str | None = None


class AreaToImproveMemoryMaintainer(BaseSpecialist):
    """Background specialist that consolidates start-of-session learning-focus memory."""

    def __init__(self, settings: Settings):
        super().__init__(name="memory_maintainer")
        self.settings = settings
        self.model = build_chat_model(settings, "memory_maintainer")
        logger.info(
            "[agents:memorymaintainer] Initialized AreaToImproveMemoryMaintainer with provider=%s, model=%s",
            settings.memory_maintainer_provider,
            settings.memory_maintainer_model,
        )

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        """Run the background chat-reset maintenance flow via the shared specialist contract."""
        return await self.run_for_user(context.user)

    async def run_for_user(self, user: Any) -> SpecialistResult:
        """Run chat-reset maintenance for one user without building a full specialist context."""
        return await self.run_session(
            user=user,
            dry_run=False,
            with_priority_review=False,
            trigger_source="chat_reset",
        )

    async def run_cli_for_user(
        self,
        user: Any,
        *,
        dry_run: bool,
        with_priority_review: bool,
    ) -> SpecialistResult:
        """Run the maintainer in CLI mode for one user without building a full specialist context."""
        return await self.run_session(
            user=user,
            dry_run=dry_run,
            with_priority_review=with_priority_review,
            trigger_source="cli",
        )

    async def run_session(
        self,
        user: Any,
        *,
        dry_run: bool,
        with_priority_review: bool,
        trigger_source: Literal["chat_reset", "cli"],
    ) -> SpecialistResult:
        """Execute the full structured maintenance pipeline."""
        started_at = perf_counter()
        user_id = int(getattr(user, "id"))
        language = self._memory_item_language(user)
        artifacts = self._base_artifacts(
            trigger_source=trigger_source,
            dry_run=dry_run,
            with_priority_review=with_priority_review,
        )
        logger.info(
            "[agents:memorymaintainer] run started user_id=%s trigger=%s dry_run=%s priority_review=%s",
            user_id,
            trigger_source,
            dry_run,
            with_priority_review,
        )

        try:
            async with provide_memory_item_service() as service:
                scope_items = await service.list_memory_items(
                    user_id=user_id,
                    category=MemoryCategory.AREA_TO_IMPROVE,
                    statuses=list(MAINTAINER_STATUSES),
                    limit=200,
                    offset=0,
                )
        except Exception as exc:
            logger.warning("[agents:memorymaintainer] Failed to load scope items: %s", exc, exc_info=True)
            artifacts["summary"] = "scope_load_failed"
            artifacts["step_errors"].append("scope_load_failed")
            return self._error_result("Failed to load maintainer scope", artifacts)

        artifacts["reviewed_item_count"] = len(scope_items)
        logger.info(
            "[agents:memorymaintainer] scope loaded user_id=%s item_count=%s elapsed_s=%.2f",
            user_id,
            len(scope_items),
            perf_counter() - started_at,
        )
        if not scope_items:
            artifacts["summary"] = "noop"
            artifacts["no_change_reason"] = "no_in_scope_items"
            return self._no_action_result(artifacts)

        # Step 0: load the stable scope once so every later LLM pass sees the same
        # in-scope snapshot unless execution-time drift is detected explicitly.
        items_by_id = {item.id: item for item in scope_items}

        # Step 1: ask the model for broad candidate buckets, then deterministically
        # repair common output defects like duplicate ids or dropped singleton items.
        bucket_plan = await self._bucket_topics(scope_items=scope_items, target_language=language)
        if bucket_plan is None:
            artifacts["summary"] = "bucket_plan_failed"
            artifacts["step_errors"].append("bucket_plan_failed")
            return self._error_result("Failed to bucket memory items", artifacts)
        logger.info(
            "[agents:memorymaintainer] bucket step completed user_id=%s bucket_count=%s elapsed_s=%.2f",
            user_id,
            len(bucket_plan.buckets),
            perf_counter() - started_at,
        )

        repaired_bucket_plan = self._repair_bucket_plan(bucket_plan, items_by_id)
        validated_buckets = self._validate_bucket_plan(repaired_bucket_plan, items_by_id)
        if validated_buckets is None:
            artifacts["summary"] = "invalid_bucket_plan"
            artifacts["step_errors"].append("invalid_bucket_plan")
            return self._error_result("Bucket plan was invalid", artifacts)

        artifacts["buckets"] = [
            {
                "bucket_label": bucket.bucket_label,
                "item_ids": bucket.item_ids,
                "item_keys": [items_by_id[item_id].key for item_id in bucket.item_ids],
                **({"why": bucket.why} if bucket.why else {}),
            }
            for bucket in validated_buckets
        ]

        planned_groups: list[PlannedGroup] = []
        next_group_number = 1
        merge_candidate_buckets = [bucket for bucket in validated_buckets if len(bucket.item_ids) > 1]
        singleton_item_ids = [bucket.item_ids[0] for bucket in validated_buckets if len(bucket.item_ids) == 1]
        if singleton_item_ids:
            logger.info(
                "[agents:memorymaintainer] skipping singleton buckets user_id=%s count=%s item_ids=%s elapsed_s=%.2f",
                user_id,
                len(singleton_item_ids),
                singleton_item_ids,
                perf_counter() - started_at,
            )

        # Step 2: process only multi-item candidate buckets. Each bucket goes through
        # a review pass, merge generation pass, and final validator pass before it can
        # become an executable planned merge.
        for bucket in merge_candidate_buckets:
            bucket_items = [items_by_id[item_id] for item_id in bucket.item_ids]
            logger.info(
                "[agents:memorymaintainer] resolving bucket user_id=%s label=%s item_count=%s elapsed_s=%.2f",
                user_id,
                bucket.bucket_label,
                len(bucket.item_ids),
                perf_counter() - started_at,
            )
            review = await self._review_bucket(
                bucket_label=bucket.bucket_label,
                bucket_why=bucket.why,
                scope_items=bucket_items,
            )
            if review is None:
                artifacts["step_errors"].append(f"bucket_review_failed:{bucket.bucket_label}")
                continue

            validated_groups = self._validate_review_plan(review, bucket_items)
            if validated_groups is None:
                artifacts["step_errors"].append(f"invalid_bucket_review:{bucket.bucket_label}")
                continue

            for group in validated_groups:
                if len(group.item_ids) < 2:
                    logger.info(
                        "[agents:memorymaintainer] resolution produced singleton group "
                        "user_id=%s label=%s item_ids=%s; leaving untouched",
                        user_id,
                        bucket.bucket_label,
                        group.item_ids,
                    )
                    continue
                merge_generation = await self._generate_merge_group(
                    bucket_label=bucket.bucket_label,
                    reviewed_group=group,
                    scope_items=[items_by_id[item_id] for item_id in group.item_ids],
                    target_language=language,
                )
                if merge_generation is None:
                    artifacts["step_errors"].append(f"merge_generation_failed:{bucket.bucket_label}:{group.item_ids}")
                    continue
                merge_validation = await self._validate_merge_group(
                    bucket_label=bucket.bucket_label,
                    reviewed_group=group,
                    scope_items=[items_by_id[item_id] for item_id in group.item_ids],
                    merge_generation=merge_generation,
                    target_language=language,
                )
                if merge_validation is None:
                    artifacts["step_errors"].append(f"merge_validation_failed:{bucket.bucket_label}:{group.item_ids}")
                    continue
                if not merge_validation.approved:
                    # Validator rejections are treated as "leave untouched" instead of
                    # hard failures because the safest fallback is to keep the original items.
                    logger.info(
                        "[agents:memorymaintainer] rejected generated merge user_id=%s label=%s item_ids=%s reason=%s",
                        user_id,
                        bucket.bucket_label,
                        group.item_ids,
                        merge_validation.why,
                    )
                    continue
                normalized_status = self._latest_status([items_by_id[item_id] for item_id in group.item_ids])
                if normalized_status != merge_generation.final_status:
                    logger.info(
                        "[agents:memorymaintainer] normalized resolved group status "
                        "user_id=%s label=%s item_ids=%s from=%s to=%s",
                        user_id,
                        bucket.bucket_label,
                        group.item_ids,
                        merge_generation.final_status,
                        normalized_status,
                    )
                planned_groups.append(
                    PlannedGroup(
                        group_id=f"group_{next_group_number}",
                        bucket_label=bucket.bucket_label,
                        source_item_ids=group.item_ids,
                        source_keys=[items_by_id[item_id].key for item_id in group.item_ids],
                        final_key=merge_generation.final_key,
                        final_content=merge_generation.final_content,
                        final_status=normalized_status,
                        why=merge_generation.why,
                    )
                )
                next_group_number += 1

        if not planned_groups:
            artifacts["summary"] = "no_valid_groups"
            artifacts["no_change_reason"] = "no_merge_candidates"
            logger.info(
                "[agents:memorymaintainer] no merge candidates user_id=%s elapsed_s=%.2f",
                user_id,
                perf_counter() - started_at,
            )
            return self._no_action_result(artifacts)

        # Step 3: priority review is intentionally CLI-only so background chat reset
        # work stays focused on safe merge planning and execution.
        priority_suggestions: list[PrioritySuggestion] = []
        if with_priority_review:
            logger.info(
                "[agents:memorymaintainer] priority review started user_id=%s merge_group_count=%s elapsed_s=%.2f",
                user_id,
                len(planned_groups),
                perf_counter() - started_at,
            )
            priority_review = await self._review_priorities(
                planned_groups=planned_groups,
                items_by_id=items_by_id,
                target_language=language,
            )
            if priority_review is None:
                artifacts["step_errors"].append("priority_review_failed")
            else:
                priority_suggestions = priority_review.suggestions

        # Step 4: execute the accepted merge groups in Python with per-group validation,
        # create-first persistence, and partial-failure tolerance.
        execution_report = await self._execute_groups(
            user_id=user_id,
            planned_groups=planned_groups,
            dry_run=dry_run,
        )
        artifacts.update(execution_report)

        if with_priority_review and priority_suggestions:
            priority_report = await self._apply_priority_review(
                user_id=user_id,
                planned_groups=planned_groups,
                suggestions=priority_suggestions,
                dry_run=dry_run,
            )
            artifacts["priority_updates"] = priority_report["priority_updates"]
            artifacts["priority_skips"] = priority_report["priority_skips"]
        else:
            artifacts["priority_updates"] = []
            artifacts["priority_skips"] = []

        planned_merge_count = len(artifacts["merged_groups"]) if dry_run else 0
        applied_merge_count = len(artifacts["merged_groups"]) if not dry_run else 0
        failed_merge_count = len(artifacts["failed_groups"])
        applied_priority_count = len(
            [update for update in artifacts["priority_updates"] if update.get("mode") == "applied"]
        )
        suggested_priority_count = len(priority_suggestions)

        if dry_run and planned_merge_count:
            artifacts["summary"] = (
                f"dry_run planned_merges={planned_merge_count} suggested_priorities={suggested_priority_count}"
            )
            return self._action_result(artifacts["summary"], artifacts)

        if applied_merge_count or applied_priority_count:
            artifacts["summary"] = (
                f"applied_merges={applied_merge_count} failed_merges={failed_merge_count} "
                f"applied_priorities={applied_priority_count}"
            )
            return self._action_result(artifacts["summary"], artifacts)

        if failed_merge_count or artifacts["step_errors"]:
            artifacts["summary"] = f"failed_merges={failed_merge_count} step_errors={len(artifacts['step_errors'])}"
            return self._error_result("Maintenance execution finished with failures", artifacts)

        artifacts["summary"] = "noop"
        artifacts["no_change_reason"] = "no_merge_candidates"
        return self._no_action_result(artifacts)

    async def _bucket_topics(
        self,
        *,
        scope_items: list[Any],
        target_language: str,
    ) -> BucketTopicsPlan | None:
        """Run the step-1 topic bucketing model."""
        payload = {
            "target_language": target_language,
            "all_item_ids": [item.id for item in scope_items],
            "items": [self._serialize_scope_item(item) for item in scope_items],
        }
        return await self._invoke_structured_model(
            BucketTopicsPlan,
            system_prompt=BUCKET_TOPICS_PROMPT,
            payload=payload,
            step_name="bucket_topics",
        )

    async def _review_bucket(
        self,
        *,
        bucket_label: str,
        bucket_why: str,
        scope_items: list[Any],
    ) -> BucketReviewPlan | None:
        """Run the step-2a bucket review model for one bucket."""
        payload = {
            "bucket": {
                "bucket_label": bucket_label,
                "why": bucket_why,
                "all_item_ids": [item.id for item in scope_items],
                "items": [self._serialize_scope_item(item) for item in scope_items],
            },
        }
        return await self._invoke_structured_model(
            BucketReviewPlan,
            system_prompt=REVIEW_BUCKET_PROMPT,
            payload=payload,
            step_name=f"review_bucket:{bucket_label}",
        )

    async def _generate_merge_group(
        self,
        *,
        bucket_label: str,
        reviewed_group: BucketReviewGroup,
        scope_items: list[Any],
        target_language: str,
    ) -> MergeGeneration | None:
        """Run the step-2b merge generation model for one reviewed same-topic group."""
        payload = {
            "target_language": target_language,
            "bucket_label": bucket_label,
            "reviewed_group": {
                "item_ids": reviewed_group.item_ids,
                "why": reviewed_group.why,
                "items": [self._serialize_scope_item(item) for item in scope_items],
            },
        }
        return await self._invoke_structured_model(
            MergeGeneration,
            system_prompt=GENERATE_MERGE_PROMPT,
            payload=payload,
            step_name=f"generate_merge:{bucket_label}:{reviewed_group.item_ids}",
        )

    async def _validate_merge_group(
        self,
        *,
        bucket_label: str,
        reviewed_group: BucketReviewGroup,
        scope_items: list[Any],
        merge_generation: MergeGeneration,
        target_language: str,
    ) -> MergeValidation | None:
        """Run the step-2c validation model for one generated merge proposal."""
        payload = {
            "target_language": target_language,
            "bucket_label": bucket_label,
            "reviewed_group": {
                "item_ids": reviewed_group.item_ids,
                "why": reviewed_group.why,
                "items": [self._serialize_scope_item(item) for item in scope_items],
            },
            "proposed_merge": {
                "final_key": merge_generation.final_key,
                "final_content": merge_generation.final_content,
                "final_status": merge_generation.final_status,
                "why": merge_generation.why,
            },
        }
        return await self._invoke_structured_model(
            MergeValidation,
            system_prompt=VALIDATE_MERGE_PROMPT,
            payload=payload,
            step_name=f"validate_merge:{bucket_label}:{reviewed_group.item_ids}",
        )

    async def _review_priorities(
        self,
        *,
        planned_groups: list[PlannedGroup],
        items_by_id: dict[int, Any],
        target_language: str,
    ) -> PriorityReviewPlan | None:
        """Run the optional CLI-only priority review model."""
        payload = {
            "target_language": target_language,
            "groups": [
                {
                    "group_id": group.group_id,
                    "bucket_label": group.bucket_label,
                    "source_item_ids": group.source_item_ids,
                    "source_keys": group.source_keys,
                    "source_statuses": [items_by_id[item_id].status for item_id in group.source_item_ids],
                    "source_priorities": [items_by_id[item_id].priority for item_id in group.source_item_ids],
                    "final_key": group.final_key,
                    "final_status": group.final_status,
                    "final_content": group.final_content,
                    "why": group.why,
                }
                for group in planned_groups
            ],
        }
        return await self._invoke_structured_model(
            PriorityReviewPlan,
            system_prompt=PRIORITY_REVIEW_PROMPT,
            payload=payload,
            step_name="priority_review",
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

    async def _execute_groups(
        self,
        *,
        user_id: int,
        planned_groups: list[PlannedGroup],
        dry_run: bool,
    ) -> dict[str, Any]:
        """Validate and execute merge groups, or validate only in dry-run mode."""
        report = {
            "merged_groups": [],
            "failed_groups": [],
            "created_item_ids": [],
            "deleted_item_ids": [],
        }
        reserved_final_keys: set[str] = set()

        async with provide_memory_item_service() as service:
            existing_area_keys = await service.list_item_keys(user_id, MemoryCategory.AREA_TO_IMPROVE)
            for group in planned_groups:
                normalized_key = self._normalize_generated_key(
                    group.final_key,
                    existing_area_keys,
                    reserved_final_keys,
                )
                key_error = self._validate_generated_key(normalized_key, group.source_keys)
                if key_error is not None:
                    report["failed_groups"].append(
                        {
                            "group_id": group.group_id,
                            "item_ids": group.source_item_ids,
                            "item_keys": group.source_keys,
                            "final_key": normalized_key,
                            "reason": key_error,
                        }
                    )
                    continue
                group.final_key = normalized_key
                if group.final_key in reserved_final_keys:
                    report["failed_groups"].append(
                        {
                            "group_id": group.group_id,
                            "item_ids": group.source_item_ids,
                            "item_keys": group.source_keys,
                            "final_key": group.final_key,
                            "reason": "duplicate_target_key",
                        }
                    )
                    continue
                reserved_final_keys.add(group.final_key)

                current_items, validation_error = await self._validate_group_state(
                    service=service,
                    user_id=user_id,
                    group=group,
                )
                if validation_error:
                    report["failed_groups"].append(
                        {
                            "group_id": group.group_id,
                            "item_ids": group.source_item_ids,
                            "item_keys": group.source_keys,
                            "final_key": group.final_key,
                            "reason": validation_error,
                        }
                    )
                    continue

                existing_target = await service.get_item_by_user_category_key(
                    user_id,
                    MemoryCategory.AREA_TO_IMPROVE,
                    group.final_key,
                )
                if existing_target is not None:
                    report["failed_groups"].append(
                        {
                            "group_id": group.group_id,
                            "item_ids": group.source_item_ids,
                            "item_keys": group.source_keys,
                            "final_key": group.final_key,
                            "reason": "duplicate_target_key",
                        }
                    )
                    continue

                if dry_run:
                    report["merged_groups"].append(self._planned_group_artifact(group))
                    continue

                try:
                    self._validate_merged_item_fields(group)
                    created_item_candidate = MemoryItem(
                        user_id=user_id,
                        category=MemoryCategory.AREA_TO_IMPROVE.value,
                        key=group.final_key,
                        content=group.final_content,
                        status=group.final_status,
                        priority=self._merged_priority(current_items),
                        status_changed_at=self._utc_now(),
                    )
                    created_item, deleted_ids = await service.create_item_and_delete_sources(
                        item=created_item_candidate,
                        source_items=current_items,
                    )
                except (ValueError, RuntimeError) as exc:
                    report["failed_groups"].append(
                        {
                            "group_id": group.group_id,
                            "item_ids": group.source_item_ids,
                            "item_keys": group.source_keys,
                            "final_key": group.final_key,
                            "reason": str(exc),
                        }
                    )
                    continue

                group.target_item_id = created_item.id
                group.target_key = created_item.key
                report["created_item_ids"].append(created_item.id)
                report["deleted_item_ids"].extend(deleted_ids)
                report["merged_groups"].append(
                    {
                        "group_id": group.group_id,
                        "bucket_label": group.bucket_label,
                        "item_ids": group.source_item_ids,
                        "item_keys": group.source_keys,
                        "final_key": group.final_key,
                        "created_item_id": created_item.id,
                        "final_status": group.final_status,
                        "deleted_item_ids": deleted_ids,
                    }
                )

        return report

    async def _apply_priority_review(
        self,
        *,
        user_id: int,
        planned_groups: list[PlannedGroup],
        suggestions: list[PrioritySuggestion],
        dry_run: bool,
    ) -> dict[str, list[dict[str, Any]]]:
        """Apply or report CLI-only priority review suggestions."""
        suggestion_by_group = {suggestion.group_id: suggestion for suggestion in suggestions}
        priority_updates: list[dict[str, Any]] = []
        priority_skips: list[dict[str, Any]] = []

        if dry_run:
            for group in planned_groups:
                suggestion = suggestion_by_group.get(group.group_id)
                if suggestion is None:
                    continue
                priority_updates.append(
                    {
                        "group_id": group.group_id,
                        "item_id": None,
                        "key": group.final_key if len(group.source_item_ids) > 1 else group.source_keys[0],
                        "from_priority": None,
                        "to_priority": suggestion.priority,
                        "reason": suggestion.why,
                        "mode": "suggested",
                    }
                )
            return {"priority_updates": priority_updates, "priority_skips": priority_skips}

        async with provide_memory_item_service() as service:
            for group in planned_groups:
                suggestion = suggestion_by_group.get(group.group_id)
                if suggestion is None:
                    continue

                target_item_id = group.target_item_id
                if target_item_id is None:
                    priority_skips.append(
                        {
                            "group_id": group.group_id,
                            "key": group.final_key,
                            "reason": "missing_priority_target",
                        }
                    )
                    continue

                try:
                    before_item = await service.get_item_by_id(target_item_id)
                    if before_item is None:
                        raise MemoryItemNotFoundError(f"Memory item with id {target_item_id} not found")
                    if before_item.user_id != user_id:
                        raise PermissionDeniedError("You don't have permission to update this item")
                    if before_item.category != MemoryCategory.AREA_TO_IMPROVE.value:
                        raise ValueError("priority target category drifted out of scope")
                    if before_item.status not in MAINTAINER_STATUSES:
                        raise ValueError("priority target status drifted out of scope")
                    old_priority, updated_item = await service.update_item_priority_with_old_value(
                        target_item_id,
                        suggestion.priority,
                        user_id,
                    )
                except (MemoryItemNotFoundError, PermissionDeniedError, ValueError) as exc:
                    priority_skips.append(
                        {
                            "group_id": group.group_id,
                            "item_id": target_item_id,
                            "key": group.target_key or group.final_key,
                            "reason": f"priority_update_failed:{type(exc).__name__}",
                        }
                    )
                    continue

                priority_updates.append(
                    {
                        "group_id": group.group_id,
                        "item_id": updated_item.id,
                        "key": updated_item.key,
                        "from_priority": old_priority,
                        "to_priority": updated_item.priority,
                        "reason": suggestion.why,
                        "mode": "applied",
                    }
                )

        return {"priority_updates": priority_updates, "priority_skips": priority_skips}

    async def _validate_group_state(
        self,
        *,
        service,
        user_id: int,
        group: PlannedGroup,
    ) -> tuple[list[MemoryItem], str | None]:
        """Validate source item state before applying one merge group."""
        current_items = await service.get_items_by_ids(group.source_item_ids)
        current_by_id = {item.id: item for item in current_items}
        missing_ids = [item_id for item_id in group.source_item_ids if item_id not in current_by_id]
        if missing_ids:
            return [], f"missing_source_items:{missing_ids}"

        ordered_items = [current_by_id[item_id] for item_id in group.source_item_ids]
        for item in ordered_items:
            if item.user_id != user_id:
                return [], f"wrong_user:{item.id}"
            if item.category != MemoryCategory.AREA_TO_IMPROVE.value:
                return [], f"out_of_scope_category:{item.id}:{item.category}"
            if item.status not in MAINTAINER_STATUSES:
                return [], f"out_of_scope_status:{item.id}:{item.status}"

        latest_status = self._latest_status(ordered_items)
        if group.final_status != latest_status:
            return [], f"status_drift:expected_{group.final_status}:latest_{latest_status}"

        return ordered_items, None

    def _validate_bucket_plan(
        self,
        bucket_plan: BucketTopicsPlan,
        items_by_id: dict[int, Any],
    ) -> list[BucketTopicGroup] | None:
        """Ensure step-1 buckets cover each source item exactly once."""
        seen_ids: set[int] = set()
        validated: list[BucketTopicGroup] = []

        for bucket in bucket_plan.buckets:
            if not bucket.item_ids:
                logger.warning(
                    "[agents:memorymaintainer] Invalid bucket plan: empty bucket label=%s", bucket.bucket_label
                )
                return None
            unique_ids = list(dict.fromkeys(bucket.item_ids))
            if any(item_id not in items_by_id for item_id in unique_ids):
                invalid_ids = [item_id for item_id in unique_ids if item_id not in items_by_id]
                logger.warning(
                    "[agents:memorymaintainer] Invalid bucket plan: unknown ids=%s label=%s",
                    invalid_ids,
                    bucket.bucket_label,
                )
                return None
            if len(unique_ids) > 1 and not bucket.why:
                logger.warning(
                    "[agents:memorymaintainer] Invalid bucket plan: missing why for multi-item bucket label=%s ids=%s",
                    bucket.bucket_label,
                    unique_ids,
                )
                return None
            duplicate_ids = sorted(seen_ids.intersection(unique_ids))
            if duplicate_ids:
                logger.warning(
                    "[agents:memorymaintainer] Invalid bucket plan: duplicate ids=%s label=%s",
                    duplicate_ids,
                    bucket.bucket_label,
                )
                return None
            seen_ids.update(unique_ids)
            bucket.item_ids = unique_ids
            validated.append(bucket)

        if set(items_by_id) != seen_ids:
            missing_ids = sorted(set(items_by_id) - seen_ids)
            logger.warning(
                "[agents:memorymaintainer] Invalid bucket plan: missing ids=%s covered=%s expected=%s",
                missing_ids,
                len(seen_ids),
                len(items_by_id),
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
                    "keeps this multi-item bucket together after the model omitted why."
                )
                synthesized_whys += 1

            repaired_buckets.append(
                BucketTopicGroup(
                    bucket_label=bucket.bucket_label,
                    item_ids=repaired_ids,
                    why=repaired_why,
                )
            )

        missing_ids = sorted(set(items_by_id) - seen_ids)
        recovered_singletons = 0
        for item_id in missing_ids:
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
                "[agents:memorymaintainer] repaired bucket plan removed_unknown_ids=%s removed_duplicate_ids=%s "
                "synthesized_whys=%s dropped_empty_buckets=%s recovered_singletons=%s final_bucket_count=%s",
                removed_unknown_ids,
                removed_duplicate_ids,
                synthesized_whys,
                dropped_empty_buckets,
                recovered_singletons,
                len(repaired_buckets),
            )

        return BucketTopicsPlan(buckets=repaired_buckets)

    def _validate_review_plan(
        self,
        review: BucketReviewPlan,
        bucket_items: list[Any],
    ) -> list[BucketReviewGroup] | None:
        """Ensure step-2a review groups cover the bucket exactly once."""
        bucket_ids = {item.id for item in bucket_items}
        seen_ids: set[int] = set()
        validated: list[BucketReviewGroup] = []

        for group in review.groups:
            if not group.item_ids:
                return None
            unique_ids = list(dict.fromkeys(group.item_ids))
            if any(item_id not in bucket_ids for item_id in unique_ids):
                return None
            if seen_ids.intersection(unique_ids):
                return None
            if not group.why:
                return None
            seen_ids.update(unique_ids)
            group.item_ids = unique_ids
            validated.append(group)

        if bucket_ids != seen_ids:
            return None
        return validated

    @staticmethod
    def _validate_generated_key(final_key: str, source_keys: list[str]) -> str | None:
        """Reject model-generated keys that violate deterministic merge-key invariants."""
        if final_key in source_keys:
            return "invalid_target_key:reused_source_key"
        if not final_key.isascii():
            return "invalid_target_key:non_ascii"
        if not MERGED_KEY_PATTERN.fullmatch(final_key):
            return "invalid_target_key:format"
        return None

    @staticmethod
    def _extract_generated_key_base(key: str) -> str | None:
        """Return the semantic key stem, stripping only one trailing maintainer version suffix."""
        if not key.isascii():
            return None
        match = VERSIONED_OR_UNVERSIONED_KEY_PATTERN.fullmatch(key)
        if not match:
            return None
        return match.group("base")

    @classmethod
    def _normalize_generated_key(
        cls,
        generated_key: str,
        existing_keys: set[str],
        reserved_final_keys: set[str],
    ) -> str:
        """
        Assign the final maintainer version suffix deterministically in Python.

        The model provides the semantic key stem. If it includes a trailing
        maintainer suffix anyway, ignore that suffix and recompute the next
        version from the existing DB keys plus keys already reserved in this run.
        """
        base_key = cls._extract_generated_key_base(generated_key)
        if base_key is None:
            return generated_key

        used_versions: list[int] = []
        version_prefix = f"{base_key}_v"
        for key in existing_keys.union(reserved_final_keys):
            if not key.startswith(version_prefix):
                continue
            if not MERGED_KEY_PATTERN.fullmatch(key):
                continue
            suffix = key[len(version_prefix) :]
            if suffix.isdigit():
                used_versions.append(int(suffix))

        next_version = max(used_versions, default=0) + 1
        return f"{base_key}_v{next_version}"

    @staticmethod
    def _validate_merged_item_fields(group: PlannedGroup) -> None:
        """Validate maintainer-owned merged item fields before persistence."""
        if not isinstance(group.final_content, str) or not group.final_content.strip():
            raise ValueError("content must not be empty")
        if group.final_status not in MAINTAINER_STATUSES:
            raise ValueError(f"invalid_status:{group.final_status}")

    @staticmethod
    def _serialize_scope_item(item: Any) -> dict[str, Any]:
        """Serialize a scope item for structured prompts."""
        return {
            "id": item.id,
            "key": item.key,
            "content": item.content,
            "status": item.status,
            "priority": item.priority,
            "updated_at": AreaToImproveMemoryMaintainer._serialize_datetime(getattr(item, "updated_at", None)),
            "status_changed_at": AreaToImproveMemoryMaintainer._serialize_datetime(
                getattr(item, "status_changed_at", None)
            ),
        }

    @staticmethod
    def _serialize_datetime(value: Any) -> str | None:
        """Convert datetime-like values into ISO strings for prompt payloads."""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return None

    @staticmethod
    def _latest_status(items: list[MemoryItem]) -> str:
        """Return the latest status across a group using status-changed time first."""
        latest_item = max(items, key=AreaToImproveMemoryMaintainer._status_order_key)
        return latest_item.status

    @staticmethod
    def _status_order_key(item: MemoryItem) -> datetime:
        """Order items by their strongest evidence of latest status."""
        timestamp = item.status_changed_at or item.updated_at or item.created_at
        if timestamp is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp

    @staticmethod
    def _merged_priority(items: list[MemoryItem]) -> int:
        """Keep the most urgent source priority when creating a merged item."""
        priorities = [
            item.priority if item.priority is not None else MEMORY_DEFAULT_AREA_TO_IMPROVE_PRIORITY for item in items
        ]
        return min(priorities)

    @staticmethod
    def _planned_group_artifact(group: PlannedGroup) -> dict[str, Any]:
        """Serialize a planned final group into artifacts."""
        return {
            "group_id": group.group_id,
            "bucket_label": group.bucket_label,
            "new_key": group.final_key,
            "status": group.final_status,
            "replaced_item_ids": group.source_item_ids,
            "replaced_keys": group.source_keys,
            "why": group.why,
        }

    @staticmethod
    def _base_artifacts(
        *,
        trigger_source: str,
        dry_run: bool,
        with_priority_review: bool,
    ) -> dict[str, Any]:
        """Create the shared artifacts payload for one maintenance run."""
        return {
            "maintenance_type": (
                "cli_memory_maintenance" if trigger_source == "cli" else "chat_reset_memory_maintenance"
            ),
            "scope": {"category": "area_to_improve", "statuses": list(MAINTAINER_STATUSES)},
            "trigger_source": trigger_source,
            "dry_run": dry_run,
            "priority_review_enabled": with_priority_review,
            "reviewed_item_count": 0,
            "buckets": [],
            "merged_groups": [],
            "failed_groups": [],
            "priority_updates": [],
            "priority_skips": [],
            "created_item_ids": [],
            "deleted_item_ids": [],
            "step_errors": [],
            "summary": "",
            "no_change_reason": None,
        }

    @staticmethod
    def _action_result(summary: str, artifacts: dict[str, Any]) -> SpecialistResult:
        """Build an action-taken specialist result."""
        return SpecialistResult(
            status="action_taken",
            actions=[SpecialistAction(tool="memory_maintainer", status="success", summary=summary)],
            info_for_teacher="",
            artifacts=artifacts,
        )

    @staticmethod
    def _no_action_result(artifacts: dict[str, Any]) -> SpecialistResult:
        """Build a no-action specialist result."""
        return SpecialistResult(status="no_action", actions=[], info_for_teacher="", artifacts=artifacts)

    @staticmethod
    def _error_result(summary: str, artifacts: dict[str, Any]) -> SpecialistResult:
        """Build an error specialist result."""
        return SpecialistResult(
            status="error",
            actions=[SpecialistAction(tool="memory_maintainer", status="error", summary=summary)],
            info_for_teacher="",
            artifacts=artifacts,
        )

    @staticmethod
    def _utc_now() -> datetime:
        """Return the current UTC timestamp."""
        return datetime.now(timezone.utc)

    @staticmethod
    def _memory_item_language(user: Any) -> str:
        """Resolve the target language for rewritten memory content."""
        mother_tongue = getattr(user, "mother_tongue", None)
        if isinstance(mother_tongue, str) and mother_tongue.strip():
            return mother_tongue.strip()
        return "English"
