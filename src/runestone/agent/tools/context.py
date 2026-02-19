"""Shared context for agent tools."""

import asyncio
from dataclasses import dataclass

from runestone.db.models import User
from runestone.rag.index import GrammarIndex
from runestone.services.grammar_service import GrammarService
from runestone.services.memory_item_service import MemoryItemService
from runestone.services.vocabulary_service import VocabularyService


@dataclass
class AgentContext:
    """Context passed to agent tools at runtime."""

    user: User
    # we can't use DI of FastAPI here, so had to put the service to context
    vocabulary_service: VocabularyService
    memory_item_service: MemoryItemService
    # Lock to prevent concurrent database access from multiple tool calls
    db_lock: "asyncio.Lock"
    grammar_index: GrammarIndex | None = None
    grammar_service: GrammarService | None = None
