"""
Centralized configuration management for Runestone.

This module provides a single source of truth for all application settings,
loaded from environment variables using Pydantic BaseSettings.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Provider Configuration
    llm_provider: str
    llm_model_name: Optional[str] = None

    # OpenAI Configuration
    openai_api_key: str

    # OpenRouter Configuration
    openrouter_api_key: Optional[str] = None
    ocr_llm_provider: Optional[str] = None
    ocr_llm_model_name: Optional[str] = None

    # Application Settings
    allowed_origins: str
    cheatsheets_dir: str = "cheatsheets"
    # Telegram Configuration
    telegram_bot_token: str
    verbose: bool = False

    # Database Configuration
    database_url: str = "sqlite:///./state/runestone.db"

    # State Management Configuration
    state_file_path: str = "state/state.json"

    # Recall Configuration
    recall_start_hour: int = 9
    recall_end_hour: int = 22  # 10 PM
    recall_interval_minutes: int = 60

    # JWT Configuration
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_days: int = 7
    min_password_length: int = 6

    # Vocabulary Learning Configuration
    words_per_day: int = 5
    cooldown_days: int = 7

    # Chat Agent Configuration
    chat_provider: str = "openrouter"
    chat_model: str = "x-ai/grok-2-1212"
    agent_persona: str = "default"

    # Chat History Configuration
    chat_history_retention_days: int = 7

    # Image Upload Configuration
    chat_image_max_size_mb: int = 10

    # Voice Transcription Configuration
    voice_transcription_model: str = "whisper-1"
    voice_enhancement_model: str = "gpt-4o-mini"
    voice_max_duration_seconds: int = 300
    voice_max_file_size_mb: int = 25

    class Config:
        """Pydantic configuration."""

        env_file = os.getenv("ENV_FILE", ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# Load environment variables from the specified env file
load_dotenv(dotenv_path=os.getenv("ENV_FILE", ".env"))

# Global settings instance
settings = Settings()  # type: ignore
