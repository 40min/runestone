"""Shared vocabulary save schemas for priority planning."""

from dataclasses import dataclass
from typing import Literal, cast

from pydantic import BaseModel, Field

PriorityWordAction = Literal["missing", "restored", "prioritized", "already_prioritized"]
PRIORITY_WORD_ACTIONS = ("missing", "restored", "prioritized", "already_prioritized")


def priority_word_action_name(action: object, *, default: PriorityWordAction = "prioritized") -> PriorityWordAction:
    action_name = str(action)
    if action_name in PRIORITY_WORD_ACTIONS:
        return cast(PriorityWordAction, action_name)
    return default


class WordSaveCandidate(BaseModel):
    """Canonical vocabulary candidate extracted before enrichment or persistence."""

    word_phrase: str = Field(..., description="Swedish word or phrase to save")
    source_form: str | None = Field(None, description="Original context form when it differs from word_phrase")


@dataclass(frozen=True)
class RepositoryPriorityAction:
    """Repository outcome for one requested priority word phrase."""

    word_phrase: str
    action: PriorityWordAction
    word_id: int | None
    changed: bool


@dataclass(frozen=True)
class RepositoryPriorityResult:
    """Batch repository result for prioritizing existing word phrases."""

    actions: list[RepositoryPriorityAction]
    missing_word_phrases: list[str]


@dataclass(frozen=True)
class VocabularyPrioritizationAction:
    """Prioritization outcome for one normalized vocabulary save candidate."""

    candidate_id: str
    word_phrase: str
    source_form: str | None
    action: PriorityWordAction
    word_id: int | None
    changed: bool

    def as_artifact(self) -> dict[str, str | int | bool | None]:
        return {
            "candidate_id": self.candidate_id,
            "word_phrase": self.word_phrase,
            "source_form": self.source_form,
            "action": self.action,
            "word_id": self.word_id,
            "changed": self.changed,
        }
