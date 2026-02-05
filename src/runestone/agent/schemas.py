"""
Pydantic schemas for the chat agent.

This module defines the data models for chat requests and responses.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class NewsSource(BaseModel):
    """News source metadata for assistant responses."""

    title: str = Field(..., description="Headline/title of the news article")
    url: str = Field(..., description="URL of the news article")
    date: str = Field(..., description="Published date string as returned by search")


class ChatMessage(BaseModel):
    """A single chat message."""

    id: Optional[int] = Field(None, description="Message ID")
    role: Literal["user", "assistant"] = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The message content")
    sources: Optional[list[NewsSource]] = Field(None, description="Optional list of cited news sources")
    created_at: Optional[datetime] = Field(None, description="Message creation timestamp")

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


class ChatHistoryResponse(BaseModel):
    """Response containing conversation history."""

    messages: list[ChatMessage] = Field(..., description="List of chat messages")


class ImageChatResponse(BaseModel):
    """Response from image OCR + translation."""

    message: str = Field(..., description="The assistant's translation response")


class VoiceTranscriptionResponse(BaseModel):
    """Response from voice transcription."""

    text: str = Field(..., description="The transcribed text from voice input")
