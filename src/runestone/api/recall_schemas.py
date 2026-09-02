"""API schemas for authenticated recall queue management."""

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator


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
    recall_start_hour: int
    recall_end_hour: int
    timezone: str
    words: list[RecallWordResponse]


class RecallSettingsUpdate(BaseModel):
    """Strict partial update for one configured recall delivery schedule."""

    model_config = ConfigDict(extra="forbid")

    recall_start_hour: StrictInt | None = Field(default=None, ge=0, le=23)
    recall_end_hour: StrictInt | None = Field(default=None, ge=0, le=23)
    delivery_enabled: StrictBool | None = None

    @model_validator(mode="after")
    def require_non_null_update(self) -> "RecallSettingsUpdate":
        """Reject empty payloads and explicit nulls while allowing omission."""
        if not self.model_fields_set:
            raise ValueError("At least one recall setting is required")
        if any(getattr(self, field_name) is None for field_name in self.model_fields_set):
            raise ValueError("Recall settings cannot be null")
        return self
