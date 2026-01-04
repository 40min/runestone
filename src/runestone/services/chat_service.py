"""
Service for managing chat interactions and history.
"""

import logging
from typing import List

from runestone.agent.schemas import ChatMessage as ChatMessageSchema
from runestone.agent.service import AgentService
from runestone.config import Settings
from runestone.db.chat_repository import ChatRepository
from runestone.db.models import ChatMessage

logger = logging.getLogger(__name__)


class ChatService:
    """Service to handle business logic of chat interactions."""

    def __init__(self, settings: Settings, repository: ChatRepository, agent_service: AgentService):
        """
        Initialize the chat service.

        Args:
            settings: Application settings
            repository: Chat repository for database operations
            agent_service: Agent service for LLM interactions
        """
        self.settings = settings
        self.repository = repository
        self.agent_service = agent_service

    async def process_message(self, user_id: int, message_text: str) -> str:
        """
        Process a user message: save, truncate, fetch context, generate response, save response.

        Args:
            user_id: ID of the user
            message_text: The user's message

        Returns:
            The assistant's response text
        """
        # 1. Save user message
        self.repository.add_message(user_id, "user", message_text)

        # 2. Truncate old messages
        self.repository.truncate_history(user_id, self.settings.chat_history_retention_days)

        # 3. Fetch context for agent
        # We fetch the most recent messages to provide context to the LLM
        context_models = self.repository.get_context_for_agent(user_id)

        # Convert models to schemas for the agent service
        context_schemas = [
            ChatMessageSchema(role=m.role, content=m.content, created_at=m.created_at) for m in context_models
        ]

        # 4. Generate assistant response
        # The last message in context_schemas is the one we just saved
        assistant_text = self.agent_service.generate_response(message_text, context_schemas[:-1])

        # 5. Save assistant message
        self.repository.add_message(user_id, "assistant", assistant_text)

        return assistant_text

    def get_history(self, user_id: int) -> List[ChatMessage]:
        """
        Get the full chat history for a user.

        Args:
            user_id: ID of the user

        Returns:
            List of ChatMessage models
        """
        return self.repository.get_raw_history(user_id)

    def clear_history(self, user_id: int):
        """
        Clear all chat history for a user.

        Args:
            user_id: ID of the user
        """
        self.repository.clear_all_history(user_id)
