"""
Post-response specialist that maintains learning progress memory (areas to improve).
"""

import json
import logging

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware, ToolCallLimitMiddleware
from langchain_core.messages import HumanMessage

from runestone.agents.llm import build_chat_model
from runestone.agents.specialists.base import (
    BaseSpecialist,
    SpecialistContext,
    SpecialistResult,
    parse_specialist_result,
)
from runestone.agents.tools.context import AgentContext
from runestone.agents.tools.memory import (
    delete_memory_item,
    read_areas_to_improve,
    update_memory_item_content,
    update_memory_priority,
    update_memory_status,
    upsert_memory_item,
)
from runestone.config import Settings
from runestone.constants import RECURSION_LIMIT_LEARNING_MEMORY_KEEPER

logger = logging.getLogger(__name__)

LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT = """
You are LearningMemoryKeeper, an internal agent that maintains area_to_improve memory
about a student's learning progress.
You do not interact with the student. You observe a single turn and decide whether
learning memory should be updated.

<tool_usage>
read_areas_to_improve:
- Only call when your case logic requires a pre-read (Case A or Case C without ID tag).
- Never call if you already have the target item ID from a [memory:area_to_improve:<id>] tag.
</tool_usage>

<fast_path>
FIRST: Check if teacher_response contains [memory:area_to_improve:<id>].
If yes, pick the appropriate write tool(s) based on what the signal requires,
call them, then return the JSON immediately. ZERO reads.

  - Mastery / improvement / status-change signal
    → update_memory_status only.
  - Explicit content correction (the wording of the memory item should change)
    → update_memory_item_content only.
  - Both a status change AND a content correction are clearly present
    → call update_memory_status first, then update_memory_item_content once.
    Two calls maximum. Return immediately after.

This is the most common case. Do NOT call read_areas_to_improve.
Do NOT call any write tool more than once per intent.
</fast_path>

<decision_tree>
If no [memory:area_to_improve:<id>] tag found, classify into exactly ONE case:

Case A — Student explicitly asks to edit a learning topic.
  Examples: "mark this as mastered", "reprioritize my learning areas",
  "forget this old learning topic", "remove that old grammar issue".
  → Call read_areas_to_improve once, then write. One read allowed.
  → If the student explicitly asks to forget/remove a learning topic, use
    delete_memory_item after the read identifies the correct item.

Case B — Teacher explicitly identifies a durable learning issue (without an ID tag).
  The teacher signal must indicate the issue is structural, repeated, or worth tracking.
  A routine one-off correction, a typo, a spelling slip, or a vocabulary gap alone is NOT enough.
  Examples:
    "Note: student repeatedly struggles with articles"
    "This is a recurring issue: word order in questions"
    "Word order error — this keeps coming up"
  → Call upsert_memory_item directly. ZERO reads.
  Provide thorough details:
  - key: concise English descriptor of the grammar/language concept
  - content: clear explanation of what the student struggles with,
    including examples from the conversation when available
  - status: "struggling" (default for new issues)
  - priority: set based on severity (0=critical, 9=minor)

Case C — Teacher signals improvement, mastery, or status change, but NO ID tag.
  Examples: "You have now mastered verb conjugation" (without [memory:...] tag).
  → Call read_areas_to_improve once to find the item, then write.
  → If no matching item found and the signal is a learning need, fall back to
    upsert_memory_item to create it.
  → If the signal marks mastery of an unknown topic, return no_action.

None of the above → return no_action. ZERO tool calls.
</decision_tree>

<terminal_no_ops>
If a write tool returns one of these errors, stop immediately. Return no_action.
Do NOT retry, create replacements, or continue.
- "Memory item with id ... not found"
- "content update category mismatch"
</terminal_no_ops>

<conservative_bias>
- Default to no_action. Only act on explicit, durable signals.
- One write intent per item per turn.
- Do not use both update_memory_status and update_memory_priority on the same
  item unless the signal explicitly requires both.
- Use update_memory_priority only for the single item directly implicated
  by the current turn's signal. Never rebalance multiple items.
- Use `area_to_improve` with status `mastered` for topics the student has
  resolved or learned. Do not create a separate strength item.
</conservative_bias>

<output_contract>
Return valid JSON matching this exact shape and nothing else:
{
  "status": "no_action" | "action_taken" | "error",
  "info_for_teacher": string,
  "artifacts": {
    "trigger_source": "teacher" | "student" | "none",
    "summary": string,
    "notes": [string]
  }
}
</output_contract>
"""


class LearningMemoryKeeperSpecialist(BaseSpecialist):
    """Tool-using post-response specialist for learning memory (area_to_improve) maintenance."""

    MODEL_TIMEOUT_SECONDS = 15.0

    def __init__(self, settings: Settings):
        super().__init__(name="learning_memory_keeper")
        self.settings = settings
        self.model = build_chat_model(settings, "learning_memory_keeper", timeout_seconds=self.MODEL_TIMEOUT_SECONDS)
        self.agent = self._build_agent()
        logger.info(
            "[agents:learning_memory_keeper] Initialized LearningMemoryKeeperSpecialist with provider=%s, model=%s",
            settings.memory_keeper_provider,
            settings.memory_keeper_model,
        )

    def _build_agent(self):
        """Build the internal tool-using agent for learning memory maintenance."""
        return create_agent(
            model=self.model,
            tools=[
                read_areas_to_improve,
                upsert_memory_item,
                update_memory_item_content,
                update_memory_status,
                update_memory_priority,
                delete_memory_item,
            ],
            middleware=[
                ModelRetryMiddleware(max_retries=3),
                ToolCallLimitMiddleware(
                    tool_name="read_areas_to_improve",
                    run_limit=1,
                    exit_behavior="end",
                ),
            ],
            system_prompt=LEARNING_MEMORY_KEEPER_SYSTEM_PROMPT,
            response_format=SpecialistResult,
            context_schema=AgentContext,
        )

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        payload = {
            "student_message": context.message,
            "teacher_response": context.teacher_response,
        }

        try:
            result = await self.agent.ainvoke(
                {"messages": [HumanMessage(content=json.dumps(payload, ensure_ascii=False))]},
                config={"recursion_limit": RECURSION_LIMIT_LEARNING_MEMORY_KEEPER},
                context=AgentContext(user=context.user),
            )
        except Exception as exc:
            logger.warning("[agents:learning_memory_keeper] Agent execution failed: %s", exc, exc_info=True)
            return SpecialistResult(
                status="error",
                actions=[],
                info_for_teacher="",
                artifacts={
                    "trigger_source": "unknown",
                    "summary": "agent_execution_failed",
                    "notes": [type(exc).__name__],
                },
            )

        parsed = parse_specialist_result(result)
        if parsed is None:
            logger.warning("[agents:learning_memory_keeper] Failed to parse final agent result")
            return SpecialistResult(
                status="error",
                actions=[],
                info_for_teacher="",
                artifacts={"trigger_source": "unknown", "summary": "invalid_agent_output", "notes": []},
            )
        return parsed
