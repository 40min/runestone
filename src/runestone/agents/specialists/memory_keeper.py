"""
Post-response specialist that maintains learner memory with memory tools.
"""

import json
import logging
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import ValidationError

from runestone.agents.llm import build_chat_model
from runestone.agents.specialists.base import BaseSpecialist, SpecialistContext, SpecialistResult
from runestone.agents.tools.context import AgentContext
from runestone.agents.tools.memory import (
    promote_to_strength,
    read_memory,
    update_memory_priority,
    update_memory_status,
    upsert_memory_item,
)
from runestone.config import Settings

logger = logging.getLogger(__name__)


MEMORY_KEEPER_SYSTEM_PROMPT = """
You are MemoryKeeper, an internal agent that maintains persistent memory about a student.
You do not interact with the student. You observe a single structured turn and decide
whether memory tools should be called.

## Input Format
- `teacher_response`: the Teacher's message this turn
- `student_message`: the student's message this turn
- `history`: prior turns for context only — never a trigger for memory actions

## Trigger Rules
1. **Teacher-driven**: act when `teacher_response` explicitly identifies a durable learning signal
   (e.g., "student has mastered X", "note that student's goal is Y").
2. **Student-driven**: act when `student_message` contains an explicit memory instruction
   (e.g., "remember that...", "forget my...", "change my goal to...").
3. **Conflict**: if teacher and student signals conflict, the student's explicit correction wins.
4. **History**: treat `history` as read-only context. Never act on older student turns.

## Mandatory Execution Pipeline
When a trigger is detected, you MUST complete ALL steps below in order.
Do not stop after reading.
Step 1 — READ:   Call read_memory with a category filter scoped to the relevant category.
Step 2 — DECIDE: Compare results against the incoming signal. Choose the correct write tool if changes are needed.
Step 3 — WRITE:  Call the write tool (upsert_memory_item, update_memory_status,
update_memory_priority, or promote_to_strength).

If no trigger is detected → return `no_action` immediately. Do not call any tools.

## Conservative Bias
- Default to `no_action`. Only proceed when the signal is explicit and durable.
- Do not infer facts, mastery, or preferences from weak or indirect signals.
- Prefer updating an existing item over creating a duplicate (that's what Step 1 is for).
- Never call `read_memory` without filters unless a broad inspection is explicitly required.
- Never call `read_memory` as a standalone action — it is always a precursor to a write.

## Category Rules

| Category | Allowed write operations | Trigger condition |
|----------|--------------------------|-------------------|
| `area_to_improve` | create, update, change status/priority | explicit learning signal or student instruction |
| `personal_info` | create, update, outdate | explicit durable fact or student correction |
| `knowledge_strength` | create, update, archive | explicit durable strength or student correction |

**Promotion**: use `promote_to_strength` to graduate an item from `area_to_improve` →
`knowledge_strength`. Do not manually delete and recreate.

## Allowed Tools
`read_memory`, `upsert_memory_item`, `update_memory_status`,
`update_memory_priority`, `promote_to_strength`

## Output Contract
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

## Signal Classification Reference

**Act on these (explicit memory instructions):**
- "remember that my native language is Finnish"
- "forget my old goal" → outdate or update the relevant item
- "that memory is wrong, it should be X"
- "change my goal to speaking practice"
- "mark this topic as mastered"
- Teacher: "student has now mastered the present perfect"

**Do NOT act on these (not memory instructions):**
- Student practicing sentences → ordinary interaction, no durable signal
- Student saying "I find grammar boring" → implicit preference, not an instruction
- Student expressing frustration → emotional signal, not a memory change request
- Student re-mentioning an earlier fact → restatement, not a correction
- Teacher giving feedback mid-lesson → instructional output, not a persistence directive
"""


class MemoryKeeperSpecialist(BaseSpecialist):
    """Tool-using post-response specialist for durable memory maintenance."""

    def __init__(self, settings: Settings):
        super().__init__(name="memory_keeper")
        self.settings = settings
        self.model = build_chat_model(settings, "memory_keeper")
        self.agent = self._build_agent()
        logger.info(
            "[agents:memorykeeper] Initialized MemoryKeeperSpecialist with provider=%s, model=%s",
            settings.memory_keeper_provider,
            settings.memory_keeper_model,
        )

    def _build_agent(self):
        """Build the internal tool-using agent for memory maintenance."""
        return create_agent(
            model=self.model,
            tools=[
                read_memory,
                upsert_memory_item,
                update_memory_status,
                update_memory_priority,
                promote_to_strength,
            ],
            system_prompt=MEMORY_KEEPER_SYSTEM_PROMPT,
            context_schema=AgentContext,
        )

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        payload = {
            "student_message": context.message,
            "history": [msg.model_dump(mode="json") for msg in context.history],
            "teacher_response": context.teacher_response,
            "routing_reason": context.routing_reason,
            "phase": "post_response",
        }

        try:
            result = await self.agent.ainvoke(
                {"messages": [HumanMessage(content=json.dumps(payload, ensure_ascii=False))]},
                context=AgentContext(user=context.user),
            )
        except Exception as exc:
            logger.warning("[agents:memorykeeper] Agent execution failed: %s", exc, exc_info=True)
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

        parsed = self._parse_result(result.get("messages", []))
        if parsed is None:
            logger.warning("[agents:memorykeeper] Failed to parse final agent result")
            return SpecialistResult(
                status="error",
                actions=[],
                info_for_teacher="",
                artifacts={"trigger_source": "unknown", "summary": "invalid_agent_output", "notes": []},
            )
        return parsed

    @staticmethod
    def _parse_result(messages: list[Any]) -> SpecialistResult | None:
        for message in reversed(messages):
            if not isinstance(message, AIMessage):
                continue
            if getattr(message, "tool_calls", None):
                continue
            content = message.content
            if not isinstance(content, str) or not content.strip():
                continue
            json_content = content.strip()
            if json_content.startswith("```"):
                start = json_content.find("{")
                end = json_content.rfind("}")
                if start != -1 and end != -1 and end >= start:
                    json_content = json_content[start : end + 1]
            try:
                return SpecialistResult.model_validate_json(json_content)
            except (ValidationError, ValueError):
                continue
        return None
