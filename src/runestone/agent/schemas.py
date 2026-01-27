"""
Pydantic schemas for the chat agent.

This module defines the data models for chat requests and responses.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single chat message."""

    id: Optional[int] = Field(None, description="Message ID")
    role: Literal["user", "assistant"] = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The message content")
    created_at: Optional[datetime] = Field(None, description="Message creation timestamp")

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    message: str = Field(..., description="The user's message", min_length=1)


class ChatResponse(BaseModel):
    """Response from the chat agent."""

    message: str = Field(..., description="The assistant's response")


class ChatHistoryResponse(BaseModel):
    """Response containing conversation history."""

    messages: List[ChatMessage] = Field(..., description="List of chat messages")


class ImageChatResponse(BaseModel):
    """Response from image OCR + translation."""

    message: str = Field(..., description="The assistant's translation response")


class VoiceTranscriptionResponse(BaseModel):
    """Response from voice transcription."""

    text: str = Field(..., description="The transcribed text from voice input")
