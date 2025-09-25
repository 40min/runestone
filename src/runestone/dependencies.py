"""
Dependency injection providers for Runestone.

This module contains reusable dependency injection functions that can be used
across different parts of the application (API, CLI, workers) to ensure
consistent object creation and configuration.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from runestone.config import Settings, settings
from runestone.db.database import get_db
from runestone.db.repository import VocabularyRepository
from runestone.services.vocabulary_service import VocabularyService


def get_settings() -> Settings:
    """
    Dependency injection for application settings.

    Returns:
        Settings: The global settings instance
    """
    return settings


def get_vocabulary_repository(db: Annotated[Session, Depends(get_db)]) -> VocabularyRepository:
    """
    Dependency injection for vocabulary repository.

    Args:
        db: Database session from FastAPI dependency injection

    Returns:
        VocabularyRepository: Repository instance with database session
    """
    return VocabularyRepository(db)


def get_vocabulary_service(
    repo: Annotated[VocabularyRepository, Depends(get_vocabulary_repository)],
) -> VocabularyService:
    """
    Dependency injection for vocabulary service.

    Args:
        repo: VocabularyRepository from dependency injection

    Returns:
        VocabularyService: Service instance with repository dependency
    """
    return VocabularyService(repo)
