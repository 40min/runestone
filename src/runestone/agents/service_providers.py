"""Async service providers for agent runtime paths that need isolated DB sessions."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from runestone.config import settings
from runestone.db.agent_side_effect_repository import AgentSideEffectRepository
from runestone.db.database import provide_db_session
from runestone.db.memory_item_repository import MemoryItemRepository
from runestone.db.vocabulary_repository import VocabularyRepository
from runestone.services.agent_side_effect_service import AgentSideEffectService
from runestone.services.memory_item_service import MemoryItemService
from runestone.services.vocabulary_service import VocabularyService


def _create_llm_client():
    """Get LLM client based on settings (for use in non-request contexts)."""
    from runestone.core.clients.factory import create_llm_client

    return create_llm_client(settings)


@asynccontextmanager
async def provide_memory_item_service() -> AsyncIterator[MemoryItemService]:
    """
    Context manager for creating a MemoryItemService with its own database session.

    This provider is intended for use in LangGraph agent tools where each tool
    call needs its own isolated session for concurrent execution.

    Usage:
        async with provide_memory_item_service() as service:
            await service.upsert_memory_item(...)

    Yields:
        MemoryItemService: A service instance with its own database session
    """
    async with provide_db_session() as session:
        repo = MemoryItemRepository(session)
        service = MemoryItemService(repo)
        yield service


@asynccontextmanager
async def provide_vocabulary_service() -> AsyncIterator[VocabularyService]:
    """
    Context manager for creating a VocabularyService with its own database session.

    This provider is intended for use in LangGraph agent tools where each tool
    call needs its own isolated session for concurrent execution.

    Usage:
        async with provide_vocabulary_service() as service:
            await service.upsert_priority_word(...)

    Yields:
        VocabularyService: A service instance with its own database session
    """
    current_settings = settings
    async with provide_db_session() as session:
        repo = VocabularyRepository(session)
        llm_client = _create_llm_client()
        service = VocabularyService(repo, current_settings, llm_client)
        yield service


@asynccontextmanager
async def provide_agent_side_effect_service() -> AsyncIterator[AgentSideEffectService]:
    """
    Context manager for side-effect writes in background agent tasks.

    Background tasks run outside the request lifecycle and must use a dedicated
    database session so coordinator status updates do not contend with request
    message persistence on a shared asyncpg connection.
    """
    async with provide_db_session() as session:
        repo = AgentSideEffectRepository(session)
        service = AgentSideEffectService(repo)
        yield service
