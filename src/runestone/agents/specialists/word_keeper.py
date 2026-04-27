"""
WordKeeper specialist responsible for vocabulary capture and prioritization.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Literal

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from runestone.agents.llm import build_chat_model
from runestone.agents.service_providers import provide_vocabulary_service
from runestone.agents.specialists.base import BaseSpecialist, SpecialistAction, SpecialistContext, SpecialistResult
from runestone.config import Settings
from runestone.core.observability import elapsed_ms_since
from runestone.schemas.vocabulary_save import VocabularyPrioritizationAction, WordSaveCandidate

logger = logging.getLogger(__name__)


WORDKEEPER_SYSTEM_PROMPT = """
You are WordKeeper, an internal vocabulary extraction specialist for a Swedish tutoring app.
You do not interact with the student. Your sole job is to decide whether vocabulary should be saved.

## Core Principle
Be conservative. When in doubt, return no candidates.
Never invent candidates simply because a Swedish word appears in the conversation.

## Phase Behavior

### Pre-response phase
- Save ONLY when the student explicitly requests it (e.g. "save", "add", "remember", "keep this word").
- Do NOT save words just because an earlier assistant message in `history` highlighted or introduced them.

### Post-response phase
- Treat `teacher_response` as the authoritative current teacher message.
- Save vocabulary when the teacher explicitly highlights it, including:
  - Named vocabulary sections (e.g. "подсказка по лексике", "key vocabulary", "useful words").
  - Structured word–translation lists or bullet pairs regardless of the header label.
  - Explicit save phrasing (e.g. "the key words here are", "good words to memorize").
- Do NOT treat ordinary exercise wording as a save signal, even if words are bolded or repeated.
- Do NOT save words from prompts like "use X or Y in a sentence", "try another sentence with X",
  or other drill wording unless the teacher also explicitly says the words are worth remembering.
- By default, ignore older assistant messages in `history` when deciding what to save.
- Use older history ONLY when the student explicitly asks to revisit it.

## What NOT to Save
- Words the student merely reused in their message.
- Words that appear only in correction or example sentences without a save signal.
- Words introduced in earlier turns unless the student explicitly references them.
- Words that are only mentioned as options in a practice prompt or writing exercise.
- Bolded words that are emphasized for an exercise but not presented as vocabulary to memorize.

## Candidate Field Rules
- `word_phrase` — the canonical Swedish learning item, not a noisy slice of the surrounding sentence.
- `source_form` — optional original form from the current context when it differs from `word_phrase`.

## Normalization Rules
- No leading articles: save `hund`, not `en hund`; save `äpple`, not `ett äpple`.
- Allow definite or bestämd forms when the form itself is the learning target.
- Use smart lowercase: lowercase ordinary words, but preserve acronyms, personal names, proper nouns, and fixed casing.
- Prefer lemma or base form unless the inflected form matters.
- Do not save bare `att` for verbs; keep `att` inside real constructions such as
  `ha svårt att`, `komma att`, or `se till att`.
- Preserve particles, prepositions, and reflexives that change meaning, such as
  `tycka om`, `hälsa på`, `höra av sig`, and `se fram emot`.
- Preserve fixed phrases exactly, minus surrounding punctuation and extra whitespace.
- Keep Swedish characters; never ASCII-fold `å`, `ä`, or `ö`.
- Use canonical duplicate handling so casing, articles, and punctuation do not create near-duplicates.
- Do not save grammar-only tokens as vocabulary unless explicitly presented as learning items.

## Extraction Rules (apply to every candidate)
- Return only canonical word keys and optional context source forms.
- Do not generate translations, examples, grammar notes, or reasons.

## Output
Return valid JSON matching the provided schema. If there are no candidates, return an empty list.
"""


WORDKEEPER_ENRICHMENT_PROMPT = """
You are WordKeeper, an internal vocabulary enrichment specialist for a Swedish tutoring app.
You do not interact with the student.

Generate full save fields only for the requested new vocabulary items.

## Field Rules
- `candidate_id` — copy the requested candidate id exactly.
- `word_phrase` — copy the requested canonical Swedish learning item exactly.
- `translation` — a concise translation in `target_translation_language`, not a grammar explanation.
- `example_phrase` — a natural Swedish sentence that demonstrates the saved item or full phrase.
- `extra_info` — an optional compact learner note with grammar or usage details.

## Context Rules
- Prefer translations and examples already present in `teacher_response` when they fit the requested word.
- Otherwise infer a concise translation and generate a short, natural Swedish example.
- If `source_form` differs from `word_phrase`, use it only when useful for `extra_info`.

## Extra Info Guidance
`extra_info` is a compact learner note, not a second translation and not a full grammar lesson.
Use it for high-value morphology or usage details, for example:
- `en-word noun; plural: hundar; definite: hunden`
- `verb; infinitive: förstå; present: förstår; past: förstod; supine: förstått`
- `adjective; common: vacker; neuter: vackert; plural/definite: vackra`
- `particle verb; "tycka om" means "to like"`
- `fixed phrase; common in spoken Swedish`
If a saved item is canonicalized from a context form, mention the relation when useful,
for example `en-word noun; context form "hunden" is definite singular`.
If unsure, leave `extra_info` empty rather than guess.

## Output
Return valid JSON matching the provided schema. Include one item for each requested word you can complete.
"""


class WordKeeperExtraction(BaseModel):
    """Structured result for WordKeeper extraction."""

    decision: Literal["no_action", "save_words"] = Field(..., description="Whether any words should be saved")
    candidates: list[WordSaveCandidate] = Field(default_factory=list, description="Words selected for saving")


class WordEnrichmentItem(BaseModel):
    """Full vocabulary payload for a new word that will be inserted."""

    candidate_id: str = Field(..., description="The requested candidate id")
    word_phrase: str = Field(..., description="The requested Swedish word or phrase")
    translation: str | None = Field(None, description="Concise translation of the word_phrase")
    example_phrase: str | None = Field(None, description="Natural Swedish example sentence")
    extra_info: str | None = Field(None, description="Compact grammar or usage note when useful")


class WordKeeperEnrichment(BaseModel):
    """Structured result for new-word enrichment."""

    items: list[WordEnrichmentItem] = Field(default_factory=list, description="Completed new vocabulary items")


@dataclass
class SaveRunState:
    """Mutable save bookkeeping for one WordKeeper run."""

    save_candidates: list[WordSaveCandidate] = field(default_factory=list)
    priority_actions: list[VocabularyPrioritizationAction] = field(default_factory=list)
    saved_words: list[str] = field(default_factory=list)
    skipped_words: list[dict[str, str]] = field(default_factory=list)
    action_counts: dict[str, int] = field(
        default_factory=lambda: {"created": 0, "restored": 0, "prioritized": 0, "already_prioritized": 0}
    )
    service_error_count: int = 0

    def artifacts(self, *, include_action_counts: bool = False) -> dict[str, object]:
        artifacts = {
            "saved_words": self.saved_words,
            "skipped_words": self.skipped_words,
            "save_candidates": [candidate.model_dump() for candidate in self.save_candidates],
            "priority_actions": [action.as_artifact() for action in self.priority_actions],
            "new_word_phrases": [action.word_phrase for action in self.priority_actions if action.action == "missing"],
        }
        if include_action_counts:
            artifacts["action_counts"] = self.action_counts
        return artifacts


class WordKeeperSpecialist(BaseSpecialist):
    """Specialist that owns vocabulary capture and prioritization."""

    def __init__(self, settings: Settings):
        super().__init__(name="word_keeper")
        self.settings = settings
        self.model = build_chat_model(settings, "word_keeper")
        logger.info(
            "[agents:wordkeeper] Initialized WordKeeperSpecialist with provider=%s, model=%s",
            settings.word_keeper_provider,
            settings.word_keeper_model,
        )

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        started = time.monotonic()
        extraction = await self._extract_candidates(context)
        if extraction.decision == "no_action" or not extraction.candidates:
            return self._no_action_result(SaveRunState())

        state = SaveRunState(save_candidates=extraction.candidates)

        try:
            async with provide_vocabulary_service() as vocabulary_service:
                priority_actions = await vocabulary_service.prepare_priority_word_save(
                    extraction.candidates,
                    user_id=context.user.id,
                )
                self._record_priority_actions(priority_actions, state)
                await self._enrich_and_save_new_words(context, vocabulary_service, priority_actions, state)

        except Exception as exc:
            latency_ms = elapsed_ms_since(started)
            logger.warning("[agents:wordkeeper] Failed to save words after %sms: %s", latency_ms, exc, exc_info=True)
            info_for_teacher = (
                f"Partially saved {len(state.saved_words)} vocabulary item(s) before an internal error."
                if state.saved_words
                else ""
            )
            return SpecialistResult(
                status="error",
                actions=[
                    SpecialistAction(
                        tool="prioritize_words_for_learning",
                        status="error",
                        summary="Failed to save vocabulary candidates",
                    )
                ],
                info_for_teacher=info_for_teacher,
                artifacts=state.artifacts(),
            )

        if not state.saved_words and state.service_error_count > 0:
            return self._error_result(state)

        if not state.saved_words:
            return self._no_action_result(state)

        summary = (
            f"created={state.action_counts['created']}, restored={state.action_counts['restored']}, "
            f"prioritized={state.action_counts['prioritized']}, "
            f"already_prioritized={state.action_counts['already_prioritized']}"
        )
        logger.info(
            "[agents:wordkeeper] Saved %s word(s) in %sms: %s",
            len(state.saved_words),
            elapsed_ms_since(started),
            summary,
        )
        info_for_teacher = f"Saved {len(state.saved_words)} vocabulary item(s) for future recall."
        if state.service_error_count:
            info_for_teacher += f" Skipped {state.service_error_count} item(s) due to internal errors."
        return SpecialistResult(
            status="action_taken",
            actions=[
                SpecialistAction(
                    tool="prioritize_words_for_learning",
                    status="success",
                    summary=summary,
                )
            ],
            info_for_teacher=info_for_teacher,
            artifacts=state.artifacts(include_action_counts=True),
        )

    @staticmethod
    def _record_priority_actions(priority_actions: list[VocabularyPrioritizationAction], state: SaveRunState) -> None:
        state.priority_actions = priority_actions
        for action_result in priority_actions:
            if action_result.action == "missing":
                continue
            state.action_counts[action_result.action] += 1
            state.saved_words.append(action_result.word_phrase)

    async def _enrich_and_save_new_words(
        self,
        context: SpecialistContext,
        vocabulary_service,
        priority_actions: list[VocabularyPrioritizationAction],
        state: SaveRunState,
    ) -> None:
        new_candidates = [action for action in priority_actions if action.action == "missing"]
        if not new_candidates:
            return

        enrichment = await self._enrich_new_words(context, new_candidates)
        if enrichment is None:
            state.skipped_words.extend(
                {"word_phrase": candidate.word_phrase, "reason": "enrichment_failed"} for candidate in new_candidates
            )
            return

        enriched_by_id = {item.candidate_id.strip(): item for item in enrichment.items if item.candidate_id.strip()}
        for action in new_candidates:
            item = enriched_by_id.get(action.candidate_id)
            if item is None:
                state.skipped_words.append({"word_phrase": action.word_phrase, "reason": "missing_enrichment"})
                continue

            completed = self._normalize_enrichment_item(item, action)
            if not completed["translation"] or not completed["example_phrase"]:
                state.skipped_words.append(
                    {"word_phrase": action.word_phrase, "reason": "missing_required_fields_after_enrichment"}
                )
                continue

            await self._save_enriched_word(context, vocabulary_service, completed, state)

    async def _save_enriched_word(
        self,
        context: SpecialistContext,
        vocabulary_service,
        completed: dict[str, str | None],
        state: SaveRunState,
    ) -> None:
        try:
            result = await vocabulary_service.upsert_priority_word(
                word_phrase=completed["word_phrase"],
                translation=completed["translation"],
                example_phrase=completed["example_phrase"],
                extra_info=completed["extra_info"],
                user_id=context.user.id,
            )
        except Exception as exc:
            state.service_error_count += 1
            # Keep partial-save behavior: reset aborted transaction and continue.
            await vocabulary_service.repo.db.rollback()
            logger.warning(
                "[agents:wordkeeper] Failed to save word '%s': %s",
                completed["word_phrase"],
                exc,
                exc_info=True,
            )
            state.skipped_words.append(
                {
                    "word_phrase": str(completed["word_phrase"]),
                    "reason": f"vocabulary_service_error: {type(exc).__name__}",
                }
            )
            return

        action = str(result.get("action", "prioritized"))
        if action not in state.action_counts:
            action = "prioritized"
        state.action_counts[action] += 1
        state.saved_words.append(str(completed["word_phrase"]))

    @staticmethod
    def _error_result(state: SaveRunState) -> SpecialistResult:
        return SpecialistResult(
            status="error",
            actions=[
                SpecialistAction(
                    tool="prioritize_words_for_learning",
                    status="error",
                    summary="Failed to save vocabulary candidates",
                )
            ],
            info_for_teacher="",
            artifacts={**state.artifacts(), "saved_words": []},
        )

    @staticmethod
    def _no_action_result(state: SaveRunState) -> SpecialistResult:
        return SpecialistResult(
            status="no_action",
            actions=[],
            info_for_teacher="",
            artifacts={**state.artifacts(), "saved_words": []},
        )

    async def _extract_candidates(self, context: SpecialistContext) -> WordKeeperExtraction:
        model = self.model.with_structured_output(WordKeeperExtraction)
        payload = {
            "message": context.message,
            "history": [msg.model_dump(mode="json") for msg in context.history],
            "teacher_response": context.teacher_response,
            "routing_reason": context.routing_reason,
            "phase": "post_response" if context.teacher_response else "pre_response",
            "target_translation_language": self._target_translation_language(context),
        }
        try:
            return await model.ainvoke(
                [
                    SystemMessage(content=WORDKEEPER_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ]
            )
        except OutputParserException as exc:
            logger.warning("[agents:wordkeeper] Extraction schema validation failed: %s", exc)
            return WordKeeperExtraction(decision="no_action", candidates=[])
        except Exception as exc:
            logger.warning("[agents:wordkeeper] Extraction failed: %s", exc, exc_info=True)
            return WordKeeperExtraction(decision="no_action", candidates=[])

    async def _enrich_new_words(
        self,
        context: SpecialistContext,
        new_candidates: list[VocabularyPrioritizationAction],
    ) -> WordKeeperEnrichment | None:
        model = self.model.with_structured_output(WordKeeperEnrichment)
        payload = {
            "new_words": [candidate.as_artifact() for candidate in new_candidates],
            "message": context.message,
            "history": [msg.model_dump(mode="json") for msg in context.history],
            "teacher_response": context.teacher_response,
            "phase": "post_response" if context.teacher_response else "pre_response",
            "target_translation_language": self._target_translation_language(context),
        }
        try:
            return await model.ainvoke(
                [
                    SystemMessage(content=WORDKEEPER_ENRICHMENT_PROMPT),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ]
            )
        except OutputParserException as exc:
            logger.warning("[agents:wordkeeper] Enrichment schema validation failed: %s", exc)
            return None
        except Exception as exc:
            logger.warning("[agents:wordkeeper] Enrichment failed: %s", exc, exc_info=True)
            return None

    @staticmethod
    def _normalize_enrichment_item(
        item: WordEnrichmentItem, action: VocabularyPrioritizationAction
    ) -> dict[str, str | None]:
        extra_info = (item.extra_info or "").strip()
        return {
            "word_phrase": action.word_phrase,
            "translation": (item.translation or "").strip(),
            "example_phrase": (item.example_phrase or "").strip(),
            "extra_info": extra_info or None,
        }

    @staticmethod
    def _target_translation_language(context: SpecialistContext) -> str:
        mother_tongue = getattr(context.user, "mother_tongue", None)
        if isinstance(mother_tongue, str) and mother_tongue.strip():
            return mother_tongue.strip()
        return "English"
