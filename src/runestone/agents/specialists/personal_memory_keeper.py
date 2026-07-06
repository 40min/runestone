"""Deterministic structured-output pipeline for append-only personal memory."""

import json
import logging
from typing import Literal, Self

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from runestone.agents.llm import build_chat_model
from runestone.agents.service_providers import provide_memory_item_service
from runestone.agents.specialists.base import BaseSpecialist, SpecialistAction, SpecialistContext, SpecialistResult
from runestone.config import Settings

logger = logging.getLogger(__name__)

PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT = """
<role>
You are PersonalMemoryKeeper. You persist durable personal facts about a student.
You do not interact with the student. You observe a single turn and decide whether
a personal fact should be stored.
Duplicates are acceptable. A separate maintenance process handles deduplication and
reconciliation after accepted facts are appended.
</role>

<context_analysis>
You receive:
- `student_message`: the student's message in the current turn
- `teacher_response`: the teacher's response in the current turn
- `previous_teacher_message`: the teacher's message from the previous turn (what the student was replying to)

CRITICAL RULE:
Before saving any fact, compare `student_message` with `previous_teacher_message`.
If the previous teacher message was a drill request, a grammar exercise, a translation test,
or asked the student to write an example phrase (for example: "Write a sentence starting
with 'Jag är...'", or "Translate 'I like history'"), then do NOT save the student's reply
as a fact. The student's reply in these cases is a fictional or practice sentence, not a real
personal fact.
Only save facts when the student is genuinely sharing real, durable personal details about
themselves outside of practice exercises.
</context_analysis>

<decision_tree>
1. Student states a clear, durable personal fact (and it is NOT a practice or drill example sentence)
   -> return `decision="append_fact"` with one or more facts.
2. Teacher explicitly signals a personal fact to persist
   -> return `decision="append_fact"` with one or more facts.
3. Student corrects a previously known fact (for example: "I moved to Stockholm")
   -> include the replacement fact with `status="correction"`. The old fact will be reconciled automatically.
4. Student asks to forget a personal fact (for example: "forget my goal")
   -> include a removal request with `status="outdated"` so the maintainer can reconcile it later.
5. None of the above
   -> return `decision="no_action"` with `facts=[]`.
</decision_tree>

<fact_fields>
Each fact must contain:
- `key`: short English descriptor (for example: `native_language`,
  `lives_in`, `occupation`, `learning_goal`, `background`)
- `content`: the fact in clear, concise English
- `status`: `active` (default), `correction` (for replacements), or `outdated` (for deletion requests)
</fact_fields>

<triggers>
Act on (durable personal facts):
- "My native language is Finnish" -> `native_language` / "Native language is Finnish"
- "I work as a nurse" -> `occupation` / "Works as a nurse"
- "My goal is conversational fluency" -> `learning_goal` / "Goal: conversational fluency"
- "I moved to Stockholm" -> `lives_in` / "Lives in Stockholm"
- "Actually, I live in Uppsala now" -> `lives_in` / "Lives in Uppsala" with `status="correction"`
- "Forget my old goal" -> `learning_goal` / "Forget the learning goal" with `status="outdated"`
- Teacher: "Remember that the student is a beginner" -> `level` / "Beginner level"

Do NOT act on (not durable personal facts):
- "I feel tired today" -> transient state
- "Maybe I should study more" -> vague wish
- "I find grammar boring" -> fleeting preference, not factual
- practice sentences, drill answers, translation answers, or general conversation
- learning progress signals (`area_to_improve`) because that belongs to `learning_memory_keeper`
</triggers>

<output_bias>
- Choose `trigger_source="student"` or `trigger_source="teacher"` according to the source.
- If the student is answering a drill, translation, grammar exercise,
  or example-sentence request, set `is_practice_response=true` and
  return no facts.
- Default to `decision="no_action"`, `trigger_source="none"`, and `facts=[]`.
</output_bias>
"""


class PersonalMemoryKeeperFact(BaseModel):
    """One validated personal fact proposed for append."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)
    status: Literal["active", "correction", "outdated"] = "active"

    @field_validator("key", "content", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class PersonalMemoryKeeperExtraction(BaseModel):
    """Bounded extraction plan for one personal-memory run."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["no_action", "append_fact"]
    trigger_source: Literal["teacher", "student", "none"] = "none"
    is_practice_response: bool = False
    facts: list[PersonalMemoryKeeperFact] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        if self.is_practice_response and self.facts:
            raise ValueError("practice_response_with_facts")
        if (self.decision == "append_fact") != bool(self.facts):
            raise ValueError("decision_list_mismatch")
        seen: dict[str, tuple[str, str]] = {}
        unique: list[PersonalMemoryKeeperFact] = []
        for fact in self.facts:
            identity = fact.key
            payload = (fact.content, fact.status)
            previous = seen.get(identity)
            if previous is not None and previous != payload:
                raise ValueError("conflicting_operations")
            if previous is None:
                seen[identity] = payload
                unique.append(fact)
        if len(unique) > 5:
            raise ValueError("over_limit")
        self.facts = unique
        return self


class PersonalMemoryKeeperSpecialist(BaseSpecialist):
    """Extract and append durable personal facts with one bounded model call."""

    def __init__(self, settings: Settings):
        super().__init__(name="personal_memory_keeper")
        self.settings = settings
        self.model = build_chat_model(settings, "personal_memory_keeper")
        logger.info(
            "[agents:personal_memory_keeper] initialized provider=%s model=%s",
            settings.memory_keeper_provider,
            settings.memory_keeper_model,
        )

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        previous_teacher_message = next(
            (message.content for message in reversed(context.history) if message.role == "assistant"),
            None,
        )
        payload = {
            "student_message": context.message,
            "teacher_response": context.teacher_response,
            "previous_teacher_message": previous_teacher_message,
        }
        extraction = await self._extract(payload)
        if isinstance(extraction, SpecialistResult):
            return extraction
        if extraction.is_practice_response:
            logger.info("[agents:personal_memory_keeper] reason=practice_response")
            return self._result("no_action", extraction.trigger_source, "practice_response")
        if not extraction.facts:
            return self._result("no_action", extraction.trigger_source, "empty_plan")

        actions: list[SpecialistAction] = []
        appended: list[str] = []
        failed = 0
        try:
            async with provide_memory_item_service() as service:
                for fact in extraction.facts:
                    try:
                        item = await service.append_personal_info_item(
                            context.user.id,
                            key=fact.key,
                            content=fact.content,
                            status=fact.status,
                        )
                    except Exception as exc:
                        failed += 1
                        logger.warning(
                            "[agents:personal_memory_keeper] reason=service_failed exception=%s",
                            type(exc).__name__,
                            exc_info=True,
                        )
                        actions.append(
                            SpecialistAction(
                                tool="append_personal_info_item",
                                status="error",
                                summary=f"Failed to append personal fact {fact.key}",
                            )
                        )
                        break
                    appended.append(fact.key)
                    actions.append(
                        SpecialistAction(
                            tool="append_personal_info_item",
                            status="success",
                            summary=f"Appended personal fact {item.key}",
                        )
                    )
        except Exception as exc:
            failed += 1
            logger.warning(
                "[agents:personal_memory_keeper] reason=service_failed exception=%s",
                type(exc).__name__,
                exc_info=True,
            )

        status = "error" if failed else "action_taken"
        return SpecialistResult(
            status=status,
            actions=actions,
            info_for_teacher=f"Appended {len(appended)} personal memory item(s)." if appended else "",
            artifacts={
                "trigger_source": extraction.trigger_source,
                "reason": "service_failed" if failed else "appended",
                "appended_count": len(appended),
                "failed_count": failed,
                "keys": appended,
            },
        )

    async def _extract(self, payload: dict[str, object]) -> PersonalMemoryKeeperExtraction | SpecialistResult:
        model = self.model.with_structured_output(PersonalMemoryKeeperExtraction)
        try:
            return await model.ainvoke(
                [
                    SystemMessage(content=PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ]
            )
        except OutputParserException as exc:
            logger.warning(
                "[agents:personal_memory_keeper] reason=schema_validation_failed exception=%s",
                type(exc).__name__,
            )
            return self._result("error", "none", "schema_validation_failed", type(exc).__name__)
        except Exception as exc:
            logger.warning(
                "[agents:personal_memory_keeper] reason=model_failed exception=%s",
                type(exc).__name__,
                exc_info=True,
            )
            return self._result("error", "none", "model_failed", type(exc).__name__)

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
