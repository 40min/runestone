"""
Service for sending daily vocabulary words to users via Telegram.

This module contains the TelegramRecallDeliveryService class that handles the daily word
portion logic for multiple concurrent users.
"""

import logging
from datetime import datetime

import httpx

from runestone.services.recall_service import RecallService
from runestone.services.recall_types import RecallQueueWord, RecallState
from runestone.utils.markdown import escape_markdown

logger = logging.getLogger(__name__)


class TelegramRecallDeliveryService:
    """Service for sending daily vocabulary words to Telegram users."""

    def __init__(
        self,
        recall_service: RecallService,
        settings,
    ):
        """
        Initialize the TelegramRecallDeliveryService.

        Args:
            recall_service: RecallService instance for user recall state management
            settings: Application settings object
        """
        self.recall_service = recall_service
        self.bot_token = settings.telegram_bot_token
        if not self.bot_token:
            raise ValueError("Telegram bot token is required")

        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.recall_start_hour = settings.recall_start_hour
        self.recall_end_hour = settings.recall_end_hour

    async def send_next_recall_word(self) -> None:
        """
        Send the next vocabulary word in the daily portion to all active users.

        This method iterates through all active users and sends one word from their
        daily portion if available and within the recall period.
        """
        current_hour = datetime.now().hour

        # Check if we're within recall hours
        if not (self.recall_start_hour <= current_hour < self.recall_end_hour):
            logger.info(
                "Outside recall hours (%s-%s), skipping recall",
                self.recall_start_hour,
                self.recall_end_hour,
            )
            return

        active_users = await self.recall_service.get_active_recall_states()
        logger.info("Starting recall word sending for %s active users", len(active_users))

        for user_state in active_users:
            try:
                await self._process_user_recall_word(user_state)
            except Exception as exc:
                logger.error(
                    "Failed to process recall word for user %s: %s",
                    user_state.user_id,
                    exc,
                )
                # Continue with other users even if one fails

        logger.info("Completed recall word sending process")

    async def _process_user_recall_word(self, user_state: RecallState, max_attempts: int = 3) -> None:
        """Delegate one user's locked delivery workflow to the recall service.

        Args:
            user_state: Recall state for the user
            max_attempts: Maximum number of attempts to retry with new selection (default: 3)
        """
        updated_state = await self.recall_service.deliver_next_word(
            user_state.user_id,
            self._send_queue_word,
            max_attempts=max_attempts,
        )
        if updated_state is not None:
            logger.info(
                "Completed recall delivery for user %s at cursor %s",
                user_state.telegram_username or user_state.user_id,
                updated_state.next_word_index,
            )

    async def _send_queue_word(self, chat_id: int, word: RecallQueueWord) -> bool:
        """Translate a recall queue DTO into the Telegram message payload."""
        return await self._send_word_message(
            chat_id,
            {
                "id": word.id,
                "word_phrase": word.word_phrase,
                "translation": word.translation,
                "example_phrase": word.example_phrase,
            },
        )

    async def _send_word_message(self, chat_id: int, word: dict) -> bool:
        """
        Send a vocabulary word message to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            word: Word dictionary with word_phrase, translation, etc.

        Returns:
            True if message was sent successfully, False otherwise
        """
        word_phrase = word.get("word_phrase", "Unknown")
        translation = word.get("translation", "Unknown")
        example_phrase = word.get("example_phrase", "")

        word_phrase = escape_markdown(word_phrase)
        translation = escape_markdown(translation)
        if example_phrase:
            example_phrase = escape_markdown(example_phrase)

        # Format the message
        message = f"🇸🇪 *{word_phrase}*\n🇬🇧 {translation}"
        if example_phrase:
            message += f"\n\n💡 _Example:_ {example_phrase}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={"chat_id": chat_id, "text": message, "parse_mode": "MarkdownV2"},
                )
                response.raise_for_status()
                payload = response.json()
                return isinstance(payload, dict) and payload.get("ok") is True
        except httpx.RequestError as exc:
            logger.error("Failed to send word message to chat %s: %s", chat_id, exc)
            return False
        except Exception as exc:
            logger.error("Unexpected error sending message to chat %s: %s", chat_id, exc)
            return False
