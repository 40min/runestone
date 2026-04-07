"""
Centralized configuration management for Runestone.

This module provides a single source of truth for all application settings,
loaded from environment variables using Pydantic BaseSettings.
"""

import os
from enum import Enum
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import AliasChoices, BaseModel, Field, model_validator
from pydantic_settings import BaseSettings


class ReasoningLevel(str, Enum):
    """Supported reasoning effort levels for chat models."""

    NONE = "none"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentLLMSettings(BaseModel):
    """Resolved LLM settings for a specific agent."""

    provider: Literal["openrouter", "openai"]
    model: str
    temperature: float
    reasoning_level: ReasoningLevel


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
    frontend_url: str

    # HuggingFace / sentence-transformers cache (must be writable in containers)
    hf_cache_dir: str = "state/hf-cache"
    # Telegram Configuration
    telegram_bot_token: str
    verbose: bool = False

    # Database Configuration
    database_url: str

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
    teacher_provider: Literal["openrouter", "openai"] = Field(
        default="openrouter",
        validation_alias=AliasChoices("TEACHER_PROVIDER", "CHAT_PROVIDER"),
    )
    teacher_model: str = Field(validation_alias=AliasChoices("TEACHER_MODEL", "CHAT_MODEL"))
    teacher_temperature: float = 1.0
    teacher_reasoning_level: ReasoningLevel = ReasoningLevel.NONE

    coordinator_provider: Optional[Literal["openrouter", "openai"]] = None
    coordinator_model: str
    coordinator_temperature: float = 0.0
    coordinator_reasoning_level: ReasoningLevel = ReasoningLevel.NONE

    word_keeper_provider: Optional[Literal["openrouter", "openai"]] = None
    word_keeper_model: Optional[str] = None
    word_keeper_temperature: float = 0.0
    word_keeper_reasoning_level: ReasoningLevel = ReasoningLevel.NONE

    news_agent_provider: Optional[Literal["openrouter", "openai"]] = None
    news_agent_model: Optional[str] = None
    news_agent_temperature: float = 0.0
    news_agent_reasoning_level: ReasoningLevel = ReasoningLevel.NONE

    memory_keeper_provider: Optional[Literal["openrouter", "openai"]] = None
    memory_keeper_model: Optional[str] = None
    memory_keeper_temperature: float = 0.0
    memory_keeper_reasoning_level: ReasoningLevel = ReasoningLevel.NONE

    agent_persona: str = "default"

    # Chat History Configuration
    chat_history_retention_days: int = 7

    # Image Upload Configuration
    chat_image_max_size_mb: int = 10

    # Voice Transcription Configuration
    voice_transcription_provider: Literal["openai", "elevenlabs"] = "openai"
    voice_transcription_model: str = "whisper-1"
    voice_enhancement_model: str = "gpt-4o-mini"
    voice_max_duration_seconds: int = 300
    voice_max_file_size_mb: int = 25

    # TTS (Text-to-Speech) Configuration
    tts_provider: Literal["openai", "elevenlabs"] = "openai"
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "onyx"

    # ElevenLabs Voice Configuration
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_tts_model: str = "eleven_multilingual_v2"
    elevenlabs_tts_voice_id: Optional[str] = None
    elevenlabs_tts_output_format: str = "mp3_44100_128"
    elevenlabs_tts_stability: float = 0.5
    elevenlabs_tts_similarity_boost: float = 0.75
    elevenlabs_tts_style: float = 0.0
    elevenlabs_tts_use_speaker_boost: bool = True

    @model_validator(mode="after")
    def _apply_agent_defaults(self) -> "Settings":
        if self.coordinator_provider is None:
            self.coordinator_provider = self.teacher_provider
        if self.word_keeper_provider is None:
            self.word_keeper_provider = self.teacher_provider
        if self.word_keeper_model is None:
            self.word_keeper_model = self.teacher_model
        if self.news_agent_provider is None:
            self.news_agent_provider = self.teacher_provider
        if self.news_agent_model is None:
            self.news_agent_model = self.teacher_model
        if self.memory_keeper_provider is None:
            self.memory_keeper_provider = self.teacher_provider
        if self.memory_keeper_model is None:
            self.memory_keeper_model = self.teacher_model
        return self

    def get_agent_llm_settings(
        self, agent_name: Literal["teacher", "coordinator", "word_keeper", "news_agent", "memory_keeper"]
    ) -> AgentLLMSettings:
        """Return resolved model settings for the requested agent."""
        if agent_name == "teacher":
            return AgentLLMSettings(
                provider=self.teacher_provider,
                model=self.teacher_model,
                temperature=self.teacher_temperature,
                reasoning_level=self.teacher_reasoning_level,
            )

        if agent_name == "coordinator":
            return AgentLLMSettings(
                provider=self.coordinator_provider,
                model=self.coordinator_model,
                temperature=self.coordinator_temperature,
                reasoning_level=self.coordinator_reasoning_level,
            )

        if agent_name == "word_keeper":
            return AgentLLMSettings(
                provider=self.word_keeper_provider,
                model=self.word_keeper_model,
                temperature=self.word_keeper_temperature,
                reasoning_level=self.word_keeper_reasoning_level,
            )

        if agent_name == "news_agent":
            return AgentLLMSettings(
                provider=self.news_agent_provider,
                model=self.news_agent_model,
                temperature=self.news_agent_temperature,
                reasoning_level=self.news_agent_reasoning_level,
            )

        if agent_name == "memory_keeper":
            return AgentLLMSettings(
                provider=self.memory_keeper_provider,
                model=self.memory_keeper_model,
                temperature=self.memory_keeper_temperature,
                reasoning_level=self.memory_keeper_reasoning_level,
            )

        raise ValueError(f"Unsupported agent name: {agent_name}")

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
