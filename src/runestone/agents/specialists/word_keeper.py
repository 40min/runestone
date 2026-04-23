"""
WordKeeper specialist responsible for vocabulary capture and prioritization.
"""

import json
import logging
import time
from typing import Literal

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from runestone.agents.llm import build_chat_model
from runestone.agents.service_providers import provide_vocabulary_service
from runestone.agents.specialists.base import BaseSpecialist, SpecialistAction, SpecialistContext, SpecialistResult
from runestone.config import Settings
from runestone.core.observability import elapsed_ms_since

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
- `translation` — a concise target-language translation, not a grammar explanation.
- `example_phrase` — a natural Swedish sentence that demonstrates the saved item or full phrase.
- `extra_info` — an optional compact learner note with grammar or usage details.
- `reason` — a short internal reason why the word should be saved or prioritized.

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
- Ensure examples naturally demonstrate the saved item or full phrase.
- Keep translations concise; put morphology and usage in `extra_info`, not `translation`.

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

## Extraction Rules (apply to every candidate)
- Prefer translations and examples already present in the chat when they fit the candidate rules.
- Otherwise infer a concise translation in `target_translation_language` and generate a short, natural Swedish example.
- Always return `translation` and `example_phrase` for every candidate; include `extra_info` when useful.

## Output
Return valid JSON matching the provided schema. If there are no candidates, return an empty list.
"""


class SaveCandidate(BaseModel):
    """Candidate vocabulary item extracted from the current turn."""

    word_phrase: str = Field(..., description="Swedish word or phrase to save")
    translation: str | None = Field(None, description="Concise translation from the chat if available")
    example_phrase: str | None = Field(None, description="Swedish example sentence from the chat if available")
    extra_info: str | None = Field(None, description="Compact grammar or usage note when useful")
    reason: str = Field("", description="Brief reason why this word should be saved")


class WordKeeperExtraction(BaseModel):
    """Structured result for WordKeeper extraction."""

    decision: Literal["no_action", "save_words"] = Field(..., description="Whether any words should be saved")
    candidates: list[SaveCandidate] = Field(default_factory=list, description="Words selected for saving")


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
            return SpecialistResult(
                status="no_action",
                actions=[],
                info_for_teacher="",
                artifacts={"saved_words": [], "skipped_words": [], "save_candidates": []},
            )

        unique_candidates = self._dedupe_candidates(extraction.candidates)
        saved_words: list[str] = []
        skipped_words: list[dict[str, str]] = []
        save_candidates: list[dict[str, str | None]] = []
        action_counts = {"created": 0, "restored": 0, "prioritized": 0, "already_prioritized": 0}
        service_error_count = 0

        try:
            async with provide_vocabulary_service() as vocabulary_service:
                for candidate in unique_candidates:
                    completed = self._normalize_candidate(candidate)
                    save_candidates.append(
                        {
                            "word_phrase": completed["word_phrase"],
                            "translation": completed["translation"],
                            "example_phrase": completed["example_phrase"],
                            "extra_info": completed["extra_info"],
                            "reason": candidate.reason,
                        }
                    )

                    if not completed["translation"] or not completed["example_phrase"]:
                        skipped_words.append(
                            {
                                "word_phrase": candidate.word_phrase,
                                "reason": "missing_required_fields_after_completion",
                            }
                        )
                        continue

                    try:
                        result = await vocabulary_service.upsert_priority_word(
                            word_phrase=completed["word_phrase"],
                            translation=completed["translation"],
                            example_phrase=completed["example_phrase"],
                            extra_info=completed["extra_info"],
                            user_id=context.user.id,
                        )
                    except Exception as exc:
                        service_error_count += 1
                        logger.warning(
                            "[agents:wordkeeper] Failed to save word '%s': %s",
                            completed["word_phrase"],
                            exc,
                            exc_info=True,
                        )
                        skipped_words.append(
                            {
                                "word_phrase": completed["word_phrase"],
                                "reason": f"vocabulary_service_error: {type(exc).__name__}",
                            }
                        )
                        continue

                    action = str(result.get("action", "prioritized"))
                    if action not in action_counts:
                        action = "prioritized"
                    action_counts[action] += 1
                    saved_words.append(completed["word_phrase"])

        except Exception as exc:
            latency_ms = elapsed_ms_since(started)
            logger.warning("[agents:wordkeeper] Failed to save words after %sms: %s", latency_ms, exc, exc_info=True)
            info_for_teacher = (
                f"Partially saved {len(saved_words)} vocabulary item(s) before an internal error."
                if saved_words
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
                artifacts={
                    "saved_words": saved_words,
                    "skipped_words": skipped_words,
                    "save_candidates": save_candidates,
                },
            )

        if not saved_words and service_error_count > 0:
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
                artifacts={
                    "saved_words": [],
                    "skipped_words": skipped_words,
                    "save_candidates": save_candidates,
                },
            )

        if not saved_words:
            return SpecialistResult(
                status="no_action",
                actions=[],
                info_for_teacher="",
                artifacts={
                    "saved_words": [],
                    "skipped_words": skipped_words,
                    "save_candidates": save_candidates,
                },
            )

        summary = (
            f"created={action_counts['created']}, restored={action_counts['restored']}, "
            f"prioritized={action_counts['prioritized']}, already_prioritized={action_counts['already_prioritized']}"
        )
        logger.info(
            "[agents:wordkeeper] Saved %s word(s) in %sms: %s",
            len(saved_words),
            elapsed_ms_since(started),
            summary,
        )
        info_for_teacher = f"Saved {len(saved_words)} vocabulary item(s) for future recall."
        if service_error_count:
            info_for_teacher += f" Skipped {service_error_count} item(s) due to internal errors."
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
            artifacts={
                "saved_words": saved_words,
                "skipped_words": skipped_words,
                "save_candidates": save_candidates,
                "action_counts": action_counts,
            },
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

    @staticmethod
    def _dedupe_candidates(candidates: list[SaveCandidate]) -> list[SaveCandidate]:
        deduped: list[SaveCandidate] = []
        seen: set[str] = set()
        for candidate in candidates:
            normalized = candidate.word_phrase.strip().casefold()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(candidate)
        return deduped

    @staticmethod
    def _normalize_candidate(candidate: SaveCandidate) -> dict[str, str | None]:
        extra_info = (candidate.extra_info or "").strip()
        return {
            "word_phrase": candidate.word_phrase.strip(),
            "translation": (candidate.translation or "").strip(),
            "example_phrase": (candidate.example_phrase or "").strip(),
            "extra_info": extra_info or None,
        }

    @staticmethod
    def _target_translation_language(context: SpecialistContext) -> str:
        mother_tongue = getattr(context.user, "mother_tongue", None)
        if isinstance(mother_tongue, str) and mother_tongue.strip():
            return mother_tongue.strip()
        return "English"
