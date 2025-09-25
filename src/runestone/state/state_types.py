"""
Type definitions for state management.
"""

from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class WordOfDay(BaseModel):
    id_: int
    word_phrase: str


class UserData(BaseModel):
    """Pydantic model for user data structure."""

    db_user_id: int
    chat_id: Optional[int] = None
    is_active: bool = False
    daily_selection: List[WordOfDay] = Field(default_factory=list)
    next_word_index: int = 0  # Added for rune_recall_service compatibility

    @field_validator("daily_selection", mode="before")
    @classmethod
    def validate_daily_selection(cls, v: Any) -> List[WordOfDay]:
        """Convert old format (list of lists) to new format (list of WordOfDay)."""
        if not v:
            return []

        # If already a list of WordOfDay objects, return as-is
        if v and isinstance(v[0], WordOfDay):
            return v

        # Convert old format [[id, word_phrase], ...] to [WordOfDay(...), ...]
        result = []
        for item in v:
            if isinstance(item, list) and len(item) == 2:
                id_val, word_phrase = item
                result.append(WordOfDay(id_=id_val, word_phrase=word_phrase))
            elif isinstance(item, dict):
                # Handle dict format if it exists
                result.append(WordOfDay(**item))
            else:
                # If it's already a WordOfDay object, keep it
                result.append(item)
        return result


class StateData(BaseModel):
    """Pydantic model for complete state structure."""

    users: dict[str, UserData] = {}
