"""
Dependency injection providers for Runestone.

This module contains reusable dependency injection functions that can be used
across different parts of the application (API, CLI, workers) to ensure
consistent object creation and configuration.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from runestone.agent.service import AgentService
from runestone.config import Settings, settings
from runestone.core.analyzer import ContentAnalyzer
from runestone.core.clients.base import BaseLLMClient
from runestone.core.ocr import OCRProcessor
from runestone.core.processor import RunestoneProcessor
from runestone.db.chat_repository import ChatRepository
from runestone.db.database import get_db
from runestone.db.memory_item_repository import MemoryItemRepository
from runestone.db.user_repository import UserRepository
from runestone.db.vocabulary_repository import VocabularyRepository
from runestone.rag.index import GrammarIndex
from runestone.services.chat_service import ChatService
from runestone.services.grammar_service import GrammarService
from runestone.services.memory_item_service import MemoryItemService
from runestone.services.tts_service import TTSService
from runestone.services.user_service import UserService
from runestone.services.vocabulary_service import VocabularyService
from runestone.services.voice_service import VoiceService


def get_settings() -> Settings:
    """
    Dependency injection for application settings.

    Returns:
        Settings: The global settings instance
    """
    return settings


def get_user_repository(db: Annotated[Session, Depends(get_db)]) -> UserRepository:
    """
    Dependency injection for user repository.

    Args:
        db: Database session from FastAPI dependency injection

    Returns:
        UserRepository: Repository instance with database session
    """
    return UserRepository(db)


def get_vocabulary_repository(db: Annotated[Session, Depends(get_db)]) -> VocabularyRepository:
    """
    Dependency injection for vocabulary repository.

    Args:
        db: Database session from FastAPI dependency injection

    Returns:
        VocabularyRepository: Repository instance with database session
    """
    return VocabularyRepository(db)


def get_chat_repository(db: Annotated[Session, Depends(get_db)]) -> ChatRepository:
    """
    Dependency injection for chat repository.

    Args:
        db: Database session from FastAPI dependency injection

    Returns:
        ChatRepository: Repository instance with database session
    """
    return ChatRepository(db)


def get_memory_item_repository(db: Annotated[Session, Depends(get_db)]) -> MemoryItemRepository:
    """
    Dependency injection for memory item repository.

    Args:
        db: Database session from FastAPI dependency injection

    Returns:
        MemoryItemRepository: Repository instance with database session
    """
    return MemoryItemRepository(db)


def get_user_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    vocab_repo: Annotated[VocabularyRepository, Depends(get_vocabulary_repository)],
) -> UserService:
    """
    Dependency injection for user service.

    Args:
        user_repo: UserRepository from dependency injection
        vocab_repo: VocabularyRepository from dependency injection

    Returns:
        UserService: Service instance with repository dependencies
    """
    return UserService(user_repo, vocab_repo)


def get_memory_item_service(
    repo: Annotated[MemoryItemRepository, Depends(get_memory_item_repository)],
) -> MemoryItemService:
    """
    Dependency injection for memory item service.

    Args:
        repo: MemoryItemRepository from dependency injection

    Returns:
        MemoryItemService: Service instance with repository dependency
    """
    return MemoryItemService(repo)


def get_llm_client(request: Request) -> BaseLLMClient:
    """
    Dependency injection for LLM client.

    Args:
        request: FastAPI request object

    Returns:
        BaseLLMClient: Cached LLM client instance
    """
    return request.app.state.llm_client


def get_ocr_llm_client(request: Request) -> BaseLLMClient:
    """
    Dependency injection for OCR-specific LLM client.

    Args:
        request: FastAPI request object

    Returns:
        BaseLLMClient: Cached OCR-specific LLM client instance
    """
    return request.app.state.ocr_llm_client


def get_vocabulary_service(
    repo: Annotated[VocabularyRepository, Depends(get_vocabulary_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
    llm_client: Annotated[BaseLLMClient, Depends(get_llm_client)],
) -> VocabularyService:
    """
    Dependency injection for vocabulary service.

    Args:
        repo: VocabularyRepository from dependency injection
        settings: Application settings from dependency injection
        llm_client: LLM client from dependency injection

    Returns:
        VocabularyService: Service instance with repository and settings dependencies
    """
    return VocabularyService(repo, settings, llm_client)


def get_ocr_processor(
    settings: Annotated[Settings, Depends(get_settings)],
    ocr_llm_client: Annotated[BaseLLMClient, Depends(get_ocr_llm_client)],
) -> OCRProcessor:
    """
    Dependency injection for OCR processor.

    Args:
        settings: Application settings from dependency injection
        ocr_llm_client: OCR-specific LLM client from dependency injection

    Returns:
        OCRProcessor: OCR processor instance
    """
    return OCRProcessor(settings, ocr_llm_client)


def get_content_analyzer(
    settings: Annotated[Settings, Depends(get_settings)],
    llm_client: Annotated[BaseLLMClient, Depends(get_llm_client)],
) -> ContentAnalyzer:
    """
    Dependency injection for content analyzer.

    Args:
        settings: Application settings from dependency injection
        llm_client: LLM client from dependency injection

    Returns:
        ContentAnalyzer: Content analyzer instance
    """
    return ContentAnalyzer(settings, llm_client)


def get_runestone_processor(
    settings: Annotated[Settings, Depends(get_settings)],
    ocr_processor: Annotated[OCRProcessor, Depends(get_ocr_processor)],
    content_analyzer: Annotated[ContentAnalyzer, Depends(get_content_analyzer)],
    vocabulary_service: Annotated[VocabularyService, Depends(get_vocabulary_service)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> RunestoneProcessor:
    """
    Dependency injection for Runestone processor.

    Args:
        settings: Application settings from dependency injection
        ocr_processor: OCR processor from dependency injection
        content_analyzer: Content analyzer from dependency injection
        vocabulary_service: Vocabulary service from dependency injection
        user_service: User service from dependency injection

    Returns:
        RunestoneProcessor: Runestone processor instance
    """
    return RunestoneProcessor(settings, ocr_processor, content_analyzer, vocabulary_service, user_service)


def get_grammar_service(request: Request) -> GrammarService:
    """
    Dependency injection for grammar service.

    Args:
        request: FastAPI request object

    Returns:
        GrammarService: Cached service instance for grammar operations
    """
    return request.app.state.grammar_service


def get_agent_service(request: Request) -> AgentService:
    """
    Dependency injection for agent service.

    Args:
        request: FastAPI request object

    Returns:
        AgentService: Cached service instance for chat agent operations
    """
    return request.app.state.agent_service


def get_tts_service(request: Request) -> TTSService:
    """
    Get TTS service singleton instance.

    Args:
        request: FastAPI request object

    Returns:
        TTSService: Cached singleton service instance for TTS operations
    """
    return request.app.state.tts_service


def get_grammar_index(request: Request) -> GrammarIndex:
    """
    Get grammar search index singleton instance.

    Args:
        request: FastAPI request object

    Returns:
        GrammarIndex: Cached singleton instance for grammar search operations
    """
    return request.app.state.grammar_index


def get_chat_service(
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[ChatRepository, Depends(get_chat_repository)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
    processor: Annotated[RunestoneProcessor, Depends(get_runestone_processor)],
    vocabulary_service: Annotated[VocabularyService, Depends(get_vocabulary_service)],
    tts_service: Annotated[TTSService, Depends(get_tts_service)],
    memory_item_service: Annotated[MemoryItemService, Depends(get_memory_item_service)],
) -> ChatService:
    """
    Get chat service instance.

    Args:
        settings: Application settings from dependency injection
        repo: ChatRepository from dependency injection
        user_service: UserService from dependency injection
        agent_service: AgentService from dependency injection
        processor: RunestoneProcessor from dependency injection
        vocabulary_service: VocabularyService from dependency injection
        tts_service: TTSService from dependency injection

    Returns:
        ChatService: Service instance for chat operations
    """
    return ChatService(
        settings, repo, user_service, agent_service, processor, vocabulary_service, tts_service, memory_item_service
    )


def get_voice_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> VoiceService:
    """
    Get voice service instance.

    Args:
        settings: Application settings from dependency injection

    Returns:
        VoiceService: Service instance for voice transcription operations
    """
    return VoiceService(settings)
