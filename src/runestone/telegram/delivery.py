"""Scheduled Telegram transport for recall-word delivery."""

import logging
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from functools import partial

import httpx

from runestone.recall.service import RecallService
from runestone.recall.types import RecallQueueWord
from runestone.utils.markdown import escape_markdown

logger = logging.getLogger(__name__)

RecallSessionProvider = Callable[[], AbstractAsyncContextManager[RecallService]]
SendWord = Callable[[int, RecallQueueWord], Awaitable[bool]]


class TelegramRecallDelivery:
    """Coordinate isolated recall sessions with Telegram message delivery."""

    def __init__(
        self,
        recall_session_provider: RecallSessionProvider,
        settings,
    ):
        """Initialize delivery with a session-only recall provider."""
        self.recall_session_provider = recall_session_provider
        self.bot_token = settings.telegram_bot_token
        if not self.bot_token:
            raise ValueError("Telegram bot token is required")

        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_next_recall_word(self) -> None:
        """Send one recall word to each eligible user in isolated sessions."""
        # Enumeration has its own short-lived read session and returns ids only.
        async with self.recall_session_provider() as recall_service:
            candidate_user_ids = await recall_service.get_delivery_candidate_user_ids()

        logger.info("Starting recall word sending for %s candidates", len(candidate_user_ids))
        async with httpx.AsyncClient(timeout=10.0) as client:
            send_word = partial(self._send_queue_word, client)
            for user_id in candidate_user_ids:
                try:
                    # deliver_next_word owns commit/rollback for this session and
                    # deliberately keeps its row lock across the send callback.
                    async with self.recall_session_provider() as recall_service:
                        await self._process_user_recall_word(recall_service, user_id, send_word)
                except Exception as exc:
                    logger.error(
                        "Failed to process recall word for user %s: %s",
                        user_id,
                        exc,
                    )

        logger.info("Completed recall word sending process")

    async def _process_user_recall_word(
        self,
        recall_service: RecallService,
        user_id: int,
        send_word: SendWord,
        max_attempts: int = 3,
    ) -> None:
        """Delegate one user's locked delivery workflow to its recall service."""
        updated_state = await recall_service.deliver_next_word(
            user_id,
            send_word,
            max_attempts=max_attempts,
        )
        if updated_state is not None:
            logger.info(
                "Completed recall delivery for user %s at cursor %s",
                user_id,
                updated_state.next_word_index,
            )

    async def _send_queue_word(
        self,
        client: httpx.AsyncClient,
        chat_id: int,
        word: RecallQueueWord,
    ) -> bool:
        """Translate a recall queue DTO into the Telegram message payload."""
        return await self._send_word_message(
            client,
            chat_id,
            {
                "id": word.id,
                "word_phrase": word.word_phrase,
                "translation": word.translation,
                "example_phrase": word.example_phrase,
            },
        )

    async def _send_word_message(
        self,
        client: httpx.AsyncClient,
        chat_id: int,
        word: dict,
    ) -> bool:
        """Send a formatted vocabulary word to one Telegram chat."""
        word_phrase = escape_markdown(word.get("word_phrase", "Unknown"))
        translation = escape_markdown(word.get("translation", "Unknown"))
        example_phrase = word.get("example_phrase", "")
        if example_phrase:
            example_phrase = escape_markdown(example_phrase)

        message = f"🇸🇪 *{word_phrase}*\n🇬🇧 {translation}"
        if example_phrase:
            message += f"\n\n💡 _Example:_ {example_phrase}"

        try:
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
