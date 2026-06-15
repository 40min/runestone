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
from runestone.agents.service_providers import provide_memory_item_service, provide_user_service
from runestone.agents.specialists.base import BaseSpecialist, SpecialistAction, SpecialistContext, SpecialistResult
from runestone.api.memory_item_schemas import MemoryCategory, PersonalInfoStatus
from runestone.config import Settings
from runestone.core.exceptions import MemoryItemNotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

PERSONAL_INFO_REVIEW_PROMPT = """
You are Bjorn, an internal learner-memory maintenance specialist.
You do not interact with the student.

Step 1: review raw `personal_info` memory rows and decide which rows stay active.

Rules:
- Every input item id must appear exactly once in `decisions`.
- Allowed actions:
  - `keep_active`: this row should remain the active representation of a fact
  - `mark_outdated`: this row should remain stored but no longer be active
  - `delete`: this row is a redundant duplicate that can be removed
- Be conservative about deletion. Use `delete` only for clear duplicates with no meaningful information loss.
- Resolve exact or near-exact duplicate rows as one duplicate bucket; only the newest
  survivor should remain active unless an older row clearly carries distinct historical value.
- Use `mark_outdated` for superseded or conflicting older facts that should remain as historical evidence.
- Prefer keeping the newest or clearest row active when several rows describe the same current fact.
- Delete expired short-lived status facts such as "working today", "off work today", or similar day-specific state.
- Do not delete historically meaningful dated background facts such as where the student
  lived, studied, or worked in a past year.
- There may be multiple active rows if they describe different facts about the student.
- Do not invent new rows or ids.
- `why` must briefly explain the reason for each action.

Return valid JSON matching the schema.
"""

PERSONAL_INFO_SUMMARY_PROMPT = """
You are Bjorn, an internal learner-memory maintenance specialist.
You do not interact with the student.

Step 2: synthesize one concise `personal_info_summary` from the active facts only.

Rules:
- Use only the supplied active facts.
- Write a compact third-person summary for internal teacher use across future chats.
- Keep it factual and stable. Do not include speculation.
- Exclude transient expired daily-state details such as "today", "tomorrow", or expired
  date-specific work/rest status by comparing facts against the provided current datetime.
- Mention the student's current goals, preferences, or background only when present in the source facts.
- Omit raw ids, keys, and status labels.
- If the active facts are empty, return an empty summary.

Return valid JSON matching the schema.
"""


class PersonalInfoDecision(BaseModel):
    """One row-level maintenance action for a personal_info item."""

    item_id: int
    action: Literal["keep_active", "mark_outdated", "delete"]
    why: str = Field(..., min_length=1)


class PersonalInfoReviewPlan(BaseModel):
    """Structured output for personal-info row reconciliation."""

    decisions: list[PersonalInfoDecision] = Field(default_factory=list)


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


class PersonalInfoMemoryMaintainer(BaseSpecialist):
    """Background specialist that reconciles raw personal-info facts."""

    MODEL_TIMEOUT_SECONDS = 30.0
    OUTDATED_RETENTION_DAYS = 14

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
            stale_outdated_deleted_count, scope_items = await self._cleanup_and_load_scope_items(
                user_id=user_id,
                dry_run=dry_run,
            )
        except Exception as exc:
            logger.warning("[agents:memorymaintainer] Failed to load personal_info scope: %s", exc, exc_info=True)
            artifacts["summary"] = "scope_load_failed"
            artifacts["step_errors"].append("scope_load_failed")
            return self._error_result("Failed to load personal_info scope", artifacts)

        artifacts["stale_outdated_deleted_count"] = stale_outdated_deleted_count
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
            review = await self._review_items(scope_items=scope_items)
            if review is None:
                artifacts["summary"] = "review_failed"
                artifacts["step_errors"].append("review_failed")
                return self._error_result("Failed to review personal_info items", artifacts)

            decisions = self._validate_review_plan(review, items_by_id)
            if decisions is None:
                artifacts["summary"] = "invalid_review_plan"
                artifacts["step_errors"].append("invalid_review_plan")
                return self._error_result("Personal-info review plan was invalid", artifacts)

            artifacts["decisions"] = [
                {"item_id": decision.item_id, "action": decision.action, "why": decision.why} for decision in decisions
            ]
            active_items = [items_by_id[decision.item_id] for decision in decisions if decision.action == "keep_active"]
            artifacts["summary_source_item_ids"] = [item.id for item in active_items]
            artifacts["summary_excluded_item_ids"] = []

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
                artifacts["kept_active_item_ids"] = [item.id for item in active_items]
                artifacts["outdated_item_ids"] = [
                    decision.item_id for decision in decisions if decision.action == "mark_outdated"
                ]
                artifacts["deleted_item_ids"] = [
                    decision.item_id for decision in decisions if decision.action == "delete"
                ]
                artifacts["persisted_summary"] = summary_text
                artifacts["summary"] = (
                    f"dry_run kept_active={len(artifacts['kept_active_item_ids'])} "
                    f"outdated={len(artifacts['outdated_item_ids'])} deleted={len(artifacts['deleted_item_ids'])}"
                )
                return self._action_result(artifacts["summary"], artifacts)

            report = await self._apply_plan(
                user_id=user_id,
                decisions=decisions,
                items_by_id=items_by_id,
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

    async def _cleanup_and_load_scope_items(self, *, user_id: int, dry_run: bool) -> tuple[int, list[Any]]:
        """Delete stale outdated rows first, then load the remaining full personal-info scope."""
        async with provide_memory_item_service() as service:
            stale_outdated_deleted_count = await service.cleanup_stale_personal_info_outdated(
                user_id=user_id,
                older_than_days=self.OUTDATED_RETENTION_DAYS,
                dry_run=dry_run,
            )
            scope_items = await service.list_memory_items(
                user_id=user_id,
                category=MemoryCategory.PERSONAL_INFO,
                limit=None,
            )
        return stale_outdated_deleted_count, scope_items

    async def _review_items(self, *, scope_items: list[Any]) -> PersonalInfoReviewPlan | None:
        current_datetime = self._current_datetime_iso()
        payload = {
            "current_datetime": current_datetime,
            "items": [self._serialize_scope_item(item) for item in scope_items],
        }
        return await self._invoke_structured_model(
            PersonalInfoReviewPlan,
            system_prompt=(
                f"{PERSONAL_INFO_REVIEW_PROMPT}\n\nCurrent datetime: {current_datetime}\n"
                "Use this timestamp when deciding whether a fact is temporary, expired, current, or durable."
            ),
            payload=payload,
            step_name="personal_info_review",
        )

    async def _synthesize_summary(self, *, active_items: list[Any]) -> PersonalInfoSummaryPlan | None:
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
        with_structured_output = getattr(self.model, "with_structured_output", None)
        if not callable(with_structured_output):
            logger.warning("[agents:memorymaintainer] Model does not support structured output for %s", step_name)
            return None

        structured_model = with_structured_output(schema)
        try:
            return await structured_model.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ]
            )
        except OutputParserException as exc:
            logger.warning("[agents:memorymaintainer] %s schema validation failed: %s", step_name, exc)
            return None
        except Exception as exc:
            logger.warning("[agents:memorymaintainer] %s failed: %s", step_name, exc, exc_info=True)
            return None

    @staticmethod
    def _validate_review_plan(
        review: PersonalInfoReviewPlan,
        items_by_id: dict[int, Any],
    ) -> list[PersonalInfoDecision] | None:
        seen_ids: set[int] = set()
        validated: list[PersonalInfoDecision] = []

        for decision in review.decisions:
            if decision.item_id not in items_by_id:
                return None
            if decision.item_id in seen_ids:
                return None
            if not decision.why:
                return None
            seen_ids.add(decision.item_id)
            validated.append(decision)

        if seen_ids != set(items_by_id):
            return None
        return validated

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
        decisions: list[PersonalInfoDecision],
        items_by_id: dict[int, Any],
        target_summary: str | None,
    ) -> PersonalInfoExecutionReport:
        kept_active_item_ids: list[int] = []
        outdated_item_ids: list[int] = []
        deleted_item_ids: list[int] = []

        async with provide_memory_item_service() as service:
            for decision in decisions:
                item = items_by_id.get(decision.item_id)
                if item is None:
                    raise MemoryItemNotFoundError(f"Memory item with id {decision.item_id} not found")
                if item.user_id != user_id:
                    raise PermissionDeniedError("You don't have permission to update this item")

                if decision.action == "keep_active":
                    if item.status != PersonalInfoStatus.ACTIVE.value:
                        await service.update_item_status(decision.item_id, PersonalInfoStatus.ACTIVE.value, user_id)
                    kept_active_item_ids.append(decision.item_id)
                elif decision.action == "mark_outdated":
                    if item.status != PersonalInfoStatus.OUTDATED.value:
                        await service.update_item_status(decision.item_id, PersonalInfoStatus.OUTDATED.value, user_id)
                    outdated_item_ids.append(decision.item_id)
                else:
                    await service.delete_item(decision.item_id, user_id)
                    deleted_item_ids.append(decision.item_id)

        async with provide_user_service() as user_service:
            await user_service.set_personal_info_summary(user_id, target_summary)

        return PersonalInfoExecutionReport(
            kept_active_item_ids=kept_active_item_ids,
            outdated_item_ids=outdated_item_ids,
            deleted_item_ids=deleted_item_ids,
            summary=target_summary,
        )

    @staticmethod
    def _serialize_scope_item(item: Any) -> dict[str, Any]:
        return {
            "id": item.id,
            "key": item.key,
            "content": item.content,
            "status": item.status,
            "updated_at": getattr(item, "updated_at", None).isoformat() if getattr(item, "updated_at", None) else None,
            "status_changed_at": (
                getattr(item, "status_changed_at", None).isoformat()
                if getattr(item, "status_changed_at", None)
                else None
            ),
        }

    @staticmethod
    def _base_artifacts(*, trigger_source: str, dry_run: bool) -> dict[str, Any]:
        return {
            "maintenance_type": "personal_info_memory_maintenance",
            "scope": {"category": "personal_info"},
            "trigger_source": trigger_source,
            "dry_run": dry_run,
            "stale_outdated_deleted_count": 0,
            "reviewed_item_count": 0,
            "decisions": [],
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
