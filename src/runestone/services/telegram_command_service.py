import logging
from typing import Optional

import httpx

from runestone.config import settings
from runestone.state.state_manager import StateManager

logger = logging.getLogger(__name__)


class TelegramCommandService:
    def __init__(self, state_manager: StateManager, bot_token: Optional[str] = None):
        self.state_manager = state_manager
        self.bot_token = bot_token or settings.telegram_bot_token
        if not self.bot_token:
            raise ValueError("Telegram bot token is required")

        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def _send_message(self, chat_id: int, text: str) -> bool:
        """Send a message to a Telegram chat."""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(f"{self.base_url}/sendMessage", json={"chat_id": chat_id, "text": text})
                response.raise_for_status()
                return True
        except httpx.RequestError as e:
            logger.error(f"Failed to send message to chat {chat_id}: {e}")
            return False

    def process_updates(self) -> None:
        """Poll for updates and process commands."""
        try:
            offset = self.state_manager.get_update_offset()
            with httpx.Client(timeout=35.0) as client:
                response = client.get(f"{self.base_url}/getUpdates", params={"offset": offset, "timeout": 30})
                response.raise_for_status()
                data = response.json()

            if not data.get("ok"):
                logger.error(f"Telegram API error: {data}")
                return

            updates = data.get("result", [])
            max_update_id = offset

            for update in updates:
                update_id = update.get("update_id")
                max_update_id = max(max_update_id, update_id)

                message = update.get("message")
                if not message:
                    continue

                chat = message.get("chat", {})
                chat_id = chat.get("id")
                user = message.get("from", {})
                username = user.get("username")
                text = message.get("text", "").strip()

                if not username or not chat_id:
                    logger.warning(f"Message without username or chat_id: {update}")
                    continue

                user_data = self.state_manager.get_user(username)
                if user_data:
                    # Authorized user
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
                    else:
                        # Unknown command, ignore or send help
                        pass
                else:
                    # Unauthorized user
                    self._send_message(chat_id, "Sorry, you are not authorized to use this bot.")
                    logger.warning(f"Unauthorized user {username} tried to access the bot")

            # Update offset to the next one if any updates were received
            if updates:
                self.state_manager.set_update_offset(max_update_id + 1)

        except httpx.RequestError as e:
            logger.error(f"Failed to poll updates: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in process_updates: {e}")
