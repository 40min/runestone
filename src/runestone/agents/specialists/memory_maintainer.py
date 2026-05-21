"""
Background specialist for start-of-session memory maintenance.
"""

import logging

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from runestone.agents.llm import build_chat_model
from runestone.agents.specialists.base import (
    BaseSpecialist,
    SpecialistContext,
    SpecialistResult,
    parse_specialist_result,
)
from runestone.agents.tools.context import AgentContext
from runestone.agents.tools.memory_maintainer import (
    clear_pending_merge_plan,
    maintainer_delete_memory_item,
    maintainer_insert_memory_item,
    maintainer_read_memory,
    maintainer_update_memory_priority,
)
from runestone.config import Settings

logger = logging.getLogger(__name__)

MEMORY_MAINTAINER_SYSTEM_PROMPT = """
You are Björn, a Swedish language teacher. Before starting a new tutoring
session, perform a routine memory maintenance check.

This is an internal maintenance task. You do not interact with the student.

The default outcome of this task is NO ACTION. Merging is the exception,
not the goal. Only merge when the criteria below are clearly satisfied.
When in doubt, do not merge.

Review current memory items only in category `area_to_improve` with status
`struggling` or `improving`. Only where it clearly makes sense, consolidate
overlapping entries. The goal is clarity and usability, not compaction for its
own sake. If everything looks well-organized already, making no changes at all
is a perfectly valid outcome.

When reviewing, consider merging items that:
- cover one single teachable concept, even across slightly different contexts
- are near-duplicates or explicit repeats

Be moderate: merge when overlap is obvious and the result preserves all
meaningful sub-cases and examples from the originals. Keep items separate if
their different contexts carry distinct instructional value.

Do NOT create broad catch-all items that bundle multiple unrelated weaknesses
into one memory. A merged item must still point to one coherent topic a teacher
could practice directly.

Keep items separate when they differ by subdomain, for example:
- vocabulary confusion vs spelling
- time expressions vs V2 word order
- possessives vs definiteness
- one grammar rule vs a different grammar rule

Bad merge example:
- one giant item like "Struggles with Swedish grammar and vocabulary" followed
  by a numbered list of unrelated topics

Bad merge example (prose form — same violation in disguise):
  "Difficulties with V2 word order (especially after time adverbials,
  e.g. 'Idag har jag...' instead of 'Idag jag har...') and word order
  in subordinate clauses ('inte' placement after 'om', 'eftersom', 'att').
  Problems with verb forms: infinitive after modals ('måste säga'), tense
  confusion, future constructions ('kommer att'/'ska')."
→ Prose paragraph form does not change the violation. This item covers
  five distinct grammar topics and must be kept separate.

Good merge examples:
- duplicate or near-duplicate items about the V2 rule in main clauses
- repeated items about Swedish time-expression placement
- overlapping items about one specific possessive pattern

If you feel tempted to summarize several different weaknesses into one compact
list, do not merge them.

Language normalization rules:
- The content target language is provided in the runtime instruction message.
- If one or more merged items use another language, write the new consolidated
  content in the target language while preserving meaning.
- Always keep memory item keys in English.
- If you cannot reliably produce target-language content, fall back to English
  content.
- Keep Swedish example words/phrases as-is when they are language-study examples.
- Do not rewrite unrelated untouched items only to normalize language.

For each merge you decide to perform:
- create one new consolidated item with:
  - a descriptive key in English capturing the concept
  - key must be a new versioned key (for example: `<concept>_v2` or `<concept>_merged_v2`)
  - never reuse any original key from the merged items
  - combined content preserving all distinct sub-cases and examples
  - the same category `area_to_improve`
  - the same status as the merged items
  - priority set to the highest priority (lowest number) among merged items
- delete all original items being replaced

Merge execution rules:
- for merge creation, call `maintainer_insert_memory_item` with
  `replaced_item_ids` containing all original ids to replace
- never mix statuses in one merge group; all `replaced_item_ids` must share one status
- after a merge upsert, only delete ids listed in that `replaced_item_ids` set
- you must complete one merge (insert then delete all replaced items) before starting another

Deletion safety rule:
- when maintainer_insert_memory_item returns `Memory item saved: [ID:<n>] ...`, treat `<n>` as the consolidated item id
- never delete that consolidated item id, even if it was listed among originals by mistake

After merges, briefly review priorities:
- consider bumping up items that are recurring or YKI exam-critical
- be conservative and change priority only when clearly justified

Allowed tools:
- maintainer_read_memory
- maintainer_insert_memory_item
- maintainer_delete_memory_item
- maintainer_update_memory_priority

Broad inspection is allowed for this maintenance task.

Return valid JSON matching this exact structure and nothing else:
{
  "status": "no_action" | "action_taken" | "error",
  "actions": [{"tool": string, "status": "success" | "error", "summary": string}],
  "artifacts": {
    "maintenance_type": "chat_reset_memory_maintenance",
    "scope": {"category": "area_to_improve", "statuses": ["struggling", "improving"]},
    "reviewed_item_count": number,
    "merged_groups": [
      {
        "new_key": string,
        "new_priority": number | null,
        "replaced_item_ids": [number],
        "replaced_keys": [string],
        "status": string
      }
    ],
    "priority_updates": [
      {
        "item_id": number,
        "key": string,
        "from_priority": number | null,
        "to_priority": number | null,
        "reason": string
      }
    ],
    "summary": string,
    "no_change_reason": string | null
  }
}
"""


class MemoryMaintainerSpecialist(BaseSpecialist):
    """Background specialist that consolidates start-of-session learner memory."""

    MODEL_TIMEOUT_SECONDS = 30.0

    def __init__(self, settings: Settings):
        super().__init__(name="memory_maintainer")
        self.settings = settings
        model = build_chat_model(settings, "memory_maintainer", timeout_seconds=self.MODEL_TIMEOUT_SECONDS)
        self.agent = self._build_agent(model)
        logger.info(
            "[agents:memorymaintainer] Initialized MemoryMaintainerSpecialist with provider=%s, model=%s",
            settings.memory_maintainer_provider,
            settings.memory_maintainer_model,
        )

    def _build_agent(self, model: BaseChatModel):
        """Build the internal tool-using agent for background memory maintenance."""
        return create_agent(
            model=model,
            tools=[
                maintainer_read_memory,
                maintainer_insert_memory_item,
                maintainer_delete_memory_item,
                maintainer_update_memory_priority,
            ],
            system_prompt=MEMORY_MAINTAINER_SYSTEM_PROMPT,
            response_format=SpecialistResult,
            context_schema=AgentContext,
        )

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        clear_pending_merge_plan(context.user.id)
        language = self._memory_item_language(context)
        prompt = (
            "Run the routine chat-reset memory maintenance check.\n"
            "Language policy:\n"
            f"- Use '{language}' for memory item content.\n"
            "- If you cannot reliably produce that language, fall back to English content.\n"
            "- Keep all memory item keys in English only."
        )

        try:
            try:
                result = await self.agent.ainvoke(
                    {"messages": [HumanMessage(content=prompt)]},
                    context=AgentContext(user=context.user),
                )
            except Exception as exc:
                logger.warning("[agents:memorymaintainer] Agent execution failed: %s", exc, exc_info=True)
                return SpecialistResult(
                    status="error",
                    info_for_teacher="",
                    actions=[],
                    artifacts={
                        "maintenance_type": "chat_reset_memory_maintenance",
                        "summary": "agent_execution_failed",
                        "scope": {"category": "area_to_improve", "statuses": ["struggling", "improving"]},
                        "reviewed_item_count": 0,
                        "merged_groups": [],
                        "priority_updates": [],
                        "no_change_reason": None,
                    },
                )

            parsed = parse_specialist_result(result)
            if parsed is None:
                logger.warning("[agents:memorymaintainer] Failed to parse final agent result")
                return SpecialistResult(
                    status="error",
                    info_for_teacher="",
                    actions=[],
                    artifacts={
                        "maintenance_type": "chat_reset_memory_maintenance",
                        "summary": "invalid_agent_output",
                        "scope": {"category": "area_to_improve", "statuses": ["struggling", "improving"]},
                        "reviewed_item_count": 0,
                        "merged_groups": [],
                        "priority_updates": [],
                        "no_change_reason": None,
                    },
                )
            return parsed
        finally:
            clear_pending_merge_plan(context.user.id)

    @staticmethod
    def _memory_item_language(context: SpecialistContext) -> str:
        mother_tongue = getattr(context.user, "mother_tongue", None)
        if isinstance(mother_tongue, str) and mother_tongue.strip():
            return mother_tongue.strip()
        return "English"
