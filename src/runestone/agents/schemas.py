"""
Pydantic schemas for the chat agent.

This module defines the data models for chat requests and responses.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

from runestone.constants import DEFAULT_TEACHER_EMOTION, TeacherEmotion


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


class TeacherOutput(BaseModel):
    """Structured Teacher response envelope; only `message` is visible to students."""

    message: str = Field(..., description="Student-facing assistant reply")
    emotion: TeacherEmotion = Field(
        DEFAULT_TEACHER_EMOTION,
        description="Teacher avatar emotion metadata; never include this in the student-facing message",
    )

    @field_validator("emotion", mode="before")
    @classmethod
    def normalize_emotion(cls, value):
        return normalize_teacher_emotion(value)


@dataclass(slots=True)
class TeacherGenerationResult:
    """Internal teacher response payload shared across orchestration layers."""

    message: str
    emotion: TeacherEmotion = DEFAULT_TEACHER_EMOTION
    final_messages: list[Any] = field(default_factory=list)


class VoiceTranscriptionResponse(BaseModel):
    """Response from voice transcription."""

    text: str = Field(..., description="The transcribed text from voice input")


class RoutingItem(BaseModel):
    """Routing decision for a specialist agent."""

    name: str = Field(..., description="Specialist name to invoke")
    reason: str = Field(..., description="Why this specialist should run")
    chat_history_size: int = Field(
        ...,
        description="Number of most recent chat messages to pass to the specialist",
        ge=0,
        le=20,
    )


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
