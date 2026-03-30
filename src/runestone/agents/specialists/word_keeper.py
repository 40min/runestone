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

## Extraction Rules (apply to every candidate)
- `word_phrase` — the Swedish word or phrase, copied exactly as it appears.
- `translation` — prefer a translation already present in the chat; otherwise infer
  a concise one in `target_translation_language`.
- `example_phrase` — prefer a natural Swedish sentence already in the teacher
  response or recent chat; otherwise generate a short, natural one.
- Always return both `translation` and `example_phrase` for every candidate.

## Output
Return valid JSON matching the provided schema. If there are no candidates, return an empty list.
"""


class SaveCandidate(BaseModel):
    """Candidate vocabulary item extracted from the current turn."""

    word_phrase: str = Field(..., description="Swedish word or phrase to save")
    translation: str | None = Field(None, description="Concise translation from the chat if available")
    example_phrase: str | None = Field(None, description="Swedish example sentence from the chat if available")
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
        save_candidates: list[dict[str, str]] = []
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
    def _normalize_candidate(candidate: SaveCandidate) -> dict[str, str]:
        return {
            "word_phrase": candidate.word_phrase.strip(),
            "translation": (candidate.translation or "").strip(),
            "example_phrase": (candidate.example_phrase or "").strip(),
        }

    @staticmethod
    def _target_translation_language(context: SpecialistContext) -> str:
        mother_tongue = getattr(context.user, "mother_tongue", None)
        if isinstance(mother_tongue, str) and mother_tongue.strip():
            return mother_tongue.strip()
        return "English"
