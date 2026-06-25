"""
Post-response specialist that maintains personal info memory (append-only).
"""

import json
import logging

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware
from langchain_core.messages import HumanMessage

from runestone.agents.llm import build_chat_model
from runestone.agents.specialists.base import (
    BaseSpecialist,
    SpecialistContext,
    SpecialistResult,
    parse_specialist_result,
)
from runestone.agents.tools.context import AgentContext
from runestone.agents.tools.memory import append_personal_info_item
from runestone.config import Settings
from runestone.constants import RECURSION_LIMIT_PERSONAL_MEMORY_KEEPER

logger = logging.getLogger(__name__)

PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT = """
<role>
You are PersonalMemoryKeeper. You persist durable personal facts about a student.
You do not interact with the student. You observe a single turn and decide whether a personal fact should be stored.
You have ONE tool: append_personal_info_item. You never read memory.
Duplicates are acceptable — a separate maintenance process handles dedup.
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
as a fact. The student's reply in these cases is a fictional/practice sentence, not a real
personal fact.
Only save facts when the student is genuinely sharing real, durable personal details about
themselves outside of practice exercises.
</context_analysis>

<decision_tree>
1. Student states a clear, durable personal fact (and it is NOT a practice/drill example sentence)
   → call append_personal_info_item. No reads.
2. Teacher explicitly signals a personal fact to persist
   → call append_personal_info_item. No reads.
3. Student corrects a previously known fact (e.g., "I moved to Stockholm")
   → append the replacement fact with status="correction". The old fact will be reconciled automatically.
4. Student asks to forget a personal fact (e.g., "forget my goal")
   → append a removal request with status="outdated" so maintainer can reconcile it later.
5. None of the above → return no_action. Do NOT call any tools.
</decision_tree>

<tool_usage>
append_personal_info_item:
- key: short English descriptor (e.g., "native_language", "lives_in", "occupation", "learning_goal", "background")
- content: the fact in clear, concise English
- status: "active" (default), "correction" (for replacements), or "outdated" (for deletion requests)
</tool_usage>

<triggers>
Act on (durable personal facts):
- "My native language is Finnish" → append(key="native_language", content="Native language is Finnish")
- "I work as a nurse" → append(key="occupation", content="Works as a nurse")
- "My goal is conversational fluency" → append(key="learning_goal", content="Goal: conversational fluency")
- "I moved to Stockholm" → append(key="lives_in", content="Lives in Stockholm")
- "Actually, I live in Uppsala now" → append(key="lives_in", content="Lives in Uppsala", status="correction")
- "Forget my old goal" → append(key="learning_goal", content="Forget the learning goal", status="outdated")
- Teacher: "Remember that the student is a beginner" → append(key="level", content="Beginner level")

Do NOT act on (not durable personal facts):
- "I feel tired today" → transient state
- "Maybe I should study more" → vague wish
- "I find grammar boring" → fleeting preference, not factual
- Practice sentences, drill answers, or general conversation
- Learning progress signals (area_to_improve) → that's learning_memory_keeper's job
</triggers>

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


class PersonalMemoryKeeperSpecialist(BaseSpecialist):
    """Tool-using post-response specialist for personal info maintenance (append-only)."""

    MODEL_TIMEOUT_SECONDS = 8.0

    def __init__(self, settings: Settings):
        super().__init__(name="personal_memory_keeper")
        self.settings = settings
        self.model = build_chat_model(settings, "personal_memory_keeper", timeout_seconds=self.MODEL_TIMEOUT_SECONDS)
        self.agent = self._build_agent()
        logger.info(
            "[agents:personal_memory_keeper] Initialized PersonalMemoryKeeperSpecialist with provider=%s, model=%s",
            settings.memory_keeper_provider,
            settings.memory_keeper_model,
        )

    def _build_agent(self):
        """Build the internal tool-using agent for personal memory maintenance."""
        return create_agent(
            model=self.model,
            tools=[append_personal_info_item],
            middleware=[ModelRetryMiddleware(max_retries=2)],
            system_prompt=PERSONAL_MEMORY_KEEPER_SYSTEM_PROMPT,
            response_format=SpecialistResult,
            context_schema=AgentContext,
        )

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        previous_teacher_message = None
        if context.history:
            for msg in reversed(context.history):
                if msg.role == "assistant":
                    previous_teacher_message = msg.content
                    break

        payload = {
            "student_message": context.message,
            "teacher_response": context.teacher_response,
            "previous_teacher_message": previous_teacher_message,
        }

        try:
            result = await self.agent.ainvoke(
                {"messages": [HumanMessage(content=json.dumps(payload, ensure_ascii=False))]},
                config={"recursion_limit": RECURSION_LIMIT_PERSONAL_MEMORY_KEEPER},
                context=AgentContext(user=context.user),
            )
        except Exception as exc:
            logger.warning("[agents:personal_memory_keeper] Agent execution failed: %s", exc, exc_info=True)
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
            logger.warning("[agents:personal_memory_keeper] Failed to parse final agent result")
            return SpecialistResult(
                status="error",
                actions=[],
                info_for_teacher="",
                artifacts={"trigger_source": "unknown", "summary": "invalid_agent_output", "notes": []},
            )
        return parsed
