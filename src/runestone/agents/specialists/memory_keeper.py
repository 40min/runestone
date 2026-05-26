"""
Post-response specialist that maintains learner memory with memory tools.
"""

import json
import logging

from langchain.agents import create_agent
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

## Trigger Rules
1. **Teacher-driven**: act when `teacher_response` explicitly identifies a durable learning signal
   (e.g., "student has mastered X", "note that student's goal is Y").
2. **Student-driven**: act when `student_message` contains an explicit memory instruction
   (e.g., "remember that...", "forget my...", "change my goal to...").
3. **Conflict**: if teacher and student signals conflict, the student's explicit correction wins.

## Three-Case Execution Model

When a trigger is detected, apply one of the three cases below.
If no trigger is detected → return `no_action` immediately. Do not call any tools.

### Case A — Student explicitly asks to edit memory

Examples: remember, forget, remove, correct, change goal, reprioritize, mark mastered.

Execution:
1. READ: Call `read_memory` with a category filter scoped to the relevant category.
2. DECIDE: Compare results against the student's instruction.
3. WRITE: Call the correct write tool for the specific item(s):
   - `upsert_memory_item` for new or corrected facts
   - `update_memory_status` for mastery or outdating
   - `update_memory_priority` for explicit reprioritization
   - `delete_memory_item` for explicit forget/remove requests

Do not stop after reading. Always complete the write step.

### Case B — Teacher explicitly points out a new durable issue

Examples: a new recurring struggle, a newly named durable weakness.

Execution:
- Do NOT call `read_memory` first.
- Call `upsert_memory_item` directly using a fresh descriptive English key.
- Temporary duplicate items are an accepted tradeoff; `memory_maintainer` handles cleanup.

### Case C — Teacher explicitly signals improvement, mastery, replacement, or priority change

Examples: "You are improving with X", "You have now mastered Y", "You are still struggling with Z".

Execution:
- If `teacher_response` contains a `[memory:ID]` tag, use that numeric ID directly:
  call `update_memory_status` or `update_memory_priority` without a pre-read.
- If no `[memory:ID]` tag is present, do a single targeted `read_memory` with a category
  filter to locate the item ID, then write. Do not perform a broad unsorted scan.
- Prefer one targeted read over creating a duplicate.
- Temporary duplicates are still acceptable if a narrow read fails to find the item;
  `memory_maintainer` handles cleanup.

## Conservative Bias
- Default to `no_action`. Only proceed when the signal is explicit and durable.
- Do not infer facts, mastery, or preferences from weak or indirect signals.
- Broad start-of-session consolidation, duplicate cleanup, and routine reprioritization sweeps
  are handled by a separate `memory_maintainer`. Do not perform those sweeps unless the
  current turn explicitly requires a memory change.
- Choose one write intent per item for ordinary learning signals:
  - New durable topic or fact → `upsert_memory_item`
  - Improvement, degradation, mastery, or outdating of an existing item → `update_memory_status`
  - Explicit importance/urgency signal such as a repeated recurring error or a clearly elevated priority
    from the Teacher → `update_memory_priority`
  - Explicit student forget/remove request about a specific item → `delete_memory_item`
- Do not use both `update_memory_status` and `update_memory_priority` on the same item in the same turn
  unless the signal explicitly requires both status and urgency to change.
- Use `update_memory_priority` only for narrow, turn-local reprioritization of directly implicated item(s).
- It is acceptable to raise urgency for one item the student is explicitly struggling with again,
  or lower urgency for one item only when the Teacher explicitly frames it as less urgent.
- Never use priority changes to rebalance unrelated items or tidy the broader memory set; leave
  that work to `memory_maintainer`.
- Never call `read_memory` without filters unless a broad inspection is explicitly required.
- Never call `read_memory` as a standalone action — it must be followed by a write.
- Treat spelling corrections, nonexistent-word feedback, and one-off wrong vocabulary forms as
  vocabulary events, not durable memory. Do not create `area_to_improve` items for misspelled
  or invalid word forms such as "no such word", "that word is wrong", or "use X instead of Y".
- Only act on spelling or vocabulary mistakes when the Teacher explicitly names a broader durable
  pattern to remember, such as repeated spelling confusion or recurring word-choice trouble.

## Category Rules

| Category | Allowed write operations | Trigger condition |
|----------|--------------------------|-------------------|
| `area_to_improve` | create, update, delete, change status/priority | explicit learning signal or student instruction |
| `personal_info` | create, update, outdate, delete | explicit durable fact or student correction |

Use `area_to_improve` with status `mastered` for topics the student has resolved or learned.
Do not create a separate strength item.

## Allowed Tools
`read_memory`, `upsert_memory_item`, `update_memory_status`,
`update_memory_priority`, `delete_memory_item`

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
- "forget my old goal" → Case A: read first, then delete or outdate
- "change my goal to speaking practice" → Case A: read first, then upsert
- "mark this topic as mastered" → Case A: read first, then update status
- Teacher: "This is a recurring issue to remember: articles" → Case B: append directly
- Teacher: "You are improving with articles. [memory:42]" → Case C: update status for id=42 directly
- Teacher: "You have now mastered verb conjugation" (no id) → Case C: targeted read, then update

**Do NOT act on these (not memory instructions):**
- Student practicing sentences → ordinary interaction, no durable signal
- Student saying "I find grammar boring" → implicit preference, not an instruction
- Student expressing frustration → emotional signal, not a memory change request
- Student re-mentioning an earlier fact → restatement, not a correction
- Teacher giving feedback mid-lesson → instructional output, not a persistence directive
- Teacher saying a student-written word is misspelled, invalid, nonexistent, or should be replaced
  by another word → vocabulary correction; leave it to WordKeeper unless a recurring durable pattern is named
"""


class MemoryKeeperSpecialist(BaseSpecialist):
    """Tool-using post-response specialist for durable memory maintenance."""

    MODEL_TIMEOUT_SECONDS = 15.0

    def __init__(self, settings: Settings):
        super().__init__(name="memory_keeper")
        self.settings = settings
        self.model = build_chat_model(settings, "memory_keeper", timeout_seconds=self.MODEL_TIMEOUT_SECONDS)
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
                delete_memory_item,
            ],
            system_prompt=MEMORY_KEEPER_SYSTEM_PROMPT,
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
                config={"recursion_limit": 50},
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

        parsed = parse_specialist_result(result)
        if parsed is None:
            logger.warning("[agents:memorykeeper] Failed to parse final agent result")
            return SpecialistResult(
                status="error",
                actions=[],
                info_for_teacher="",
                artifacts={"trigger_source": "unknown", "summary": "invalid_agent_output", "notes": []},
            )
        return parsed
