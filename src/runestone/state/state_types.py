"""
Type definitions for state management.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class UserData(BaseModel):
    """Pydantic model for user data structure."""

    db_user_id: int
    chat_id: Optional[int] = None
    is_active: bool = False
    daily_selection: Dict[str, Any] = {}
    next_word_index: int = 0  # Added for rune_recall_service compatibility


class StateData(BaseModel):
    """Pydantic model for complete state structure."""

    users: Dict[str, UserData] = {}
