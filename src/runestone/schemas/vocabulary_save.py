"""Shared internal schemas for vocabulary save planning and persistence."""

from dataclasses import dataclass
from typing import Any, Literal, cast

from pydantic import BaseModel, Field, field_validator

from runestone.constants import VOCABULARY_PRIORITY_DEFAULT, VOCABULARY_PRIORITY_HIGH, VOCABULARY_PRIORITY_LOW

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


class PriorityWordSaveItem(BaseModel):
    """Internal payload for inserting or prioritizing a vocabulary item."""

    word_phrase: str = Field(..., description="Canonical Swedish word or phrase to persist")
    translation: str = Field(..., description="Concise translation for the saved item")
    example_phrase: str | None = Field(None, description="Natural Swedish example sentence")
    extra_info: str | None = Field(None, description="Compact grammar or usage note")
    in_learn: bool = Field(True, description="Whether the item should be active in the learning set")
    priority_learn: int = Field(
        default=VOCABULARY_PRIORITY_DEFAULT,
        ge=VOCABULARY_PRIORITY_HIGH,
        le=VOCABULARY_PRIORITY_LOW,
        description="Learning priority where 0 is highest and 9 is lowest",
    )

    @field_validator("priority_learn", mode="before")
    @classmethod
    def reject_boolean_priority_learn(cls, v: Any) -> Any:
        """Reject boolean payloads to avoid silent bool-to-int coercion."""
        if isinstance(v, bool):
            raise ValueError("priority_learn must be an integer between 0 and 9")
        return v


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
