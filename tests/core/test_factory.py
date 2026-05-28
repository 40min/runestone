"""Tests for the non-agent LangChain model builder."""

from unittest.mock import Mock, patch

import pytest
from pydantic import SecretStr

from runestone.config import DEFAULT_GEMINI_SERVICE_LLM_MODEL, DEFAULT_SERVICE_LLM_MODEL, Settings
from runestone.core.exceptions import APIKeyError
from runestone.core.service_llm import (
    OPENAI_SERVICE_LLM_MAX_RETRIES,
    SERVICE_LLM_TIMEOUT_SECONDS,
    build_service_llm_model,
    get_available_service_llm_providers,
)


class TestServiceLLMBuilder:
    """Test cases for service-side LangChain model construction."""

    def test_get_available_providers(self):
        """Supported non-agent providers should match the legacy surface."""
        assert get_available_service_llm_providers() == ["openai", "openrouter", "gemini"]

    @patch("runestone.core.service_llm.ChatOpenAI")
    def test_build_service_llm_model_openai(self, mock_chat_openai):
        """OpenAI builder should use the configured key, model, and resilience settings."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openai"
        mock_settings.llm_model_name = "gpt-4o-mini"
        mock_settings.resolve_service_llm_provider.return_value = "openai"
        mock_settings.resolve_service_llm_model.return_value = "gpt-4o-mini"
        mock_settings.resolve_openrouter_disallowed_providers.return_value = []
        mock_settings.openai_api_key = "test-openai-key"

        build_service_llm_model(mock_settings)

        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["api_key"] == SecretStr("test-openai-key")
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["timeout"] == SERVICE_LLM_TIMEOUT_SECONDS
        assert call_kwargs["max_retries"] == OPENAI_SERVICE_LLM_MAX_RETRIES
        assert "base_url" not in call_kwargs

    @patch("runestone.core.service_llm.ChatOpenAI")
    def test_build_service_llm_model_uses_shared_default_model(self, mock_chat_openai):
        """OpenAI builder should fall back to the shared non-agent default model."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openai"
        mock_settings.llm_model_name = None
        mock_settings.resolve_service_llm_provider.return_value = "openai"
        mock_settings.resolve_service_llm_model.return_value = DEFAULT_SERVICE_LLM_MODEL
        mock_settings.resolve_openrouter_disallowed_providers.return_value = []
        mock_settings.openai_api_key = "test-openai-key"

        build_service_llm_model(mock_settings)

        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["model"] == DEFAULT_SERVICE_LLM_MODEL

    @patch("runestone.core.service_llm.ChatOpenAI")
    def test_build_service_llm_model_openrouter(self, mock_chat_openai):
        """OpenRouter builder should preserve base URL, attribution headers, and timeout."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openrouter"
        mock_settings.llm_model_name = "anthropic/claude-3.5-sonnet"
        mock_settings.resolve_service_llm_provider.return_value = "openrouter"
        mock_settings.resolve_service_llm_model.return_value = "anthropic/claude-3.5-sonnet"
        mock_settings.resolve_openrouter_disallowed_providers.return_value = []
        mock_settings.openrouter_api_key = "test-openrouter-key"

        build_service_llm_model(mock_settings)

        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["model"] == "anthropic/claude-3.5-sonnet"
        assert call_kwargs["api_key"] == SecretStr("test-openrouter-key")
        assert call_kwargs["base_url"] == "https://openrouter.ai/api/v1"
        assert call_kwargs["default_headers"]["HTTP-Referer"] == "https://runestone.app"
        assert call_kwargs["default_headers"]["X-Title"] == "Runestone"
        assert call_kwargs["timeout"] == SERVICE_LLM_TIMEOUT_SECONDS
        assert call_kwargs["extra_body"] is None
        assert "max_retries" not in call_kwargs

    @patch("runestone.core.service_llm.ChatOpenAI")
    def test_build_service_llm_model_openrouter_adds_provider_blacklist(self, mock_chat_openai):
        """OpenRouter builder should pass ignored providers when configured."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openrouter"
        mock_settings.llm_model_name = "anthropic/claude-3.5-sonnet"
        mock_settings.resolve_service_llm_provider.return_value = "openrouter"
        mock_settings.resolve_service_llm_model.return_value = "anthropic/claude-3.5-sonnet"
        mock_settings.resolve_openrouter_disallowed_providers.return_value = ["bad-provider"]
        mock_settings.openrouter_api_key = "test-openrouter-key"

        build_service_llm_model(mock_settings)

        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["extra_body"] == {"provider": {"ignore": ["bad-provider"]}}

    @patch("runestone.core.service_llm.ChatOpenAI")
    def test_build_service_llm_model_respects_overrides(self, mock_chat_openai):
        """Provider and model overrides should win over default settings."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openai"
        mock_settings.llm_model_name = "gpt-4o-mini"
        mock_settings.resolve_service_llm_provider.return_value = "openai"
        mock_settings.resolve_service_llm_model.return_value = "gpt-4o-mini"
        mock_settings.resolve_openrouter_disallowed_providers.return_value = []
        mock_settings.openai_api_key = "unused-openai-key"
        mock_settings.openrouter_api_key = "test-openrouter-key"

        build_service_llm_model(
            mock_settings,
            provider="openrouter",
            model_name="google/gemini-2.5-flash",
            temperature=0.0,
        )

        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["model"] == "google/gemini-2.5-flash"
        assert call_kwargs["api_key"] == SecretStr("test-openrouter-key")
        assert call_kwargs["temperature"] == 0.0
        assert call_kwargs["base_url"] == "https://openrouter.ai/api/v1"
        assert call_kwargs["timeout"] == SERVICE_LLM_TIMEOUT_SECONDS

    @patch("runestone.core.service_llm.ChatGoogleGenerativeAI")
    def test_build_service_llm_model_gemini(self, mock_chat_gemini):
        """Gemini builder should use the configured key, model, and timeout."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "gemini"
        mock_settings.llm_model_name = "gemini-2.5-flash"
        mock_settings.resolve_service_llm_provider.return_value = "gemini"
        mock_settings.resolve_service_llm_model.return_value = "gemini-2.5-flash"
        mock_settings.resolve_openrouter_disallowed_providers.return_value = []
        mock_settings.gemini_api_key = "test-gemini-key"

        build_service_llm_model(mock_settings)

        call_kwargs = mock_chat_gemini.call_args[1]
        assert call_kwargs["model"] == "gemini-2.5-flash"
        assert call_kwargs["api_key"] == SecretStr("test-gemini-key")
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["request_timeout"] == SERVICE_LLM_TIMEOUT_SECONDS

    @patch("runestone.core.service_llm.ChatGoogleGenerativeAI")
    def test_build_service_llm_model_gemini_uses_provider_default_model(self, mock_chat_gemini):
        """Gemini builder should fall back to the Gemini default model."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "gemini"
        mock_settings.llm_model_name = None
        mock_settings.resolve_service_llm_provider.return_value = "gemini"
        mock_settings.resolve_service_llm_model.return_value = DEFAULT_GEMINI_SERVICE_LLM_MODEL
        mock_settings.resolve_openrouter_disallowed_providers.return_value = []
        mock_settings.gemini_api_key = "test-gemini-key"

        build_service_llm_model(mock_settings)

        call_kwargs = mock_chat_gemini.call_args[1]
        assert call_kwargs["model"] == DEFAULT_GEMINI_SERVICE_LLM_MODEL

    def test_build_service_llm_model_missing_openai_key(self):
        """Missing OpenAI configuration should raise a helpful error."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openai"
        mock_settings.llm_model_name = "gpt-4o-mini"
        mock_settings.resolve_service_llm_provider.return_value = "openai"
        mock_settings.resolve_service_llm_model.return_value = "gpt-4o-mini"
        mock_settings.resolve_openrouter_disallowed_providers.return_value = []
        mock_settings.openai_api_key = ""

        with pytest.raises(APIKeyError, match="OpenAI API key is required"):
            build_service_llm_model(mock_settings)

    def test_build_service_llm_model_missing_openrouter_key(self):
        """Missing OpenRouter configuration should raise a helpful error."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openrouter"
        mock_settings.llm_model_name = "anthropic/claude-3.5-sonnet"
        mock_settings.resolve_service_llm_provider.return_value = "openrouter"
        mock_settings.resolve_service_llm_model.return_value = "anthropic/claude-3.5-sonnet"
        mock_settings.resolve_openrouter_disallowed_providers.return_value = []
        mock_settings.openrouter_api_key = ""

        with pytest.raises(APIKeyError, match="OpenRouter API key is required"):
            build_service_llm_model(mock_settings)

    def test_build_service_llm_model_missing_gemini_key(self):
        """Missing Gemini configuration should raise a helpful error."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "gemini"
        mock_settings.llm_model_name = "gemini-2.5-flash"
        mock_settings.resolve_service_llm_provider.return_value = "gemini"
        mock_settings.resolve_service_llm_model.return_value = "gemini-2.5-flash"
        mock_settings.resolve_openrouter_disallowed_providers.return_value = []
        mock_settings.gemini_api_key = ""

        with pytest.raises(APIKeyError, match="Gemini API key is required"):
            build_service_llm_model(mock_settings)

    def test_build_service_llm_model_unsupported_provider(self):
        """Unsupported providers should fail fast."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "unsupported"
        mock_settings.llm_model_name = "test-model"
        mock_settings.resolve_service_llm_provider.return_value = "unsupported"
        mock_settings.resolve_service_llm_model.return_value = "test-model"
        mock_settings.resolve_openrouter_disallowed_providers.return_value = []

        with pytest.raises(ValueError, match="Unsupported LLM provider: unsupported"):
            build_service_llm_model(mock_settings)
