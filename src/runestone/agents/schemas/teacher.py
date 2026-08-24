"""Structured Teacher output and internal generation result."""

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, field_validator

from runestone.agents.schemas.chat import normalize_teacher_emotion
from runestone.agents.schemas.memory import LearningMemorySignal
from runestone.constants import DEFAULT_TEACHER_EMOTION, TeacherEmotion
from runestone.schemas.vocabulary_save import WordSaveCandidate


class TeacherOutput(BaseModel):
    """Structured Teacher response envelope; only `message` is visible to students."""

    message: str = Field(..., description="Student-facing assistant reply")
    emotion: TeacherEmotion = Field(
        DEFAULT_TEACHER_EMOTION,
        description="Teacher avatar emotion metadata; never include this in the student-facing message",
    )
    grammar_source_urls: list[str] | None = Field(
        default=None,
        description="Optional grammar reference URLs. Never invent or guess URLs.",
    )
    vocabulary_candidates: list[WordSaveCandidate] = Field(
        default_factory=list,
        description="Teacher-proposed Swedish vocabulary candidates for post-response WordKeeper handling",
    )
    learning_memory_signals: list[LearningMemorySignal] = Field(
        default_factory=list,
        description="Teacher-proposed structured learning-memory signals for post-response handling",
    )

    @field_validator("emotion", mode="before")
    @classmethod
    def normalize_emotion(cls, value):
        return normalize_teacher_emotion(value)

    @field_validator("grammar_source_urls", mode="before")
    @classmethod
    def normalize_grammar_source_urls(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return None

        normalized: list[str] = []
        seen_urls: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                continue
            url = item.strip()
            if not url or url in seen_urls:
                continue
            normalized.append(url)
            seen_urls.add(url)
        return normalized

    @field_validator("learning_memory_signals")
    @classmethod
    def normalize_learning_memory_signals(cls, value: list[LearningMemorySignal]) -> list[LearningMemorySignal]:
        deduplicated: list[LearningMemorySignal] = []
        seen: set[tuple[str, str, int | None]] = set()
        for signal in value:
            if signal.signal_type == "new_issue" and signal.memory_id is not None:
                raise ValueError("new_issue_cannot_have_memory_id")
            key = (signal.signal_type, signal.summary, signal.memory_id)
            if key in seen:
                continue
            deduplicated.append(signal)
            seen.add(key)
        if len(deduplicated) > 3:
            raise ValueError("too_many_learning_memory_signals")
        return deduplicated


@dataclass(slots=True)
class TeacherGenerationResult:
    """Internal teacher response payload shared across orchestration layers."""

    message: str
    emotion: TeacherEmotion = DEFAULT_TEACHER_EMOTION
    grammar_source_urls: list[str] | None = None
    vocabulary_candidates: list[WordSaveCandidate] = field(default_factory=list)
    learning_memory_signals: list[LearningMemorySignal] = field(default_factory=list)
    final_messages: list[Any] = field(default_factory=list)
