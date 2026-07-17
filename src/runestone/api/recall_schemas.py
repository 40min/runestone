"""API schemas for authenticated recall queue management."""

from pydantic import BaseModel


class RecallWordResponse(BaseModel):
    """Display-safe vocabulary data for one recall queue entry."""

    id: int
    word_phrase: str
    translation: str | None = None
    example_phrase: str | None = None


class RecallResponse(BaseModel):
    """Current recall configuration and ordered queue."""

    configured: bool
    delivery_enabled: bool
    words: list[RecallWordResponse]
