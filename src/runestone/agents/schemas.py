"""
Pydantic schemas for the chat agent.

This module defines the data models for chat requests and responses.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

from runestone.constants import DEFAULT_TEACHER_EMOTION, TeacherEmotion
from runestone.schemas.vocabulary_save import WordSaveCandidate


def normalize_teacher_emotion(value: Any) -> TeacherEmotion:
    """Return a safe Teacher avatar emotion for API and persistence boundaries."""
    if isinstance(value, str):
        try:
            return TeacherEmotion(value.strip().lower())
        except ValueError:
            pass
    if isinstance(value, TeacherEmotion):
        return value
    return DEFAULT_TEACHER_EMOTION


class NewsSource(BaseModel):
    """News source metadata for assistant responses."""

    title: str = Field(..., description="Headline/title of the news article")
    url: HttpUrl = Field(..., description="URL of the news article")
    date: str = Field(..., description="Published date string as returned by search")


class NewsSpecialistArticle(BaseModel):
    """Structured news article payload produced by NewsAgent."""

    title: str = Field(..., description="Headline/title of the news article")
    url: HttpUrl = Field(..., description="URL of the news article")
    date: str = Field(..., description="Published date string as returned by search")
    snippet: str = Field("", description="Short summary or snippet used for teacher composition")
    article_text: str = Field("", description="Optional extracted article text when NewsAgent read the article")


class AgentPersonalInfoStatus(str, Enum):
    """Internal personal-info workflow statuses used by keeper and maintainer."""

    ACTIVE = "active"
    CORRECTION = "correction"
    OUTDATED = "outdated"


class ChatMessage(BaseModel):
    """A single chat message."""

    id: Optional[int] = Field(None, description="Message ID")
    role: Literal["user", "assistant"] = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The message content")
    sources: Optional[list[NewsSource]] = Field(None, description="Optional list of cited news sources")
    teacher_emotion: TeacherEmotion = Field(
        DEFAULT_TEACHER_EMOTION,
        description="Internal UI metadata selecting the Teacher avatar for assistant messages",
    )
    created_at: Optional[datetime] = Field(None, description="Message creation timestamp")

    @field_validator("sources", mode="before")
    @classmethod
    def deserialize_sources(cls, value):
        if isinstance(value, str):
            try:
                data = json.loads(value)
            except json.JSONDecodeError:
                return None
            return data if isinstance(data, list) else None
        return value

    @field_validator("teacher_emotion", mode="before")
    @classmethod
    def deserialize_teacher_emotion(cls, value):
        return normalize_teacher_emotion(value)

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    message: str = Field(..., description="The user's message", min_length=1)
    tts_expected: bool = Field(False, description="Whether to synthesize TTS audio for the response")
    speed: float = Field(1.0, description="Speed of the speech (0.25 to 4.0)", ge=0.25, le=4.0)


class ChatResponse(BaseModel):
    """Response from the chat agent."""

    message: str = Field(..., description="The assistant's response")
    sources: Optional[list[NewsSource]] = Field(None, description="Optional list of cited news sources")
    teacher_emotion: TeacherEmotion = Field(
        DEFAULT_TEACHER_EMOTION,
        description="Internal UI metadata selecting the Teacher avatar for this response",
    )


class ChatHistoryResponse(BaseModel):
    """Response containing conversation history."""

    chat_id: str = Field(..., description="Current active chat session ID")
    chat_mismatch: bool = Field(False, description="Whether client-provided chat id mismatched current server chat id")
    latest_id: int = Field(..., description="Latest message ID in active chat (0 if empty)")
    has_more: bool = Field(False, description="Whether additional pages are available after this response")
    history_truncated: bool = Field(
        False, description="Whether older messages before this cursor were already truncated by retention"
    )
    messages: list[ChatMessage] = Field(..., description="List of chat messages")


class ImageChatResponse(BaseModel):
    """Response from image OCR + translation."""

    message: str = Field(..., description="The assistant's translation response")
    teacher_emotion: TeacherEmotion = Field(
        DEFAULT_TEACHER_EMOTION,
        description="Internal UI metadata selecting the Teacher avatar for this response",
    )


class LearningMemorySignal(BaseModel):
    """Teacher-declared structured learning-memory signal for post-phase handling."""

    signal_type: Literal["new_issue", "improving", "mastered", "regressed", "content_correction"]
    summary: str = Field(..., description="Compact internal summary of the learning-memory signal")
    memory_id: int | None = Field(
        default=None,
        description="Optional existing `area_to_improve` memory item id targeted by this signal",
    )

    @field_validator("summary", mode="before")
    @classmethod
    def normalize_summary(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("summary")
    @classmethod
    def require_non_empty_summary(cls, value: str) -> str:
        if not value:
            raise ValueError("empty_learning_memory_summary")
        return value

    @field_validator("memory_id", mode="before")
    @classmethod
    def validate_memory_id(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        return value

    @field_validator("memory_id")
    @classmethod
    def require_positive_memory_id(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value <= 0:
            raise ValueError("invalid_memory_id")
        return value


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


class VoiceTranscriptionResponse(BaseModel):
    """Response from voice transcription."""

    text: str = Field(..., description="The transcribed text from voice input")


class RoutingItem(BaseModel):
    """Routing decision for a specialist agent."""

    name: str = Field(..., description="Specialist name to invoke")
    reason: str = Field(..., description="Why this specialist should run")


class CoordinatorPlan(BaseModel):
    """Coordinator routing plan for a single turn."""

    pre_response: list[RoutingItem] = Field(default_factory=list, description="Pre-response specialists")
    post_response: list[RoutingItem] = Field(default_factory=list, description="Post-response specialists")
    audit: dict = Field(default_factory=dict, description="Audit metadata for observability")


class TeacherSideEffect(BaseModel):
    """Typed side-effect payload consumed by the teacher prompt layer."""

    name: str = Field(..., description="Specialist name")
    phase: str = Field(..., description="Execution phase")
    status: str = Field(..., description="Specialist status")
    info_for_teacher: str = Field("", description="Teacher-facing summary")
    artifacts: dict[str, Any] = Field(default_factory=dict, description="Structured specialist artifacts")
    routing_reason: str = Field("", description="Coordinator rationale")
    latency_ms: int | None = Field(None, description="Specialist execution latency in milliseconds")
    created_at: datetime | None = Field(None, description="Persisted record timestamp")


class CoordinatorRow(BaseModel):
    """Coordinator lifecycle row used to track background post-stage state."""

    id: int = Field(..., description="Persisted coordinator row id")
    status: str = Field(..., description="Coordinator status")
    created_at: datetime | None = Field(None, description="Persisted row timestamp")
