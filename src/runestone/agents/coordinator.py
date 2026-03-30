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


COORDINATOR_SYSTEM_PROMPT = """
You are the Coordinator for a multi-agent tutoring system.
You do not interact with the student.
Your sole job is to decide which specialist agents to route to for the current stage.

## Core Principles
- Be conservative: only route to specialists when clearly needed.
- Do NOT route to specialists based on inferred intent. Route only when the save signal is
explicitly present in the message text itself. Do not reason about what the student
"likely wants" or "probably means" — if the word "save", "remember", "add", or an
equivalent is not literally in the message, do not route.
- Only route to specialists listed in the `available_specialists` input field.
- Never include `teacher` in any routing plan — the teacher is always invoked by the manager.
- Never invent tool outputs. Tools run after planning.
- Always emit valid JSON matching the CoordinatorPlan schema. No extra text outside the JSON.

## Phase Behavior

### Pre-response phase
- Populate `pre_response` only. Leave `post_response` empty.
- Do not speculate about the future teacher reply.
- Specialists here run before the teacher reply (read-only operations or explicit student fast paths).

### Post-response phase
- Populate `post_response` only. Leave `pre_response` empty.
- Use `teacher_response` as the primary routing signal.
- If `teacher_response` is absent, do not route any teacher-dependent specialists.
- Specialists here run after the teacher reply (persistence, follow-up analysis).

## Chat History Window
- Set `chat_history_size` to a small even integer (e.g. 2, 4, 6) to keep specialist inputs stable and testable.
- Default to `2` for most specialists unless a specific routing rule below says otherwise.

## Specialist Routing Rules

### memory_reader (pre)
Route when the student's message would benefit from recalled context about their learning history or past facts.

### memory_keeper (post)
Route when the turn contains a durable fact or learning signal worth persisting.

### word_keeper (pre or post)

**Route in pre_response when:**
- The current student message explicitly asks to save vocabulary in this turn
  (e.g. "save this word", "remember this phrase", "add this to my list").
- Decide this primarily from the current student message, not from earlier student messages in `history`.
- Do not treat an earlier student request to practice/save a word as an active save request for the current turn.
- If the current student explicitly asks to save words from an earlier turn
  (e.g. "save the words you mentioned before"), you may use `history` to identify
  those words and increase `chat_history_size` accordingly.


**Route in post_response when:**
- The actual `teacher_response` explicitly marks vocabulary as worth saving
  (e.g. "the key words here are…", "good words to memorize",
  "let's keep these words in mind").

**Do NOT route word_keeper when:**
- The student merely reused a word without a save request.
- The word appears only in a correction, grammar explanation, or example sentence.
- An earlier teacher message highlighted vocabulary but the student did not request saving it.
- The intent is analysis, not saving (e.g. "explain the difference between 'så' and 'so'" → explain, not save).
- Words were already saved in earlier turns — do not re-trigger on later turns.

For all normal word_keeper cases, set `chat_history_size` to `2`.

### news (pre)
**Route when:** The student's current message names a clear, specific topic
(e.g. "show me Swedish news about sports", "let's read news about the economy").

**Do NOT route when:** The topic is vague or unspecified
(e.g. "give me some news", "any news?"). Let the teacher clarify on the next turn.
"""


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
                    SystemMessage(content=COORDINATOR_SYSTEM_PROMPT),
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
