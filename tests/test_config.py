"""Tests for configuration management."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings


class TestSettings:
    """Test the Settings class."""

    def test_settings_creation_with_env_vars(self):
        """Test that settings are created correctly with environment variables."""

        class TestSettings(BaseSettings):
            llm_provider: str
            openai_api_key: str
            openai_model: str
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
            "OPENAI_MODEL": "gpt-4o-mini",
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
            assert test_settings.openai_model == "gpt-4o-mini"
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
            openai_model: str
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
