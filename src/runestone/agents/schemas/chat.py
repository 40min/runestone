"""Chat transport models and emotion normalization for agent requests/responses."""

import json
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from runestone.agents.schemas.news import NewsSource
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


class VoiceTranscriptionResponse(BaseModel):
    """Response from voice transcription."""

    text: str = Field(..., description="The transcribed text from voice input")
