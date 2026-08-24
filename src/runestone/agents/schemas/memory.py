"""Memory status and Teacher-declared memory signals."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AgentPersonalInfoStatus(str, Enum):
    """Internal personal-info workflow statuses used by keeper and maintainer."""

    ACTIVE = "active"
    CORRECTION = "correction"
    OUTDATED = "outdated"


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
