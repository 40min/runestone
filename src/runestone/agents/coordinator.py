"""
Coordinator agent responsible for routing and orchestration planning.
"""

import json
import logging
import time

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage

from runestone.agents.llm import build_chat_model
from runestone.agents.schemas import ChatMessage, CoordinatorPlan
from runestone.config import Settings

logger = logging.getLogger(__name__)


COORDINATOR_SYSTEM_PROMPT = """
You are the coordinator for a multi-agent tutoring system. You do not speak to the student.

Your job is to decide which specialist agents should run before and after the teacher response.

Rules:
- Be conservative: only route to specialists when clearly needed.
- Keep routing deterministic and explain the reason for each specialist.
- Always emit valid JSON matching the CoordinatorPlan schema.
- Do not include speculation or extra text outside the JSON.
- Do NOT invent any tool outputs. Tools (if any) run after planning.
- Choose `chat_history_size` as a small integer window (e.g., 2, 4, 6) so specialist inputs stay stable and testable.
- Only route to specialists listed in the `available_specialists` input field.

Phases:
- Pre-response: specialists that must run before the teacher reply (read-only or explicit user fast paths).
- Post-response: specialists that should run after the teacher reply (persistence, follow-up analysis).

Specialists (typical ownership; some may not be available yet):
- memory_reader (pre): reads relevant student memory and returns compact context for teacher.
- memory_keeper (post): persists durable facts or learning signals after the turn.
- word_keeper (pre/post): saves vocabulary, typically post; pre only for explicit “save this word” commands.
- news (pre): if user asks for news, performs search/read and returns sources + summary.
- grammar (pre/post): finds relevant cheatsheet(s) and returns a distilled explanation; may be post if teacher decides
  to add a reference after composing the response.

Never include `teacher` in `pre_response` or `post_response`. The teacher call is always executed by the manager.
"""


class CoordinatorAgent:
    """LLM-based coordinator that produces structured routing plans."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = build_chat_model(
            settings,
            model_name=settings.coordinator_model or settings.chat_model,
            temperature=0,
        )

        logger.info(
            "[agents:coordinator] Initialized CoordinatorAgent with provider=%s, model=%s",
            settings.chat_provider,
            settings.coordinator_model,
        )

    async def plan(
        self,
        message: str,
        history: list[ChatMessage],
        *,
        available_specialists: list[str],
    ) -> CoordinatorPlan:
        """Return a routing plan for the given turn."""
        started = time.monotonic()
        model = self.model.with_structured_output(CoordinatorPlan)
        payload = {
            "message": message,
            "history": [msg.model_dump() for msg in history],
            "available_specialists": available_specialists,
        }

        try:
            result = await model.ainvoke(
                [
                    SystemMessage(content=COORDINATOR_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ]
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            logger.info("[agents:coordinator] Plan created in %sms", latency_ms)
            return result
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
