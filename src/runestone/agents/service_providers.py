"""Async service providers for agent runtime paths that need isolated DB sessions."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from runestone.config import settings
from runestone.db.agent_side_effect_repository import AgentSideEffectRepository
from runestone.db.chat_session_learning_focus_repository import ChatSessionLearningFocusRepository
from runestone.db.database import provide_db_session
from runestone.db.memory_item_repository import MemoryItemRepository
from runestone.db.user_repository import UserRepository
from runestone.db.vocabulary_repository import VocabularyRepository
from runestone.services.agent_side_effect_service import AgentSideEffectService
from runestone.services.chat_session_learning_focus_service import ChatSessionLearningFocusService
from runestone.services.memory_item_service import MemoryItemService
from runestone.services.user_service import UserService
from runestone.services.vocabulary_service import VocabularyService


def _create_llm_model():
    """Get non-agent chat model based on settings for service-layer use."""
    from runestone.core.service_llm import build_service_llm_model

    return build_service_llm_model(settings)


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
async def provide_chat_session_learning_focus_service() -> AsyncIterator[ChatSessionLearningFocusService]:
    """Context manager for chat-session learning-focus service in agent runtime paths."""
    async with provide_db_session() as session:
        memory_repo = MemoryItemRepository(session)
        focus_repo = ChatSessionLearningFocusRepository(session)
        memory_item_service = MemoryItemService(memory_repo)
        service = ChatSessionLearningFocusService(focus_repo, memory_item_service)
        yield service


@asynccontextmanager
async def provide_vocabulary_service() -> AsyncIterator[VocabularyService]:
    """
    Context manager for creating a VocabularyService with its own database session.

    This provider is intended for use in LangGraph agent tools where each tool
    call needs its own isolated session for concurrent execution.

    Usage:
        async with provide_vocabulary_service() as service:
            await service.insert_or_prioritize_words(...)

    Yields:
        VocabularyService: A service instance with its own database session
    """
    current_settings = settings
    async with provide_db_session() as session:
        repo = VocabularyRepository(session)
        llm_model = _create_llm_model()
        service = VocabularyService(repo, current_settings, llm_model)
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


@asynccontextmanager
async def provide_user_service() -> AsyncIterator[UserService]:
    """
    Context manager for user writes in agent/background runtime paths.

    Agent-side tasks that need to persist derived user state should go through
    the user service boundary rather than reaching into ORM sessions directly.
    """
    async with provide_db_session() as session:
        user_repo = UserRepository(session)
        service = UserService(user_repo)
        yield service
