"""Deterministic structured-output pipeline for teacher-emitted learning-progress memory."""

import json
import logging
from dataclasses import dataclass
from typing import Literal, Self

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from runestone.agents.llm import build_chat_model
from runestone.agents.schemas import LearningMemorySignal
from runestone.agents.service_providers import provide_memory_item_service
from runestone.agents.specialists.base import BaseSpecialist, SpecialistAction, SpecialistContext, SpecialistResult
from runestone.api.memory_item_schemas import MemoryCategory, MemorySortBy, SortDirection
from runestone.config import Settings

logger = logging.getLogger(__name__)
LEARNING_STATUSES = ("struggling", "improving", "mastered")

LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT = """
<role>
You are LearningMemoryKeeper, an internal agent that maintains `area_to_improve`
memory about a student's learning progress.
You do not interact with the student. You observe a single turn and decide whether
learning memory should be updated.
</role>

<context_analysis>
You receive:
- `student_message`: the student's message in the current turn
- `teacher_response`: the teacher's response in the current turn, as secondary context only
- `learning_memory_signals`: structured teacher signals for this turn
- `target_memory_ids`: validated target ids derived from structured `memory_id` values
- `existing_targets`: the current allowed `area_to_improve` targets for this turn

Mutations may reference only exact `target_id` values from `existing_targets`.
</context_analysis>

<fast_path>
FIRST: Read `learning_memory_signals`, then check `target_memory_ids`.
If present, treat those IDs as the direct targets for this turn. Prefer precise mutations
for those IDs and do not invent replacement creates for the same signal.

  - Mastery, improvement, regression, or status-change signal
    -> set `status` only.
  - Explicit content correction (the wording of the memory item should change)
    -> set `content` only.
  - Both a status change AND a content correction are clearly present
    -> set both `status` and `content` in the same mutation.
  - Explicit reprioritization
    -> set `priority` only.
  - Explicit request to remove the stored topic, or confirmation that the stored topic is wrong
    -> set `delete=true`.

This is the most common case. Do not mutate IDs outside `target_memory_ids` when they are present.
</fast_path>

<decision_tree>
If `target_memory_ids` is empty, classify into exactly ONE case based on
`learning_memory_signals` first, then explicit `student_message` edit requests,
and `teacher_response` only as support context:

Case A: Student explicitly asks to edit a tracked learning topic.
  Examples:
    - "forget this old grammar issue"
    - "mark this as mastered"
    - "remove that problem from my list"
    - "change that note, it is about articles not prepositions"
  -> use `existing_targets` to find the single clearly referenced item, then return a mutation.
  -> prefer `delete=true` for explicit remove/forget requests.
  -> use `status="mastered"` for explicit mastery requests.
  -> use `content` only for explicit wording corrections.
  -> use `priority` only for explicit reprioritization.
  -> if no single target is clearly identified, return `decision="no_action"`.
  -> set `trigger_source="student"`.

Case B: Teacher explicitly identifies a durable learning issue without an ID tag.
  The teacher signal must indicate the issue is structural, repeated, or worth tracking.
  A routine one-off correction, a typo, a spelling slip, or a vocabulary gap alone is NOT enough.
  Structured examples:
    `{"signal_type":"new_issue","summary":"Recurring issue: the student struggles with articles"}`
    `{"signal_type":"new_issue","summary":"Recurring issue: word order in questions"}`
  -> return one create plan.
  Provide thorough details:
  - `key`: concise English descriptor of the grammar or language concept
  - `content`: clear explanation of what the student struggles with,
    including examples from the conversation when available
  - `status`: `struggling` by default for new issues
  - `priority`: set based on severity (`0` critical, `9` minor)

Case C: Teacher signals improvement, mastery, regression, or content correction, but NO ID tag.
  Structured example: `{"signal_type":"mastered","summary":"The student has now mastered verb conjugation."}`
  -> use `existing_targets` to find the matching item, then return a mutation.
  -> if no matching item is found and the signal is a learning need, fall back to a create plan.
  -> if the signal marks mastery of an unknown topic, return `decision="no_action"`.

None of the above
  -> return `decision="no_action"`.
</decision_tree>

<terminal_no_ops>
- If `target_memory_ids` are present, do not invent replacement creates for those targeted topics.
- Do not mutate an existing target unless the current turn clearly refers to that topic.
- If multiple existing targets are plausible but the turn does not clearly identify one, return `decision="no_action"`.
</terminal_no_ops>

<conservative_bias>
- Default to `decision="no_action"`. Only act on explicit, durable signals.
- One write intent per item per turn.
- Do not use both `status` and `priority` on the same item unless the signal explicitly requires both.
- Use `priority` only for the single item directly implicated by the
  current turn's signal. Never rebalance multiple items.
- Use `area_to_improve` with status `mastered` for topics the student
  has resolved or learned. Do not create a separate strength item.
- Represent recurring issues as creates so Python can upsert by key.
</conservative_bias>

<extraction_contract>
- Return `decision="update_memory"` only when `creates` or `mutations` is non-empty.
- `trigger_source` must be `teacher`, `student`, or `none`.
- `creates` are for durable new or recurring issues.
- `mutations` may use only `target_id` values from `existing_targets`.
- Default to `decision="no_action"`, `trigger_source="none"`, and empty operation lists.
</extraction_contract>
"""


class LearningMemoryCreate(BaseModel):
    """One proposed area-to-improve upsert."""

    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)
    status: Literal["struggling", "improving", "mastered"] = "struggling"
    priority: int | None = Field(None, ge=0, le=9)

    @field_validator("key", "content", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LearningMemoryMutation(BaseModel):
    """One proposed mutation of an allowlisted learning target."""

    model_config = ConfigDict(extra="forbid")
    target_id: StrictInt = Field(gt=0)
    content: str | None = Field(None, min_length=1)
    status: Literal["struggling", "improving", "mastered"] | None = None
    priority: int | None = Field(None, ge=0, le=9)
    delete: bool = False

    @field_validator("content", mode="before")
    @classmethod
    def trim_content(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_mutation(self) -> Self:
        changes = (self.content is not None, self.status is not None, self.priority is not None)
        if self.delete and any(changes):
            raise ValueError("delete_not_exclusive")
        if not self.delete and not any(changes):
            raise ValueError("empty_mutation")
        return self


class LearningMemoryKeeperExtraction(BaseModel):
    """Bounded extraction plan for one learning-memory run."""

    model_config = ConfigDict(extra="forbid")
    decision: Literal["no_action", "update_memory"]
    trigger_source: Literal["teacher", "student", "none"] = "none"
    creates: list[LearningMemoryCreate] = Field(default_factory=list)
    mutations: list[LearningMemoryMutation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        if (self.decision == "update_memory") != bool(self.creates or self.mutations):
            raise ValueError("decision_list_mismatch")

        creates: dict[str, LearningMemoryCreate] = {}
        for operation in self.creates:
            previous = creates.get(operation.key)
            if previous is not None and previous != operation:
                raise ValueError("conflicting_operations")
            creates.setdefault(operation.key, operation)
        mutations: dict[int, LearningMemoryMutation] = {}
        for operation in self.mutations:
            previous = mutations.get(operation.target_id)
            if previous is not None and previous != operation:
                raise ValueError("conflicting_operations")
            mutations.setdefault(operation.target_id, operation)
        if len(creates) + len(mutations) > 3:
            raise ValueError("over_limit")
        self.creates = list(creates.values())
        self.mutations = list(mutations.values())
        return self


@dataclass(frozen=True)
class AllowedLearningTarget:
    """Sanitized snapshot exposed to the extraction model."""

    id: int
    key: str
    content: str
    status: str
    priority: int | None

    def as_payload(self) -> dict[str, object]:
        return {
            "id": self.id,
            "key": self.key,
            "content": self.content,
            "status": self.status,
            "priority": self.priority,
        }


def parse_learning_memory_ids(signals: list[LearningMemorySignal]) -> list[int]:
    """Return unique validated target ids from structured learning-memory signals."""
    tagged_ids: list[int] = []
    for signal in signals:
        if signal.memory_id is None:
            continue
        tagged_ids.append(signal.memory_id)
    return list(dict.fromkeys(tagged_ids))


class LearningMemoryKeeperSpecialist(BaseSpecialist):
    """Extract and apply bounded learning-memory operations deterministically."""

    def __init__(self, settings: Settings):
        super().__init__(name="learning_memory_keeper")
        self.settings = settings
        self.model = build_chat_model(settings, "learning_memory_keeper")
        logger.info(
            "[agents:learning_memory_keeper] initialized provider=%s model=%s",
            settings.memory_keeper_provider,
            settings.memory_keeper_model,
        )

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        tagged_ids = parse_learning_memory_ids(context.learning_memory_signals)
        try:
            async with provide_memory_item_service() as service:
                targets = await self._load_targets(service, context.user.id, tagged_ids)
                if tagged_ids and not targets:
                    logger.info("[agents:learning_memory_keeper] reason=stale_target")
                    return self._result("no_action", "none", "stale_target")

                payload = {
                    "student_message": context.message,
                    "teacher_response": context.teacher_response,
                    "learning_memory_signals": [
                        signal.model_dump(mode="json") for signal in context.learning_memory_signals
                    ],
                    "target_memory_ids": tagged_ids,
                    "existing_targets": [target.as_payload() for target in targets.values()],
                }
                extraction = await self._extract(payload)
                if isinstance(extraction, SpecialistResult):
                    return extraction
                if not extraction.creates and not extraction.mutations:
                    return self._result("no_action", extraction.trigger_source, "empty_plan")
                disallowed = [m.target_id for m in extraction.mutations if m.target_id not in targets]
                if disallowed:
                    logger.warning("[agents:learning_memory_keeper] reason=target_not_allowed")
                    return self._result("error", extraction.trigger_source, "target_not_allowed")
                return await self._execute(
                    service, context.user.id, extraction, targets, context.learning_memory_signals
                )
        except Exception as exc:
            logger.warning(
                "[agents:learning_memory_keeper] reason=service_failed exception=%s",
                type(exc).__name__,
                exc_info=True,
            )
            return self._result("error", "none", "service_failed", type(exc).__name__)

    async def _load_targets(self, service, user_id: int, tagged_ids: list[int]) -> dict[int, AllowedLearningTarget]:
        if tagged_ids:
            rows = [await service.get_item_by_id(item_id) for item_id in tagged_ids]
        else:
            rows = await service.list_memory_items(
                user_id,
                category=MemoryCategory.AREA_TO_IMPROVE,
                statuses=list(LEARNING_STATUSES),
                sort_by=MemorySortBy.UPDATED_AT,
                sort_direction=SortDirection.DESC,
                limit=100,
            )
        targets: dict[int, AllowedLearningTarget] = {}
        for row in rows:
            if row is None or row.user_id != user_id or row.category != MemoryCategory.AREA_TO_IMPROVE.value:
                if row is not None:
                    logger.warning("[agents:learning_memory_keeper] reason=invalid_target")
                continue
            targets[row.id] = AllowedLearningTarget(
                id=row.id,
                key=row.key,
                content=row.content,
                status=row.status,
                priority=row.priority,
            )
        return targets

    async def _extract(self, payload: dict[str, object]) -> LearningMemoryKeeperExtraction | SpecialistResult:
        model = self.model.with_structured_output(LearningMemoryKeeperExtraction)
        try:
            return await model.ainvoke(
                [
                    SystemMessage(content=LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ]
            )
        except OutputParserException as exc:
            logger.warning(
                "[agents:learning_memory_keeper] reason=schema_validation_failed exception=%s",
                type(exc).__name__,
            )
            return self._result("error", "none", "schema_validation_failed", type(exc).__name__)
        except Exception as exc:
            logger.warning(
                "[agents:learning_memory_keeper] reason=model_failed exception=%s",
                type(exc).__name__,
                exc_info=True,
            )
            return self._result("error", "none", "model_failed", type(exc).__name__)

    async def _execute(
        self,
        service,
        user_id: int,
        extraction: LearningMemoryKeeperExtraction,
        targets: dict[int, AllowedLearningTarget],
        learning_memory_signals: list[LearningMemorySignal],
    ) -> SpecialistResult:
        actions: list[SpecialistAction] = []
        counts = {"upserted": 0, "updated": 0, "deleted": 0, "failed": 0}
        changed_item_ids: list[int] = []
        upserted_item_ids: list[int] = []
        updated_item_ids: list[int] = []
        deleted_item_ids: list[int] = []
        operations: list[tuple[str, object]] = [
            *(("create", operation) for operation in extraction.creates),
            *(("mutation", operation) for operation in extraction.mutations),
        ]
        for operation_type, operation in operations:
            try:
                if operation_type == "create":
                    create = operation
                    item = await service.upsert_memory_item(
                        user_id,
                        MemoryCategory.AREA_TO_IMPROVE,
                        create.key,
                        create.content,
                        create.status,
                        create.priority,
                    )
                    counts["upserted"] += 1
                    changed_item_ids.append(item.id)
                    upserted_item_ids.append(item.id)
                    actions.append(self._action("upsert_memory_item", "success", f"Upserted {item.key}"))
                    continue

                mutation = operation
                if mutation.delete:
                    await service.delete_item(mutation.target_id, user_id)
                    counts["deleted"] += 1
                    changed_item_ids.append(mutation.target_id)
                    deleted_item_ids.append(mutation.target_id)
                    actions.append(self._action("delete_item", "success", f"Deleted item {mutation.target_id}"))
                    continue
                for tool, value, call in (
                    ("update_item_status", mutation.status, service.update_item_status),
                    ("update_item_content", mutation.content, service.update_item_content_in_category),
                    ("update_item_priority", mutation.priority, service.update_item_priority),
                ):
                    if value is None:
                        continue
                    if tool == "update_item_content":
                        await call(mutation.target_id, MemoryCategory.AREA_TO_IMPROVE, value, user_id)
                    else:
                        await call(mutation.target_id, value, user_id)
                    counts["updated"] += 1
                    if mutation.target_id not in updated_item_ids:
                        updated_item_ids.append(mutation.target_id)
                    if mutation.target_id not in changed_item_ids:
                        changed_item_ids.append(mutation.target_id)
                    actions.append(self._action(tool, "success", f"Updated item {mutation.target_id}"))
            except Exception as exc:
                counts["failed"] += 1
                logger.warning(
                    "[agents:learning_memory_keeper] reason=service_failed exception=%s",
                    type(exc).__name__,
                    exc_info=True,
                )
                actions.append(self._action("memory_item_service", "error", "Memory operation failed"))
                break

        status = "error" if counts["failed"] else ("action_taken" if actions else "no_action")
        return SpecialistResult(
            status=status,
            actions=actions,
            info_for_teacher=(
                f"Applied {len([a for a in actions if a.status == 'success'])} learning memory change(s)."
                if actions
                else ""
            ),
            artifacts={
                "trigger_source": extraction.trigger_source,
                "reason": "service_failed" if counts["failed"] else ("applied" if actions else "stale_target"),
                "signal_count": len(learning_memory_signals),
                "signal_types": [signal.signal_type for signal in learning_memory_signals],
                "target_memory_ids": parse_learning_memory_ids(learning_memory_signals),
                "changed_item_ids": changed_item_ids,
                "upserted_item_ids": upserted_item_ids,
                "updated_item_ids": updated_item_ids,
                "deleted_item_ids": deleted_item_ids,
                **counts,
            },
        )

    @staticmethod
    def _action(tool: str, status: Literal["success", "error"], summary: str) -> SpecialistAction:
        return SpecialistAction(tool=tool, status=status, summary=summary)

    @staticmethod
    def _result(
        status: Literal["no_action", "action_taken", "error"],
        trigger_source: str,
        reason: str,
        exception_type: str | None = None,
    ) -> SpecialistResult:
        artifacts: dict[str, object] = {"trigger_source": trigger_source, "reason": reason}
        if exception_type:
            artifacts["exception_type"] = exception_type
        return SpecialistResult(status=status, actions=[], info_for_teacher="", artifacts=artifacts)
