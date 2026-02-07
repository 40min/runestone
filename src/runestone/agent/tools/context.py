"""Shared context for agent tools."""

import asyncio
from dataclasses import dataclass

from runestone.db.models import User
from runestone.services.user_service import UserService
from runestone.services.vocabulary_service import VocabularyService


@dataclass
class AgentContext:
    """Context passed to agent tools at runtime."""

    user: User
    # we can't use DI of FastAPI here, so had to put the service to context
    user_service: UserService
    vocabulary_service: VocabularyService
    # Lock to prevent concurrent database access from multiple tool calls
    db_lock: "asyncio.Lock"
