"""Transport-independent recall state data transfer objects."""

from dataclasses import dataclass, field
from enum import StrEnum


@dataclass(slots=True)
class RecallQueueWord:
    """One ordered vocabulary item in a user's recall queue."""

    id: int
    word_phrase: str
    translation: str | None = None
    example_phrase: str | None = None


@dataclass(slots=True)
class RecallState:
    """Current recall-delivery state for one Runestone user."""

    user_id: int
    telegram_username: str | None
    telegram_chat_id: int | None
    is_enabled: bool
    next_word_index: int = 0
    daily_selection: list[RecallQueueWord] = field(default_factory=list)


class RecallEnableStatus(StrEnum):
    """Outcome of resolving and enabling recall from a Telegram profile."""

    INVALID_USERNAME = "invalid_username"
    USER_NOT_FOUND = "user_not_found"
    USER_INACTIVE = "user_inactive"
    ENABLED = "enabled"


@dataclass(frozen=True, slots=True)
class RecallEnableResult:
    """Explicit outcome and prior activation state for an enable request."""

    status: RecallEnableStatus
    normalized_username: str | None = None
    user_id: int | None = None
    state: RecallState | None = None
    was_already_enabled: bool = False
