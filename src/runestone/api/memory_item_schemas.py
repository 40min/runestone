"""
Pydantic schemas for memory item API.

This module defines the request and response models for memory item operations.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class MemoryCategory(str, Enum):
    """Memory category types."""

    PERSONAL_INFO = "personal_info"
    AREA_TO_IMPROVE = "area_to_improve"
    KNOWLEDGE_STRENGTH = "knowledge_strength"


class PersonalInfoStatus(str, Enum):
    """Status values for personal_info category."""

    ACTIVE = "active"
    OUTDATED = "outdated"


class AreaToImproveStatus(str, Enum):
    """Status values for area_to_improve category."""

    STRUGGLING = "struggling"
    IMPROVING = "improving"
    MASTERED = "mastered"


class KnowledgeStrengthStatus(str, Enum):
    """Status values for knowledge_strength category."""

    ACTIVE = "active"
    ARCHIVED = "archived"


DEFAULT_STATUS_BY_CATEGORY: dict[MemoryCategory, str] = {
    MemoryCategory.PERSONAL_INFO: PersonalInfoStatus.ACTIVE.value,
    MemoryCategory.AREA_TO_IMPROVE: AreaToImproveStatus.STRUGGLING.value,
    MemoryCategory.KNOWLEDGE_STRENGTH: KnowledgeStrengthStatus.ACTIVE.value,
}

VALID_STATUSES_BY_CATEGORY: dict[MemoryCategory, set[str]] = {
    MemoryCategory.PERSONAL_INFO: {s.value for s in PersonalInfoStatus},
    MemoryCategory.AREA_TO_IMPROVE: {s.value for s in AreaToImproveStatus},
    MemoryCategory.KNOWLEDGE_STRENGTH: {s.value for s in KnowledgeStrengthStatus},
}


class MemoryItemCreate(BaseModel):
    """Schema for creating a memory item."""

    category: MemoryCategory
    key: str = Field(..., min_length=1, max_length=100, description="Unique key within category")
    content: str = Field(..., min_length=1, description="Content/description of the memory item")
    status: Optional[str] = Field(None, description="Status (defaults based on category)")

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: object) -> object:
        # Treat empty strings as "not provided" so defaults can apply.
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _validate_status_for_category(self) -> "MemoryItemCreate":
        if self.status is None:
            return self

        valid_statuses = VALID_STATUSES_BY_CATEGORY.get(self.category)
        if not valid_statuses or self.status not in valid_statuses:
            raise ValueError(f"Invalid status '{self.status}' for category '{self.category.value}'")
        return self


class MemoryItemStatusUpdate(BaseModel):
    """Schema for updating memory item status."""

    status: str = Field(..., description="New status value")


class MemoryItemResponse(BaseModel):
    """Schema for memory item response."""

    id: int
    user_id: int
    category: str
    key: str
    content: str
    status: str
    created_at: datetime
    updated_at: datetime
    status_changed_at: Optional[datetime]
    metadata_json: Optional[str]

    class Config:
        from_attributes = True
