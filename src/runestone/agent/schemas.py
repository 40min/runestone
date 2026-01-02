"""
Pydantic schemas for the chat agent.

This module defines the data models for chat requests and responses.
"""

from typing import List, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single chat message."""

    role: Literal["user", "assistant"] = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The message content")


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    message: str = Field(..., description="The user's message", min_length=1)
    history: List[ChatMessage] = Field(default_factory=list, description="Conversation history")


class ChatResponse(BaseModel):
    """Response from the chat agent."""

    message: str = Field(..., description="The assistant's response")
