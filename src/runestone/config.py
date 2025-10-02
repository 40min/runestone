"""
Centralized configuration management for Runestone.

This module provides a single source of truth for all application settings,
loaded from environment variables using Pydantic BaseSettings.
"""

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Provider Configuration
    llm_provider: str

    # OpenAI Configuration
    openai_api_key: str
    openai_model: str

    # Gemini Configuration
    gemini_api_key: str

    # Application Settings
    allowed_origins: str
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

    # Vocabulary Learning Configuration
    words_per_day: int = 5
    cooldown_days: int = 7

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# Load environment variables from .env file
load_dotenv()

# Global settings instance
settings = Settings()  # type: ignore
