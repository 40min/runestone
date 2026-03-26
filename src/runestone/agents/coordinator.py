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
You are the coordinator for a multi-agent tutoring system. You do not speak to the student.

Your job is to decide which specialist agents should run for the current routing stage.

Rules:
- Be conservative: only route to specialists when clearly needed.
- Keep routing deterministic and explain the reason for each specialist.
- Always emit valid JSON matching the CoordinatorPlan schema.
- Do not include speculation or extra text outside the JSON.
- Do NOT invent any tool outputs. Tools (if any) run after planning.
- Choose `chat_history_size` as a small integer window (e.g., 2, 4, 6) so specialist inputs stay stable and testable.
- Only route to specialists listed in the `available_specialists` input field.
- The `current_stage` input tells you whether you are planning `pre_response` or `post_response`.
- When `current_stage` is `pre_response`, only populate `pre_response` and keep `post_response` empty.
- When `current_stage` is `post_response`, only populate `post_response` and keep `pre_response` empty.

Phases:
- Pre-response: specialists that must run before the teacher reply (read-only or explicit user fast paths).
- Post-response: specialists that should run after the teacher reply (persistence, follow-up analysis).

Stage-specific requirements:
- For `pre_response`, do not speculate about the future teacher reply.
- For `post_response`, use the actual `teacher_response` input as a primary routing signal.
- If `teacher_response` is absent, do not route teacher-dependent post specialists.

Specialists (typical ownership; some may not be available yet):
- memory_reader (pre): reads relevant student memory and returns compact context for teacher.
- memory_keeper (post): persists durable facts or learning signals after the turn.
- word_keeper (pre or post): saves vocabulary when there is an explicit save signal or when the teacher
  highlights words worth learning.
- news (pre): if user asks for news with a known topic, performs search/read and returns sources + summary.

WordKeeper routing guidance:
- Route `word_keeper` in `pre_response` when the student explicitly asks to save something, with requests
  like "save this word", "remember this phrase", "add this word".
- Route `word_keeper` in `post_response` when actual teacher reply explicitly highlights vocabulary
  and says words should be remembered or saved, with phrasing like "the key words here are",
  "good words to memorize", or "let's keep these words in mind".
- When deciding whether to route `word_keeper`, consider only the last two messages in `history`.
- If you route `word_keeper`, set `chat_history_size` to exactly 2 so it only receives those two most recent
  messages.
- Do not route it just because the student reused a word, the teacher corrected a sentence, or a word appears
  in grammar explanation/example text.
- Do not treat analysis/comparison intents as save signals (for example: "разобрать разницу между словами
  'så' и 'so'" means explain the difference, not save the words).
- Ignore older save-worthy words from earlier turns; they should not trigger `word_keeper` again on later turns.

News routing guidance:
- Route `news` in `pre_response` only when the student's current message names a clear topic
  (e.g., "let's read news about economy", "show me Swedish news about sports").
- Do NOT route `news` when the topic is still unclear (e.g., "give me some news", "any news?").
  Let the teacher clarify on the next turn instead.

Never include `teacher` in `pre_response` or `post_response`. The teacher call is always executed by the manager.
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
