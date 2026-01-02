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

    # Maximum number of messages to keep in history to avoid context window issues
    MAX_HISTORY_MESSAGES = 20

    def __init__(self, settings: Settings):
        """
        Initialize the agent service.

        Args:
            settings: Application settings containing chat configuration
        """
        self.settings = settings
        self.persona = load_persona(settings.agent_persona)

        # Initialize the LangChain chat model
        # Using ChatOpenAI which works with OpenRouter and other OpenAI-compatible APIs
        self.chat_model = ChatOpenAI(
            model=settings.chat_model,
            openai_api_key=(
                settings.openrouter_api_key if settings.chat_provider == "openrouter" else settings.openai_api_key
            ),
            openai_api_base="https://openrouter.ai/api/v1" if settings.chat_provider == "openrouter" else None,
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
            history: Previous conversation messages

        Returns:
            The assistant's response

        Raises:
            Exception: If the LLM call fails
        """
        # Truncate history if it's too long
        truncated_history = self._truncate_history(history)

        # Build the full message list
        system_prompt = self.persona["system_prompt"]
        messages = build_messages(system_prompt, truncated_history, message)

        # Convert to LangChain message format
        langchain_messages = self._convert_to_langchain_messages(messages)

        try:
            # Call the LLM
            response = self.chat_model.invoke(langchain_messages)
            return response.content
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

    def _truncate_history(self, history: list[ChatMessage]) -> list[ChatMessage]:
        """
        Truncate conversation history to avoid context window limits.

        Keeps only the most recent messages.

        Args:
            history: Full conversation history

        Returns:
            Truncated history
        """
        if len(history) <= self.MAX_HISTORY_MESSAGES:
            return history

        logger.info(f"Truncating history from {len(history)} to {self.MAX_HISTORY_MESSAGES} messages")
        return history[-self.MAX_HISTORY_MESSAGES :]

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
