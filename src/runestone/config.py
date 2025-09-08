"""
Centralized configuration management for Runestone.

This module provides a single source of truth for all application settings,
loaded from environment variables using Pydantic BaseSettings.
"""

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Provider Configuration
    llm_provider: str = "openai"

    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    # Gemini Configuration
    gemini_api_key: Optional[str] = None

    # Application Settings
    verbose: bool = False
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3010,http://127.0.0.1:3010"

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
