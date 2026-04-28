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
- Set `chat_history_size` to a small even integer (e.g. 2, 4, 6) to keep specialist inputs stable and testable.
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
- Decide this primarily from the current student message, not from earlier student messages in `history`.
- Do not treat an earlier student request to practice/save a word as an active save request for the current turn.
- If the current student explicitly asks to save words from an earlier turn
  (e.g. "save the words you mentioned before"), you may use `history` to identify
  those words and increase `chat_history_size` accordingly.

**Do NOT route when:**
- The student merely reused a word without a save request.
- The word appears only in a correction, grammar explanation, or example sentence.
- An earlier teacher message highlighted vocabulary but the student did not request saving it.
- The intent is analysis, not saving (e.g. "explain the difference between 'så' and 'so'" → explain, not save).
- The student is moving to the next exercise or continuing the lesson without an explicit save request
  (e.g. "next task", "let's continue", "another exercise", "I'm done").
- Words were already saved in earlier turns — do not re-trigger on later turns.

For all normal word_keeper cases, set `chat_history_size` to `2`.

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

## Specialist Routing Rules

### memory_keeper (post)
**Route when:**
- The `teacher_response` explicitly identifies a durable learning signal worth persisting,
  such as a repeated struggle, visible improvement, confirmed mastery, a new recurring issue,
  or a stable fact/strength correction.
- OR the latest student `message` explicitly asks to change memory in this turn
  (for example: remember, forget, remove, correct, change, reprioritize, mark mastered).
- Student-driven memory edits take priority over teacher-driven maintenance if both are present.
- Use only the latest student `message` as the active student intent signal.

**Do NOT route when:**
- The student only hints at a fact or preference without explicitly asking to change memory.
- The request existed only in older `history` rather than the current student `message`.
- The teacher response is routine praise, a normal correction, a drill prompt, or a generic explanation
  without an explicit durable signal.
- The teacher only says a student-written word is misspelled, invalid, nonexistent, or should be replaced
  by another vocabulary item. That is a vocabulary correction, not a durable memory update.
- The plan would rely on inferred intent rather than explicit wording in the current turn.

Examples that SHOULD route:
- Student: "Forget my old goal."
- Student: "Change my goal to speaking practice."
- Teacher: "You are still repeatedly missing article agreement, so this remains a study priority."
- Teacher: "You have now clearly mastered this tense."

Examples that should NOT route:
- Student: "I guess I like speaking more than writing."
- Student: "We talked about this before."
- Teacher: "Good job."
- Teacher: "Write one more sentence with these words."
- Teacher: "There is no such word as 'varen'; use 'våren' for spring."

### word_keeper (post)

**Route when:**
- The actual `teacher_response` explicitly marks vocabulary as worth saving
  (e.g. "the key words here are…", "good words to memorize",
  "let's keep these words in mind").
- The teacher clearly presents a vocabulary-saving moment, not just vocabulary usage inside a drill.
- The teacher explicitly corrects a misspelled, invalid, or nonexistent student-written word and provides
  the corrected Swedish vocabulary item. Route so WordKeeper can prioritize the corrected item, not the error.

Examples that SHOULD route:
- Teacher: "There is no such word as 'varen'; use 'våren' for spring."

**Do NOT route when:**
- The teacher is only asking the student to practice, answer, or write another sentence using words.
- Words are merely bolded, translated, grammatically corrected, or reused in an exercise prompt without
  an explicit memory/save signal or a corrected Swedish vocabulary item.
- The teacher gives an example sentence using words but does not say they are important to memorize or save.
- The response is an ordinary exercise, correction, explanation, or drill rather than a vocabulary-saving moment.

For all normal word_keeper cases, set `chat_history_size` to `2`.
"""
)


class CoordinatorAgent:
    """LLM-based coordinator that produces structured routing plans."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = build_chat_model(settings, "coordinator")

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
