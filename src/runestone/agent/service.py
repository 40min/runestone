"""
Service layer for the chat agent.

This module contains the AgentService class that handles chat interactions
using LangChain and LLM providers.
"""

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from runestone.agent.prompts import build_messages, load_persona
from runestone.agent.schemas import ChatMessage
from runestone.config import Settings

logger = logging.getLogger(__name__)


class AgentService:
    """Service for managing chat agent interactions."""

    def __init__(self, settings: Settings):
        """
        Initialize the agent service.

        Args:
            settings: Application settings containing chat configuration
        """
        self.settings = settings
        self.persona = load_persona(settings.agent_persona)

        # Initialize the LangChain chat model
        # Determine API key and base URL based on provider
        if settings.chat_provider == "openrouter":
            api_key = settings.openrouter_api_key
            api_base = "https://openrouter.ai/api/v1"
        elif settings.chat_provider == "openai":
            api_key = settings.openai_api_key
            api_base = None
        else:
            raise ValueError(f"Unsupported chat provider: {settings.chat_provider}")

        if not api_key:
            raise ValueError(f"API key for {settings.chat_provider} is not configured")

        # Using ChatOpenAI which works with OpenRouter and other OpenAI-compatible APIs
        self.chat_model = ChatOpenAI(
            model=settings.chat_model,
            openai_api_key=api_key,
            openai_api_base=api_base,
            temperature=0.7,
        )

        logger.info(
            f"Initialized AgentService with provider={settings.chat_provider}, "
            f"model={settings.chat_model}, persona={settings.agent_persona}"
        )

    def generate_response(self, message: str, history: list[ChatMessage]) -> str:
        """
        Generate a response to a user message.

        Args:
            message: The user's message
            history: Previous conversation messages (provided by backend)

        Returns:
            The assistant's response

        Raises:
            Exception: If the LLM call fails
        """
        # Build the full message list
        system_prompt = self.persona["system_prompt"]
        messages = build_messages(system_prompt, history, message)

        # Convert to LangChain message format
        langchain_messages = self._convert_to_langchain_messages(messages)

        try:
            # Call the LLM
            response = self.chat_model.invoke(langchain_messages)
            return response.content
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

    def _convert_to_langchain_messages(self, messages: list[dict]) -> list:
        """
        Convert message dictionaries to LangChain message objects.

        Args:
            messages: list of message dictionaries with 'role' and 'content'

        Returns:
            list of LangChain message objects
        """
        langchain_messages = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))

        return langchain_messages
