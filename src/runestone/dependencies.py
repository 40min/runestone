"""
Dependency injection providers for Runestone.

This module contains reusable dependency injection functions that can be used
across different parts of the application (API, CLI, workers) to ensure
consistent object creation and configuration.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from runestone.agent.service import AgentService
from runestone.config import Settings, settings
from runestone.core.analyzer import ContentAnalyzer
from runestone.core.clients.base import BaseLLMClient
from runestone.core.clients.factory import create_llm_client
from runestone.core.ocr import OCRProcessor
from runestone.core.processor import RunestoneProcessor
from runestone.db.chat_repository import ChatRepository
from runestone.db.database import get_db
from runestone.db.user_repository import UserRepository
from runestone.db.vocabulary_repository import VocabularyRepository
from runestone.services.chat_service import ChatService
from runestone.services.grammar_service import GrammarService
from runestone.services.user_service import UserService
from runestone.services.vocabulary_service import VocabularyService


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


def get_llm_client(settings: Annotated[Settings, Depends(get_settings)]) -> BaseLLMClient:
    """
    Dependency injection for LLM client.

    Args:
        settings: Application settings from dependency injection

    Returns:
        BaseLLMClient: LLM client instance
    """
    return create_llm_client(settings=settings)


def get_ocr_llm_client(
    settings: Annotated[Settings, Depends(get_settings)],
    llm_client: Annotated[BaseLLMClient, Depends(get_llm_client)],
) -> BaseLLMClient:
    """
    Dependency injection for OCR-specific LLM client.

    This function implements a fallback strategy:
    - If ocr_llm_provider is configured, creates a dedicated OCR client
    - Otherwise, returns the main LLM client (reuse for OCR)

    Args:
        settings: Application settings from dependency injection
        llm_client: Main LLM client from dependency injection (used as fallback)

    Returns:
        BaseLLMClient: OCR-specific LLM client instance or main client
    """
    if settings.ocr_llm_provider:
        # Create dedicated OCR client with OCR-specific settings
        return create_llm_client(
            settings=settings,
            provider=settings.ocr_llm_provider,
            model_name=settings.ocr_llm_model_name,
        )
    # Fall back to main client if no OCR-specific provider is configured
    return llm_client


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


def get_grammar_service(settings: Annotated[Settings, Depends(get_settings)]) -> GrammarService:
    """
    Dependency injection for grammar service.

    Args:
        settings: Application settings from dependency injection

    Returns:
        GrammarService: Service instance for grammar operations
    """
    return GrammarService(settings.cheatsheets_dir)


def get_agent_service(
    settings: Annotated[Settings, Depends(get_settings)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> AgentService:
    """
    Dependency injection for agent service.

    Args:
        settings: Application settings from dependency injection
        user_service: UserService from dependency injection

    Returns:
        AgentService: Service instance for chat agent operations
    """
    return AgentService(settings, user_service)


def get_chat_service(
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[ChatRepository, Depends(get_chat_repository)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ChatService:
    """
    Dependency injection for chat service.

    Args:
        settings: Application settings from dependency injection
        repo: ChatRepository from dependency injection
        user_service: UserService from dependency injection
        agent_service: AgentService from dependency injection

    Returns:
        ChatService: Service instance for chat operations
    """
    return ChatService(settings, repo, user_service, agent_service)
