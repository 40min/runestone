import logging
import re
from typing import Optional

import httpx

from runestone.config import settings
from runestone.services.rune_recall_service import RuneRecallService
from runestone.state.state_manager import StateManager
from runestone.utils.markdown import escape_markdown

logger = logging.getLogger(__name__)


class TelegramCommandService:
    def __init__(self, state_manager: StateManager, rune_recall_service: RuneRecallService):
        self.state_manager = state_manager
        self.rune_recall_service = rune_recall_service
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
            return match.group(1).strip().strip("*_")

        return None

    def _send_message(self, chat_id: int, text: str, parse_mode: Optional[str] = None) -> bool:
        """Send a message to a Telegram chat."""
        try:
            payload = {"chat_id": chat_id, "text": text}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            with httpx.Client(timeout=10.0) as client:
                response = client.post(f"{self.base_url}/sendMessage", json=payload)
                response.raise_for_status()
                return True
        except httpx.RequestError as e:
            logger.error(f"Failed to send message to chat {chat_id}: {e}")
            return False

    def process_updates(self) -> None:
        """Poll for updates and process commands."""
        # Get the updates from Telegram API with isolated error handling
        updates, max_update_id = self._fetch_updates()
        if not updates:
            return  # Error occurred during fetch or no updates, already logged

        # Process each update individually with isolated error handling
        for update in updates:
            try:
                update_id = update.get("update_id")
                if update_id:
                    max_update_id = max(max_update_id, update_id)

                self._process_single_update(update)
            except Exception as e:
                logger.error(f"Error processing single update {update.get('update_id', 'unknown')}: {e}")
                # Continue processing other updates even if one fails

        # Update offset to the next one if any updates were received
        if updates and max_update_id > 0:
            try:
                self.state_manager.set_update_offset(max_update_id + 1)
            except Exception as e:
                logger.error(f"Failed to update offset: {e}")

    def _fetch_updates(self) -> tuple[list, int]:
        """
        Fetch updates from Telegram API with isolated error handling.

        Returns:
            tuple: (updates_list, max_update_id) - empty list if error occurred
        """
        try:
            offset = self.state_manager.get_update_offset()
        except Exception as e:
            logger.error(f"Failed to get update offset: {e}")
            return [], 0

        try:
            with httpx.Client(timeout=35.0) as client:
                response = client.get(f"{self.base_url}/getUpdates", params={"offset": offset, "timeout": 30})
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

    def _process_single_update(self, update: dict) -> None:
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

        try:
            user_data = self.state_manager.get_user(username)
        except Exception as e:
            logger.error(f"Failed to get user data for {username}: {e}")
            return

        if user_data:
            # Authorized user - process commands
            try:
                self._handle_authorized_user_command(text, message, username, user_data, chat_id)
            except Exception as e:
                logger.error(f"Error processing command '{text}' for user {username}: {e}")
                # Attempt to notify user of the error
                try:
                    self._send_message(chat_id, "Sorry, an error occurred while processing your command.")
                except Exception as send_error:
                    logger.error(f"Failed to send error message to user {username}: {send_error}")
        else:
            # Unauthorized user
            logger.warning(f"Unauthorized user {username} tried to access the bot")
            try:
                self._send_message(chat_id, "Sorry, you are not authorized to use this bot.")
            except Exception as e:
                logger.error(f"Failed to send unauthorized message to {username}: {e}")

    def _handle_authorized_user_command(self, text: str, message: dict, username: str, user_data, chat_id: int) -> None:
        """Handle commands from authorized users."""
        if text == "/start":
            was_inactive = not user_data.is_active
            user_data.is_active = True
            user_data.chat_id = chat_id
            self.state_manager.update_user(username, user_data)
            if was_inactive:
                self._send_message(chat_id, "Bot started! You will receive daily vocabulary words.")
                logger.info(f"User {username} started the bot")
            else:
                logger.info(f"User {username} sent /start but was already active")
        elif text == "/stop":
            user_data.is_active = False
            self.state_manager.update_user(username, user_data)
            self._send_message(chat_id, "Bot stopped. You will no longer receive vocabulary words.")
            logger.info(f"User {username} stopped the bot")
        elif text == "/remove":
            self._handle_remove_command(message, username, user_data, chat_id)
        elif text == "/postpone":
            self._handle_postpone_command(message, username, user_data, chat_id)
        elif text == "/state":
            self._handle_state_command(username, user_data, chat_id)
        else:
            # Unknown command, ignore or send help
            logger.debug(f"Unknown command '{text}' from user {username}")

    def _handle_remove_command(self, message: dict, username: str, user_data, chat_id: int) -> None:
        """Handle the /remove command to completely remove a word from database and daily_selection."""

        reply_to_message = message.get("reply_to_message")
        if not reply_to_message:
            self._send_message(chat_id, "Please reply to a word message to remove it.")
            return

        reply_text = reply_to_message.get("text", "")
        word_phrase = self._parse_word_from_reply_text(reply_text)

        if not word_phrase:
            self._send_message(chat_id, "Could not find a word to remove in the replied message.")
            return

        # Delegate to RuneRecallService
        result = self.rune_recall_service.remove_word_completely(username, word_phrase)

        # Send response based on result
        self._send_message(chat_id, result["message"])

    def _handle_state_command(self, username: str, user_data, chat_id: int) -> None:
        """Handle the /state command to show user's current state."""
        is_active_text = "✅ Yes" if user_data.is_active else "❌ No"

        if user_data.daily_selection:
            words_list = "\n".join(f"- {escape_markdown(word.word_phrase)}" for word in user_data.daily_selection)
        else:
            words_list = "No words selected for today."

        message = f"**Current State**\n\n**Is Active:** {is_active_text}\n\n**Daily Selection:**\n{words_list}"

        self._send_message(chat_id, message, parse_mode="MarkdownV2")

    def _handle_postpone_command(self, message: dict, username: str, user_data, chat_id: int) -> None:
        """Handle the /postpone command to remove a word from daily_selection only."""
        if not self.rune_recall_service:
            self._send_message(chat_id, "Postpone command is not available - no vocabulary service configured.")
            return

        reply_to_message = message.get("reply_to_message")
        if not reply_to_message:
            self._send_message(chat_id, "Please reply to a word message to postpone it.")
            return

        reply_text = reply_to_message.get("text", "")
        word_phrase = self._parse_word_from_reply_text(reply_text)

        if not word_phrase:
            self._send_message(chat_id, "Could not find a word to postpone in the replied message.")
            return

        # Delegate to RuneRecallService
        result = self.rune_recall_service.postpone_word(username, word_phrase)

        # Send response based on result
        self._send_message(chat_id, result["message"])
