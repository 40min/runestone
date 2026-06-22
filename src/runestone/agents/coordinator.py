"""
Coordinator agent responsible for routing and orchestration planning.
"""

import json
import logging
from typing import Literal

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage

from runestone.agents.llm import build_chat_model
from runestone.agents.schemas import ChatMessage, CoordinatorPlan
from runestone.config import Settings
from runestone.core.observability import timed_operation

logger = logging.getLogger(__name__)


COORDINATOR_BASE_PROMPT = """
You are the Coordinator for a multi-agent tutoring system.
You do not interact with the student.
Your sole job is to decide which specialist agents to route to for the current stage.

## Core Principles
- Be conservative: only route to specialists when clearly needed.
- Do NOT route to specialists based on inferred intent.
- Route only when the relevant trigger signal is explicitly present in the current turn text.
- Do not reason about what the student or teacher "likely wants" or "probably means".
- For memory or persistence specialists, require literal intent such as save, remember, add,
  forget, remove, correct, change, reprioritize, mark mastered, or an equally explicit equivalent.
- Only route to specialists listed in the `available_specialists` input field.
- Never include `teacher` in any routing plan — the teacher is always invoked by the manager.
- Never invent tool outputs. Tools run after planning.
- Always emit valid JSON matching the CoordinatorPlan schema. No extra text outside the JSON.

## Chat History Window
- Set `chat_history_size` to a small non-negative integer
  (e.g. 0, 2, 4, 6) to keep specialist inputs stable and testable.
- Default to `2` for most specialists unless a specific routing rule below says otherwise.
"""


COORDINATOR_PRE_RESPONSE_PROMPT = (
    COORDINATOR_BASE_PROMPT
    + """

## Current Phase
- This is the pre-response phase.
- Populate `pre_response` only. Leave `post_response` empty.
- Do not speculate about the future teacher reply.
- Specialists here run before the teacher reply (read-only operations or explicit student fast paths).

## Specialist Routing Rules

### word_keeper (pre)

**Route when:**
- The current student message explicitly asks to save vocabulary in this turn
  (e.g. "save this word", "remember this phrase", "add this to my list").
- This includes cases where the student explicitly names the words to save in the current message
  (e.g. "save `begripa` and `noggrann`") or clearly points to words present in that same message
  (e.g. "save these words for me: beskriva, bekräfta").
- This also includes deictic save requests that clearly refer to words from the immediately preceding
  teacher message (e.g. "save that word", "remember those words").
- Decide this from the current student message only.
- Do not treat an earlier student request to practice/save a word as an active save request for the current turn.

**Do NOT route when:**
- The student merely reused a word without a save request.
- The word appears only in a correction, grammar explanation, or example sentence.
- An earlier teacher message highlighted vocabulary but the student did not request saving it.
- The intent is analysis, not saving (e.g. "explain the difference between 'så' and 'so'" → explain, not save).
- The student is moving to the next exercise or continuing the lesson without an explicit save request
  (e.g. "next task", "let's continue", "another exercise", "I'm done").
- Words were already saved in earlier turns — do not re-trigger on later turns.

Set `chat_history_size` to `0` for `word_keeper`.

### news_agent (pre)
**Route when:** The student's current message asks about a specific real-time or current-events topic that requires
live data — such as news about a subject, place, or event, current weather, or any other factual query that cannot
be answered from static knowledge.
- **Hard trigger:** if the current student message explicitly asks for `news`/`nyheter` and names a concrete topic,
  place, or event in the same message, route `news_agent`.
  This includes invitation phrasing like "Ska vi lasa nyheter om Sverige?" and follow-ups like
  "Ja, teknik ar bra" when the immediate context is already a live news fetch request.

**Do NOT route when:**
- The topic is vague or unspecified (e.g. "give me some news", "any news?"). Let the teacher clarify on the next turn.
- The student is asking a grammar or vocabulary question with no real-time component.

For all normal news_agent cases, set `chat_history_size` to `2`.
"""
)


COORDINATOR_POST_RESPONSE_PROMPT = (
    COORDINATOR_BASE_PROMPT
    + """

## Current Phase
- This is the post-response phase.
- Populate `post_response` only. Leave `pre_response` empty.
- Use `teacher_response` as the primary routing signal.
- If `teacher_response` is absent, do not route any teacher-dependent specialists.
- Specialists here run after the teacher reply (persistence, follow-up analysis).
- Post-phase memory routing is history-free: decide from the current student `message`
  and current `teacher_response` only.

## Specialist Routing Rules

### learning_memory_keeper (post)
**Route when:**
- The `teacher_response` explicitly identifies a durable **learning progress** signal:
  repeated struggle, visible improvement, confirmed mastery, or a new recurring learning issue.
- OR the student explicitly asks to edit a **learning topic** (area_to_improve):
  reprioritize, mark mastered, correct a learning area description.

**Do NOT route when:**
- The signal is about personal facts (native language, hometown, goals) — route
  `personal_memory_keeper` instead.
- The teacher gives routine praise, normal corrections, drill prompts, or generic explanations.
- The teacher merely explains grammar rules using instructional verbs like "kom ihåg" or "tänk på".
- The teacher only corrects a misspelled/invalid word (vocabulary event, not learning memory).

Set `chat_history_size` to `0` for `learning_memory_keeper`.

### personal_memory_keeper (post)
**Route when:**
- The student's `message` contains a clear, durable personal fact (for example: native language,
  hometown, occupation, long-term goal, stable preference, background).
- OR the student explicitly corrects, replaces, or asks to forget a personal fact.
- OR the `teacher_response` explicitly signals a personal fact to persist.

**Do NOT route when:**
- The student expresses transient emotions, vague wishes, or one-off plans.
- The student is just practicing sentences or doing drills.
- The student is writing fictional examples or translating practice sentences (e.g. in response to a teacher exercise).
- The signal is about learning progress (area_to_improve) — route `learning_memory_keeper`.

Set `chat_history_size` to `2` for `personal_memory_keeper`.
"""
)


class CoordinatorAgent:
    """LLM-based coordinator that produces structured routing plans."""

    MODEL_TIMEOUT_SECONDS = 3.0

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = build_chat_model(settings, "coordinator", timeout_seconds=self.MODEL_TIMEOUT_SECONDS)

        logger.info(
            "[agents:coordinator] Initialized CoordinatorAgent with provider=%s, model=%s",
            settings.coordinator_provider,
            settings.coordinator_model,
        )

    @staticmethod
    def _system_prompt(current_stage: Literal["pre_response", "post_response"]) -> str:
        """Select the prompt for the current coordinator phase."""
        if current_stage == "pre_response":
            return COORDINATOR_PRE_RESPONSE_PROMPT
        return COORDINATOR_POST_RESPONSE_PROMPT

    @timed_operation(logger, "[agents:coordinator] Plan completed")
    async def plan(
        self,
        message: str,
        history: list[ChatMessage],
        *,
        current_stage: Literal["pre_response", "post_response"],
        available_specialists: list[str],
        teacher_response: str | None = None,
    ) -> CoordinatorPlan:
        """Return a routing plan for the given turn."""
        model = self.model.with_structured_output(CoordinatorPlan)
        payload = {
            "current_stage": current_stage,
            "message": message,
            "history": [msg.model_dump(mode="json") for msg in history],
            "teacher_response": teacher_response,
            "available_specialists": available_specialists,
        }

        try:
            result = await model.ainvoke(
                [
                    SystemMessage(content=self._system_prompt(current_stage)),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ]
            )
            return self._normalize_plan(result, current_stage)
        except OutputParserException as e:
            logger.error("[agents:coordinator] Schema validation failed: %s", str(e))
            # Fallback to teacher only if plan fails
            return CoordinatorPlan(
                pre_response=[],
                post_response=[],
                audit={"error": "output_parsing", "details": str(e)},
            )
        except Exception as e:
            logger.error("[agents:coordinator] Coordinator execution failed: %s", str(e))
            # Return a safe fallback plan
            return CoordinatorPlan(
                pre_response=[],
                post_response=[],
                audit={"error": "generic_error", "details": str(e)},
            )

    async def plan_pre_turn(
        self,
        message: str,
        history: list[ChatMessage],
        *,
        available_specialists: list[str],
    ) -> CoordinatorPlan:
        return await self.plan(
            message=message,
            history=history,
            current_stage="pre_response",
            available_specialists=available_specialists,
        )

    async def plan_post_turn(
        self,
        message: str,
        history: list[ChatMessage],
        *,
        teacher_response: str,
        available_specialists: list[str],
    ) -> CoordinatorPlan:
        return await self.plan(
            message=message,
            history=history,
            current_stage="post_response",
            teacher_response=teacher_response,
            available_specialists=available_specialists,
        )

    @staticmethod
    def _normalize_plan(
        plan: CoordinatorPlan, current_stage: Literal["pre_response", "post_response"]
    ) -> CoordinatorPlan:
        if current_stage == "pre_response":
            return CoordinatorPlan(
                pre_response=plan.pre_response,
                post_response=[],
                audit=plan.audit,
            )
        return CoordinatorPlan(
            pre_response=[],
            post_response=plan.post_response,
            audit=plan.audit,
        )
