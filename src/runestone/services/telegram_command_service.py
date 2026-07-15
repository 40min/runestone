import logging
import re
from typing import Optional

import httpx

from runestone.config import settings
from runestone.core.exceptions import (
    RecallOperationError,
    TelegramUsernameConflictError,
    WordNotFoundError,
    WordNotInSelectionError,
)
from runestone.services.recall_service import RecallService
from runestone.services.recall_types import RecallEnableStatus
from runestone.state.telegram_update_offset_store import TelegramUpdateOffsetStore

logger = logging.getLogger(__name__)


class TelegramCommandService:
    def __init__(
        self,
        offset_store: TelegramUpdateOffsetStore,
        recall_service: RecallService,
    ):
        self.offset_store = offset_store
        self.recall_service = recall_service
        self.bot_token = settings.telegram_bot_token
        if not self.bot_token:
            raise ValueError("Telegram bot token is required")

        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def _parse_word_from_reply_text(self, reply_text: str) -> Optional[str]:
        """
        Parse the Swedish word from reply text format like:
        '🇸🇪 kontanter\n🇬🇧 cash\n\n💡 Example: - Tår ni kontanter?'

        Returns:
            The Swedish word or None if not found
        """
        if not reply_text:
            return None

        # Look for the pattern: 🇸🇪 followed by a word
        pattern = r"🇸🇪\s+([^\n]+)"
        match = re.search(pattern, reply_text)

        if match:
            word_phrase = match.group(1).strip()
            for marker in ("**", "__", "*", "_"):
                if word_phrase.startswith(marker) and word_phrase.endswith(marker):
                    return word_phrase[len(marker) : -len(marker)].strip()
            return word_phrase

        return None

    async def _send_message(self, chat_id: int, text: str, parse_mode: Optional[str] = None) -> bool:
        """Send a message to a Telegram chat."""
        try:
            payload = {"chat_id": chat_id, "text": text}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{self.base_url}/sendMessage", json=payload)
                response.raise_for_status()
                return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to send message to chat {chat_id}: {e}")
            return False

    async def process_updates(self) -> None:
        """Poll for updates and process commands."""
        # Get the updates from Telegram API with isolated error handling
        updates, max_update_id = await self._fetch_updates()
        if not updates:
            return  # Error occurred during fetch or no updates, already logged

        # Telegram update IDs define the durable processing order. Sorting also
        # makes recovery deterministic if a proxy or recorder returns a batch
        # in an unexpected order.
        updates = sorted(updates, key=lambda update: update.get("update_id", 0))

        # Process each update individually with isolated error handling.
        for update in updates:
            try:
                update_id = update.get("update_id")
                if update_id:
                    max_update_id = max(max_update_id, update_id)

                await self._process_single_update(update)
            except Exception as e:
                logger.error(f"Error processing single update {update.get('update_id', 'unknown')}: {e}")
                await self._recover_failed_update()
                # Continue processing other updates even if one fails

        # Update offset to the next one if any updates were received
        if updates and max_update_id > 0:
            try:
                self.offset_store.set_update_offset(max_update_id + 1)
            except Exception as e:
                logger.error(f"Failed to update offset: {e}")

    async def _fetch_updates(self) -> tuple[list, int]:
        """
        Fetch updates from Telegram API with isolated error handling.

        Returns:
            tuple: (updates_list, max_update_id) - empty list if error occurred
        """
        try:
            offset = self.offset_store.get_update_offset()
        except Exception as e:
            logger.error(f"Failed to get update offset: {e}")
            return [], 0

        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                response = await client.get(f"{self.base_url}/getUpdates", params={"offset": offset, "timeout": 30})
                response.raise_for_status()
                data = response.json()
        except httpx.RequestError as e:
            logger.error(f"Failed to poll updates (network error): {e}")
            return [], 0
        except Exception as e:
            logger.error(f"Unexpected error during API request: {e}")
            return [], 0

        if not data.get("ok"):
            logger.error(f"Telegram API error: {data}")
            return [], 0

        updates = data.get("result", [])
        return updates, 0

    async def _process_single_update(self, update: dict) -> None:
        """
        Process a single update with proper validation and error handling.

        Args:
            update: The update dictionary from Telegram API
        """
        message = update.get("message")
        if not message:
            logger.debug(f"Update {update.get('update_id')} has no message, skipping")
            return

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        user = message.get("from", {})
        username = user.get("username")
        text = message.get("text", "").strip()

        if not username or not chat_id:
            logger.warning(f"Message without username or chat_id: {update}")
            return

        # Check if message contains bot command
        entities = message.get("entities", [])
        if not any(entity.get("type") == "bot_command" for entity in entities):
            logger.debug(f"Message from {username} is not a bot command, ignoring")
            return

        logger.info(f"Processing bot command '{text}' from {username} in chat {chat_id}")

        if text == "/start":
            try:
                if not await self._try_link_user_from_profile(username, chat_id):
                    await self._send_start_response(chat_id, "Sorry, you are not authorized to use this bot.")
            except Exception as e:
                logger.error(f"Error processing command '/start' for user {username}: {e}")
                await self._recover_failed_update()
                if not await self._send_message(chat_id, "Sorry, an error occurred while processing your command."):
                    logger.error("Failed to send /start error message to user %s", username)
            return

        try:
            normalized_username, user_data = await self.recall_service.get_state_for_telegram_username(username)
        except TelegramUsernameConflictError:
            logger.exception("Telegram username %s could not be resolved uniquely", username)
            return
        except Exception as e:
            logger.error(f"Failed to get user data for {username}: {e}")
            await self._recover_failed_update()
            return

        if user_data and normalized_username:
            # Authorized user - process commands
            try:
                await self._handle_authorized_user_command(text, message, normalized_username, user_data, chat_id)
            except Exception as e:
                logger.error(f"Error processing command '{text}' for user {username}: {e}")
                await self._recover_failed_update()
                # Attempt to notify user of the error
                try:
                    await self._send_message(chat_id, "Sorry, an error occurred while processing your command.")
                except Exception as send_error:
                    logger.error(f"Failed to send error message to user {username}: {send_error}")
        else:
            # Unauthorized user
            logger.warning(f"Unauthorized user {username} tried to access the bot")
            try:
                await self._send_message(chat_id, "Sorry, you are not authorized to use this bot.")
            except Exception as e:
                logger.error(f"Failed to send unauthorized message to {username}: {e}")

    async def _recover_failed_update(self) -> None:
        """Restore the shared command session after an unexpected update failure."""
        try:
            await self.recall_service.rollback_failed_operation()
        except Exception:
            logger.exception("Failed to recover the recall session after an update error")

    async def _send_start_response(self, chat_id: int, text: str) -> None:
        """Require an observable response for a consumed `/start` update."""
        if not await self._send_message(chat_id, text):
            raise RuntimeError("Telegram rejected the /start response")

    async def _try_link_user_from_profile(self, username: str, chat_id: int) -> bool:
        """Link an active profile through the recall application boundary."""
        try:
            result = await self.recall_service.enable_for_username(username, chat_id)
        except TelegramUsernameConflictError:
            await self._send_start_response(
                chat_id,
                "This Telegram username is linked to multiple Runestone accounts. Please contact an administrator.",
            )
            logger.exception("Telegram username %s matched multiple Runestone users", username)
            return True

        if result.status is RecallEnableStatus.INVALID_USERNAME:
            logger.warning("Cannot link Telegram user %s because its username is invalid", username)
            return False

        if result.status is RecallEnableStatus.USER_NOT_FOUND:
            await self._send_start_response(
                chat_id,
                "I couldn't find a Runestone account linked to this Telegram username. "
                "Add your Telegram username in Profile, then send /start again.",
            )
            return True

        if result.status is RecallEnableStatus.USER_INACTIVE:
            await self._send_start_response(
                chat_id,
                "Your Runestone account is not active. Please contact an administrator.",
            )
            return True

        if (
            result.status is not RecallEnableStatus.ENABLED
            or result.normalized_username is None
            or result.user_id is None
        ):
            logger.error("Unexpected recall enable result status=%s", result.status)
            await self._send_start_response(chat_id, "Sorry, an error occurred while starting the bot.")
            return True
        if result.was_already_enabled:
            await self._send_start_response(
                chat_id,
                "Bot is already active. You will continue receiving daily vocabulary words.",
            )
            logger.info("Telegram user %s sent /start but recall was already enabled", result.normalized_username)
            return True

        await self._send_start_response(chat_id, "Bot started! You will receive daily vocabulary words.")
        logger.info("Linked Telegram user %s to Runestone user %s", result.normalized_username, result.user_id)
        return True

    async def _handle_authorized_user_command(
        self, text: str, message: dict, username: str, user_data, chat_id: int
    ) -> None:
        """Handle commands from authorized users."""
        if text == "/stop":
            await self.recall_service.disable_for_user(user_data.user_id, chat_id=user_data.telegram_chat_id)
            await self._send_message(chat_id, "Bot stopped. You will no longer receive vocabulary words.")
            logger.info(f"User {username} stopped the bot")
        elif text == "/remove":
            await self._handle_remove_command(message, username, user_data, chat_id)
        elif text == "/postpone":
            await self._handle_postpone_command(message, username, user_data, chat_id)
        elif text == "/state":
            await self._handle_state_command(username, user_data, chat_id)
        elif text == "/bump_words":
            await self._handle_bump_words_command(username, user_data, chat_id)
        else:
            logger.debug(f"Unknown command '{text}' from user {username}")

    async def _handle_remove_command(self, message: dict, username: str, user_data, chat_id: int) -> None:
        """Handle the /remove command to completely remove a word from database and daily_selection."""
        reply_to_message = message.get("reply_to_message")
        if not reply_to_message:
            await self._send_message(chat_id, "Please reply to a word message to remove it.")
            return

        reply_text = reply_to_message.get("text", "")
        word_phrase = self._parse_word_from_reply_text(reply_text)

        if not word_phrase:
            await self._send_message(chat_id, "Could not find a word to remove in the replied message.")
            return

        try:
            await self.recall_service.remove_word_completely(user_data, word_phrase)
            await self._send_message(chat_id, f"Word '{word_phrase}' removed from vocabulary.")

        except WordNotFoundError:
            await self._send_message(chat_id, f"Word '{word_phrase}' not found in your vocabulary.")
        except RecallOperationError as e:
            await self._send_message(chat_id, f"Error: {e.message}")
            logger.error(f"Failed to remove word for {username}: {e.details}")

    async def _handle_bump_words_command(self, username: str, user_data, chat_id: int) -> None:
        """Handle the /bump_words command to replace current daily selection with new words."""
        try:
            user_data = await self.recall_service.bump_words(user_data)
            count = len(user_data.daily_selection)
            if count > 0:
                await self._send_message(chat_id, f"Daily selection updated! Selected {count} new words for today.")
            else:
                await self._send_message(chat_id, "Daily selection cleared. No new words available at this time.")

        except RecallOperationError as e:
            await self._send_message(chat_id, f"Error: {e.message}")

    async def _handle_state_command(self, username: str, user_data, chat_id: int) -> None:
        """Handle the /state command to show user's current state."""
        is_active_text = "✅ Yes" if user_data.is_enabled else "❌ No"

        if user_data.daily_selection:
            words_list = "\n".join(f"- {word.word_phrase}" for word in user_data.daily_selection)
        else:
            words_list = "No words selected for today."

        message = f"Current State\n\nIs Active: {is_active_text}\n\nDaily Selection:\n{words_list}"

        await self._send_message(chat_id, message)

    async def _handle_postpone_command(self, message: dict, username: str, user_data, chat_id: int) -> None:
        """Handle the /postpone command to remove a word from daily_selection only."""
        reply_to_message = message.get("reply_to_message")
        if not reply_to_message:
            await self._send_message(chat_id, "Please reply to a word message to postpone it.")
            return

        reply_text = reply_to_message.get("text", "")
        word_phrase = self._parse_word_from_reply_text(reply_text)

        if not word_phrase:
            await self._send_message(chat_id, "Could not find a word to postpone in the replied message.")
            return

        try:
            await self.recall_service.postpone_word(user_data, word_phrase)
            await self._send_message(chat_id, f"Word '{word_phrase}' postponed (removed from today's selection).")

        except WordNotInSelectionError:
            await self._send_message(chat_id, f"Word '{word_phrase}' was not in today's selection.")
        except RecallOperationError as e:
            await self._send_message(chat_id, f"Error: {e.message}")
