"""Tests for configuration management."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings

from runestone.config import DEFAULT_GEMINI_SERVICE_LLM_MODEL, DEFAULT_SERVICE_LLM_MODEL, ReasoningLevel, Settings


class TestSettings:
    """Test the Settings class."""

    def test_settings_creation_with_env_vars(self):
        """Test that settings are created correctly with environment variables."""

        class TestSettings(BaseSettings):
            llm_provider: str
            openai_api_key: str
            llm_model_name: str
            verbose: bool = False
            allowed_origins: str
            database_url: str = "sqlite:///./state/runestone.db"
            state_file_path: str = "state/state.json"
            telegram_bot_token: str
            recall_start_hour: int = 9
            recall_end_hour: int = 22
            recall_interval_minutes: int = 60

            class Config:
                env_file_encoding = "utf-8"
                case_sensitive = False
                extra = "ignore"

        env_vars = {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "LLM_MODEL_NAME": "gpt-4o-mini",
            "VERBOSE": "true",
            "ALLOWED_ORIGINS": "http://localhost:3000",
            "DATABASE_URL": "sqlite:///./test.db",
            "STATE_FILE_PATH": "custom/state.json",
            "TELEGRAM_BOT_TOKEN": "test-token",
            "RECALL_START_HOUR": "8",
            "RECALL_END_HOUR": "23",
            "RECALL_INTERVAL_MINUTES": "30",
        }

        with patch.dict(os.environ, env_vars):
            test_settings = TestSettings()  # type: ignore

            assert test_settings.llm_provider == "openai"
            assert test_settings.openai_api_key == "test-key"
            assert test_settings.llm_model_name == "gpt-4o-mini"
            assert test_settings.verbose is True
            assert test_settings.allowed_origins == "http://localhost:3000"
            assert test_settings.database_url == "sqlite:///./test.db"
            assert test_settings.state_file_path == "custom/state.json"
            assert test_settings.telegram_bot_token == "test-token"
            assert test_settings.recall_start_hour == 8
            assert test_settings.recall_end_hour == 23
            assert test_settings.recall_interval_minutes == 30

    def test_settings_required_fields(self):
        """Test that settings raise ValidationError when required fields are missing."""

        class TestSettings(BaseSettings):
            llm_provider: str
            openai_api_key: str
            llm_model_name: str
            verbose: bool = False
            allowed_origins: str
            database_url: str = "sqlite:///./state/runestone.db"
            state_file_path: str = "state/state.json"
            telegram_bot_token: str
            recall_start_hour: int = 9
            recall_end_hour: int = 22
            recall_interval_minutes: int = 60

            class Config:
                env_file_encoding = "utf-8"
                case_sensitive = False
                extra = "ignore"

        minimal_env = {
            "ALLOWED_ORIGINS": "http://localhost:3000",
        }

        with patch.dict(os.environ, minimal_env, clear=True):
            with pytest.raises(ValidationError):
                TestSettings()

    def test_test_env_file_is_used(self):
        """Test that tests use the .env.test file instead of .env."""
        from runestone.config import settings

        # These should be the test values from .env.test, not from .env
        assert settings.llm_provider == "openai"
        assert settings.openai_api_key == "test_openai_api_key_for_testing_only"
        assert settings.allowed_origins == "http://localhost:5173,http://127.0.0.1:5173,http://frontend:3010"
        assert settings.telegram_bot_token == "test_telegram_bot_token_for_testing_only"

    def test_agent_reasoning_level_accepts_known_enum_values(self):
        """Test per-agent reasoning settings are validated via enum."""
        env_vars = {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "OPENROUTER_API_KEY": "test-openrouter-key",
            "ALLOWED_ORIGINS": "http://localhost:3000",
            "DATABASE_URL": "sqlite:///./test.db",
            "TELEGRAM_BOT_TOKEN": "test-token",
            "FRONTEND_URL": "http://localhost:5173",
            "JWT_SECRET_KEY": "secret",
            "TEACHER_MODEL": "teacher-model",
            "COORDINATOR_MODEL": "coordinator-model",
            "COORDINATOR_REASONING_LEVEL": "minimal",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            test_settings = Settings()

        assert test_settings.coordinator_reasoning_level == ReasoningLevel.MINIMAL

    def test_agent_reasoning_level_rejects_unknown_values(self):
        """Test invalid reasoning values fail validation."""
        env_vars = {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "OPENROUTER_API_KEY": "test-openrouter-key",
            "ALLOWED_ORIGINS": "http://localhost:3000",
            "DATABASE_URL": "sqlite:///./test.db",
            "TELEGRAM_BOT_TOKEN": "test-token",
            "FRONTEND_URL": "http://localhost:5173",
            "JWT_SECRET_KEY": "secret",
            "TEACHER_MODEL": "teacher-model",
            "COORDINATOR_MODEL": "coordinator-model",
            "TEACHER_REASONING_LEVEL": "turbo",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValidationError):
                Settings()

    def test_teacher_env_names_configure_teacher_model_settings(self):
        """Test TEACHER_* env names configure teacher model settings."""
        env_vars = {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "OPENROUTER_API_KEY": "test-openrouter-key",
            "ALLOWED_ORIGINS": "http://localhost:3000",
            "DATABASE_URL": "sqlite:///./test.db",
            "TELEGRAM_BOT_TOKEN": "test-token",
            "FRONTEND_URL": "http://localhost:5173",
            "JWT_SECRET_KEY": "secret",
            "TEACHER_PROVIDER": "openai",
            "TEACHER_MODEL": "teacher-env-model",
            "COORDINATOR_MODEL": "coordinator-model",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            test_settings = Settings()

        assert test_settings.teacher_provider == "openai"
        assert test_settings.teacher_model == "teacher-env-model"

    def test_service_llm_resolvers_use_default_fallbacks(self):
        """Service-side resolver helpers should centralize default provider/model selection."""
        test_settings = Settings.model_construct(
            llm_provider="openai",
            llm_model_name=None,
            openai_api_key="test-key",
            gemini_api_key="test-gemini-key",
            openrouter_api_key="test-openrouter-key",
            ocr_llm_provider=None,
            ocr_llm_model_name=None,
            allowed_origins="http://localhost:3000",
            database_url="sqlite:///./test.db",
            telegram_bot_token="test-token",
            frontend_url="http://localhost:5173",
            jwt_secret_key="secret",
            teacher_provider="openrouter",
            teacher_model="teacher-model",
            coordinator_model="coordinator-model",
        )

        assert test_settings.resolve_service_llm_provider() == "openai"
        assert test_settings.resolve_service_llm_model() == DEFAULT_SERVICE_LLM_MODEL
        assert test_settings.resolve_ocr_llm_provider() == "openai"
        assert test_settings.resolve_ocr_llm_model() == DEFAULT_SERVICE_LLM_MODEL

    def test_service_llm_resolver_uses_gemini_default_model(self):
        """Gemini provider should use the Gemini default model when none is configured."""
        test_settings = Settings.model_construct(
            llm_provider="gemini",
            llm_model_name=None,
            openai_api_key="test-key",
            gemini_api_key="test-gemini-key",
            openrouter_api_key="test-openrouter-key",
            ocr_llm_provider=None,
            ocr_llm_model_name=None,
            allowed_origins="http://localhost:3000",
            database_url="sqlite:///./test.db",
            telegram_bot_token="test-token",
            frontend_url="http://localhost:5173",
            jwt_secret_key="secret",
            teacher_provider="gemini",
            teacher_model="teacher-model",
            coordinator_model="coordinator-model",
        )

        assert test_settings.resolve_service_llm_provider() == "gemini"
        assert test_settings.resolve_service_llm_model() == DEFAULT_GEMINI_SERVICE_LLM_MODEL

    def test_gemini_only_settings_do_not_require_openai_api_key(self):
        """Gemini-first configs should validate without unrelated OpenAI credentials."""
        test_settings = Settings(
            llm_provider="gemini",
            openai_api_key=None,
            gemini_api_key="test-gemini-key",
            allowed_origins="http://localhost:3000",
            database_url="sqlite:///./test.db",
            telegram_bot_token="test-token",
            frontend_url="http://localhost:5173",
            jwt_secret_key="secret",
            teacher_provider="gemini",
            teacher_model="teacher-model",
            coordinator_model="coordinator-model",
        )

        assert test_settings.openai_api_key is None
        assert test_settings.resolve_service_llm_provider() == "gemini"

    def test_ocr_service_llm_resolvers_prefer_explicit_overrides(self):
        """OCR resolver helpers should prefer OCR-specific provider/model overrides."""
        test_settings = Settings.model_construct(
            llm_provider="openai",
            llm_model_name="gpt-5-mini",
            openai_api_key="test-key",
            gemini_api_key="test-gemini-key",
            openrouter_api_key="test-openrouter-key",
            ocr_llm_provider="openrouter",
            ocr_llm_model_name="anthropic/claude-3.5-sonnet",
            allowed_origins="http://localhost:3000",
            database_url="sqlite:///./test.db",
            telegram_bot_token="test-token",
            frontend_url="http://localhost:5173",
            jwt_secret_key="secret",
            teacher_provider="openrouter",
            teacher_model="teacher-model",
            coordinator_model="coordinator-model",
        )

        assert test_settings.resolve_ocr_llm_provider() == "openrouter"
        assert test_settings.resolve_ocr_llm_model() == "anthropic/claude-3.5-sonnet"

    def test_gemini_service_provider_can_keep_ocr_on_openrouter(self):
        """Gemini service flows should coexist with an explicit OpenRouter OCR override."""
        test_settings = Settings.model_construct(
            llm_provider="gemini",
            llm_model_name="gemini-2.5-flash",
            openai_api_key="test-key",
            gemini_api_key="test-gemini-key",
            openrouter_api_key="test-openrouter-key",
            ocr_llm_provider="openrouter",
            ocr_llm_model_name="amazon/nova-lite-v1",
            allowed_origins="http://localhost:3000",
            database_url="sqlite:///./test.db",
            telegram_bot_token="test-token",
            frontend_url="http://localhost:5173",
            jwt_secret_key="secret",
            teacher_provider="gemini",
            teacher_model="teacher-model",
            coordinator_model="coordinator-model",
        )

        assert test_settings.resolve_service_llm_provider() == "gemini"
        assert test_settings.resolve_service_llm_model() == "gemini-2.5-flash"
        assert test_settings.resolve_ocr_llm_provider() == "openrouter"
        assert test_settings.resolve_ocr_llm_model() == "amazon/nova-lite-v1"

    def test_news_agent_defaults_to_teacher_model_settings(self):
        """Test news_agent inherits teacher provider/model when not configured explicitly."""
        test_settings = Settings.model_construct(
            llm_provider="openai",
            openai_api_key="test-key",
            gemini_api_key="test-gemini-key",
            openrouter_api_key="test-openrouter-key",
            allowed_origins="http://localhost:3000",
            database_url="sqlite:///./test.db",
            telegram_bot_token="test-token",
            frontend_url="http://localhost:5173",
            jwt_secret_key="secret",
            teacher_provider="openrouter",
            teacher_model="teacher-model",
            coordinator_model="coordinator-model",
            news_agent_provider=None,
            news_agent_model=None,
        )
        test_settings = test_settings._apply_agent_defaults()

        assert test_settings.news_agent_provider == "openrouter"
        assert test_settings.news_agent_model == "teacher-model"

    def test_memory_maintainer_defaults_to_memory_keeper_settings(self):
        """Test memory_maintainer inherits memory_keeper settings when not configured explicitly."""
        test_settings = Settings.model_construct(
            llm_provider="openai",
            openai_api_key="test-key",
            gemini_api_key="test-gemini-key",
            openrouter_api_key="test-openrouter-key",
            allowed_origins="http://localhost:3000",
            database_url="sqlite:///./test.db",
            telegram_bot_token="test-token",
            frontend_url="http://localhost:5173",
            jwt_secret_key="secret",
            teacher_provider="openrouter",
            teacher_model="teacher-model",
            coordinator_model="coordinator-model",
            memory_keeper_provider="gemini",
            memory_keeper_model="gemini-3.1-flash-lite-preview",
            memory_keeper_temperature=0.3,
            memory_keeper_reasoning_level=ReasoningLevel.MINIMAL,
            memory_maintainer_provider=None,
            memory_maintainer_model=None,
        )
        test_settings = test_settings._apply_agent_defaults()

        assert test_settings.memory_maintainer_provider == "gemini"
        assert test_settings.memory_maintainer_model == "gemini-3.1-flash-lite-preview"
        assert test_settings.memory_maintainer_temperature == 0.3
        assert test_settings.memory_maintainer_reasoning_level == ReasoningLevel.MINIMAL

    def test_memory_mastered_cleanup_days_defaults_to_three(self):
        """Test mastered memory cleanup defaults to a tighter retention window."""
        test_settings = Settings.model_construct(
            llm_provider="openai",
            openai_api_key="test-key",
            gemini_api_key="test-gemini-key",
            openrouter_api_key="test-openrouter-key",
            allowed_origins="http://localhost:3000",
            database_url="sqlite:///./test.db",
            telegram_bot_token="test-token",
            frontend_url="http://localhost:5173",
            jwt_secret_key="secret",
            teacher_provider="openrouter",
            teacher_model="teacher-model",
            coordinator_model="coordinator-model",
        )

        assert test_settings.memory_mastered_cleanup_days == 3

    def test_voice_settings_defaults_include_elevenlabs_configuration(self):
        """Test new voice provider settings keep OpenAI defaults while exposing ElevenLabs config."""
        env_vars = {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "OPENROUTER_API_KEY": "test-openrouter-key",
            "ALLOWED_ORIGINS": "http://localhost:3000",
            "DATABASE_URL": "sqlite:///./test.db",
            "TELEGRAM_BOT_TOKEN": "test-token",
            "FRONTEND_URL": "http://localhost:5173",
            "JWT_SECRET_KEY": "secret",
            "TEACHER_MODEL": "teacher-model",
            "COORDINATOR_MODEL": "coordinator-model",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            test_settings = Settings()

        assert test_settings.voice_transcription_provider == "openai"
        assert test_settings.tts_provider == "openai"
        assert test_settings.elevenlabs_tts_model == "eleven_multilingual_v2"
        assert test_settings.elevenlabs_tts_output_format == "mp3_44100_128"
