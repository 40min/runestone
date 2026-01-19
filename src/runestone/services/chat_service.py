"""
Service for managing chat interactions and history.
"""

import logging
from typing import List

from runestone.agent.schemas import ChatMessage as ChatMessageSchema
from runestone.agent.service import AgentService
from runestone.config import Settings
from runestone.core.exceptions import RunestoneError
from runestone.core.processor import RunestoneProcessor
from runestone.db.chat_repository import ChatRepository
from runestone.db.models import ChatMessage
from runestone.services.user_service import UserService

logger = logging.getLogger(__name__)


class ChatService:
    """Service to handle business logic of chat interactions."""

    def __init__(
        self,
        settings: Settings,
        repository: ChatRepository,
        user_service: UserService,
        agent_service: AgentService,
        processor: RunestoneProcessor,
    ):
        """
        Initialize the chat service.

        Args:
            settings: Application settings
            repository: Chat repository for database operations
            user_service: User service for user and memory operations
            agent_service: Agent service for LLM interactions
            processor: Runestone processor for OCR operations
        """
        self.settings = settings
        self.repository = repository
        self.user_service = user_service
        self.agent_service = agent_service
        self.processor = processor

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
        context_models = self.repository.get_context_for_agent(user_id)

        # Convert models to schemas for the agent service
        # Note: context_models includes the message we just saved at the end
        history = [
            ChatMessageSchema(id=m.id, role=m.role, content=m.content, created_at=m.created_at) for m in context_models
        ]

        # 4. Get user and build memory context
        user = self.user_service.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        memory = self.user_service.get_user_memory(user)

        # 5. Generate response using the ReAct agent
        # The agent handles tool execution automatically
        assistant_text = await self.agent_service.generate_response(
            message=message_text,
            history=history[:-1],  # Exclude current message (it's passed separately)
            user=user,
            user_service=self.user_service,
            memory_context=memory,
        )

        # 6. Save assistant message
        self.repository.add_message(user_id, "assistant", assistant_text)

        return assistant_text

    async def process_image_message(self, user_id: int, image_content: bytes) -> str:
        """
        Process image for OCR and generate translation response.

        Args:
            user_id: ID of the user
            image_content: Image file content as bytes

        Returns:
            Translation response message

        Raises:
            RunestoneError: If OCR fails or returns empty text
        """
        # 1. Run OCR on image content
        ocr_result = self.processor.run_ocr(image_content)

        if not ocr_result.transcribed_text or not ocr_result.transcribed_text.strip():
            logger.warning("OCR returned empty text")
            raise RunestoneError("Could not recognize text from image")

        logger.info(f"OCR extracted {len(ocr_result.transcribed_text)} characters")
        ocr_text = ocr_result.transcribed_text

        # 2. Truncate old messages
        self.repository.truncate_history(user_id, self.settings.chat_history_retention_days)

        # 3. Fetch context for agent
        context_models = self.repository.get_context_for_agent(user_id)

        # Convert models to schemas for the agent service
        history = [
            ChatMessageSchema(id=m.id, role=m.role, content=m.content, created_at=m.created_at) for m in context_models
        ]

        # 4. Get user and build memory context
        user = self.user_service.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        memory = self.user_service.get_user_memory(user)

        # 5. Build translation prompt with OCR text
        # Determine intro text based on user's mother tongue
        mother_tongue = user.mother_tongue or "English"

        translation_prompt = f"""User uploaded an image with Swedish text. Please translate it phrase-by-phrase.

OCR Text:
{ocr_text}

Instructions:
1. Start your response with an intro like "Here's the translated text from your image:" (in {mother_tongue})
2. Then provide phrase-by-phrase translation in format: "Swedish phrase (translation). Next phrase (translation)."
3. Use {mother_tongue} for all translations."""

        # 6. Generate response using the ReAct agent
        assistant_text = await self.agent_service.generate_response(
            message=translation_prompt,
            history=history,
            user=user,
            user_service=self.user_service,
            memory_context=memory,
        )

        # 7. Save assistant message (no user message saved for image uploads)
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
