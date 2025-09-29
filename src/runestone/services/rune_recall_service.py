"""
Service for sending daily vocabulary words to users via Telegram.

This module contains the RuneRecallService class that handles the daily word
portion logic for multiple concurrent users.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from runestone.config import settings
from runestone.db.repository import VocabularyRepository
from runestone.state.state_manager import StateManager
from runestone.state.state_types import UserData, WordOfDay

logger = logging.getLogger(__name__)


class RuneRecallService:
    """Service for sending daily vocabulary words to Telegram users."""

    def __init__(
        self,
        vocabulary_repository: VocabularyRepository,
        state_manager: StateManager,
        bot_token: Optional[str] = None,
        words_per_day: int = 5,
        cooldown_days: int = 7,
    ):
        """
        Initialize the RuneRecallService.

        Args:
            vocabulary_repository: VocabularyRepository instance for database operations
            state_manager: StateManager instance for user state management
            bot_token: Telegram bot token (optional, uses settings if not provided)
            words_per_day: Maximum number of words to send per day per user
            cooldown_days: Number of days before a word can be repeated
        """
        self.vocabulary_repository = vocabulary_repository
        self.state_manager = state_manager
        self.bot_token = bot_token or settings.telegram_bot_token
        if not self.bot_token:
            raise ValueError("Telegram bot token is required")

        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.words_per_day = words_per_day
        self.cooldown_days = cooldown_days

    def send_next_recall_word(self) -> None:
        """
        Send the next vocabulary word in the daily portion to all active users.

        This method iterates through all active users and sends one word from their
        daily portion if available and within the recall period.
        """
        current_hour = datetime.now().hour

        # Check if we're within recall hours
        if not (settings.recall_start_hour <= current_hour < settings.recall_end_hour):
            logger.info(
                f"Outside recall hours ({settings.recall_start_hour}-{settings.recall_end_hour}), skipping recall"
            )
            return

        active_users = self.state_manager.get_active_users()
        logger.info(f"Starting recall word sending for {len(active_users)} active users")

        for username, user_data in active_users.items():
            try:
                self._process_user_recall_word(username, user_data)
            except Exception as e:
                logger.error(f"Failed to process recall word for user {username}: {e}")
                # Continue with other users even if one fails

        logger.info("Completed recall word sending process")

    def _process_user_recall_word(self, username: str, user_data: UserData) -> None:
        """
        Process and send the next word from the daily portion for a specific user.

        Args:
            user_data: UserData object for the user
        """
        db_user_id = user_data.db_user_id
        chat_id = user_data.chat_id

        if not chat_id:
            logger.warning(f"Missing chat_id for user {username}, skipping recall")
            return

        daily_selection = user_data.daily_selection
        next_word_index = user_data.next_word_index

        # Check if we need to select a new daily portion
        if not daily_selection:
            logger.info(f"Selecting new daily portion for user {username}")
            portion_words = self._select_daily_portion(db_user_id)
            if not portion_words:
                logger.info(f"No words available for daily portion for user {username}")
                return

            daily_selection_list = [
                WordOfDay(id_=word["id"], word_phrase=word["word_phrase"]) for word in portion_words
            ]
            next_word_index = 0
            user_data.daily_selection = daily_selection_list
            user_data.next_word_index = next_word_index
            self.state_manager.update_user(username, user_data)

        # Get the selected items for today
        selected_items = user_data.daily_selection
        selected_ids = [item.id_ for item in selected_items]
        if not selected_ids:
            logger.warning(f"No selected words available for user {username}, clearing daily selection")
            user_data.daily_selection = []
            self.state_manager.update_user(username, user_data)
            return
        if next_word_index >= len(selected_ids):
            next_word_index = 0

        # Fetch the next word from database
        word_id = selected_ids[next_word_index]
        word = self.vocabulary_repository.get_vocabulary_item_for_recall(word_id, db_user_id)
        if not word:
            logger.error(f"Word {word_id} not found in database or not in learning")
            return

        word_to_send = {
            "id": word.id,
            "word_phrase": word.word_phrase,
            "translation": word.translation,
            "example_phrase": word.example_phrase,
        }

        if self._send_word_message(chat_id, word_to_send):
            # Update last_learned timestamp
            self.vocabulary_repository.update_last_learned(word)
            # Update the next word index
            user_data.next_word_index = next_word_index + 1
            self.state_manager.update_user(username, user_data)
            logger.info(f"Sent recall word {next_word_index + 1}/{len(selected_ids)} to user {username}")
        else:
            logger.error(f"Failed to send recall word to user {username}")

    def _select_daily_portion(self, db_user_id: int) -> List[Dict]:
        """
        Select a daily portion of words for recall based on user's vocabulary and cooldown.

        Args:
            db_user_id: Database user ID

        Returns:
            List of word dictionaries for the daily portion
        """
        # Repository method now handles cooldown filtering based on last_learned
        available_word_ids = self.vocabulary_repository.select_new_daily_word_ids(db_user_id, self.cooldown_days)

        # Limit to words_per_day
        selected_ids = available_word_ids[: self.words_per_day]

        # Fetch full word details using repository method
        if selected_ids:
            words = self.vocabulary_repository.get_vocabulary_items_by_ids(selected_ids, db_user_id)
            return [
                {
                    "id": word.id,
                    "word_phrase": word.word_phrase,
                    "translation": word.translation,
                    "example_phrase": word.example_phrase,
                }
                for word in words
            ]

        return []

    def _escape_markdown(self, text: str) -> str:
        """Escape special Markdown characters that are not already escaped."""
        escape_chars = ["*", "_", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]

        for char in escape_chars:
            # Only escape characters that are not already preceded by a backslash
            # Use negative lookbehind (?<!\\) to check if the character is not already escaped
            pattern = f"(?<!\\\\){re.escape(char)}"
            text = re.sub(pattern, f"\\{char}", text)

        return text

    def _send_word_message(self, chat_id: int, word: Dict) -> bool:
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

        word_phrase = self._escape_markdown(word_phrase)
        translation = self._escape_markdown(translation)
        if example_phrase:
            example_phrase = self._escape_markdown(example_phrase)

        # Format the message
        message = f"🇸🇪 **{word_phrase}**\n🇬🇧 {translation}"
        if example_phrase:
            message += f"\n\n💡 *Example:* {example_phrase}"

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{self.base_url}/sendMessage",
                    json={"chat_id": chat_id, "text": message, "parse_mode": "MarkdownV2"},
                )
                response.raise_for_status()
                return True
        except httpx.RequestError as e:
            logger.error(f"Failed to send word message to chat {chat_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending message to chat {chat_id}: {e}")
            return False

    # Vocabulary Management Methods
    # These methods handle vocabulary state management operations

    def remove_word_from_daily_selection(self, user_data: UserData, word_phrase: str) -> bool:
        """
        Remove a word from user's daily_selection by word_phrase.

        Args:
            user_data: UserData object for the user
            word_phrase: Word phrase to remove from daily selection

        Returns:
            True if word was found and removed, False otherwise
        """
        original_length = len(user_data.daily_selection)
        user_data.daily_selection = [word for word in user_data.daily_selection if word.word_phrase != word_phrase]

        # Adjust next_word_index if needed
        if user_data.next_word_index >= len(user_data.daily_selection):
            user_data.next_word_index = 0

        return len(user_data.daily_selection) < original_length

    def replenish_daily_selection_if_empty(self, username: str, user_data: UserData) -> None:
        """
        Replenish daily_selection if it becomes empty.

        Args:
            username: Username for logging purposes
            user_data: UserData object for the user
        """
        if not user_data.daily_selection:
            logger.info(f"Daily selection empty for user {username}, selecting new portion")
            portion_words = self._select_daily_portion(user_data.db_user_id)
            if portion_words:
                daily_selection_list = [
                    WordOfDay(id_=word["id"], word_phrase=word["word_phrase"]) for word in portion_words
                ]
                user_data.daily_selection = daily_selection_list
                user_data.next_word_index = 0
                logger.info(f"Selected {len(portion_words)} new words for user {username}")

    def update_user_daily_selection(self, username: str, user_data: UserData) -> None:
        """
        Centralized method for updating user's daily_selection in state.

        Args:
            username: Username to update
            user_data: UserData object with updated daily_selection
        """
        self.state_manager.update_user(username, user_data)

    def remove_word_completely(self, username: str, word_phrase: str) -> Dict[str, Any]:
        """
        Remove word from both database and daily_selection.

        Args:
            username: Username of the user
            word_phrase: Word phrase to remove completely

        Returns:
            Dictionary with 'success' bool, 'message' str, and optional 'removed_from_selection' bool
        """
        try:
            user_data = self.state_manager.get_user(username)
            if not user_data:
                return {"success": False, "message": f"User '{username}' not found"}

            # Find the word in database by word_phrase and user_id
            matching_word = self.vocabulary_repository.get_vocabulary_item_by_word_phrase(
                word_phrase, user_data.db_user_id
            )

            if not matching_word:
                return {"success": False, "message": f"Word '{word_phrase}' not found in your vocabulary"}

            # Remove from database (set in_learn = False)
            db_success = self.vocabulary_repository.delete_vocabulary_item_by_word_phrase(
                word_phrase, user_data.db_user_id
            )

            if not db_success:
                return {"success": False, "message": f"Failed to remove word '{word_phrase}' from vocabulary"}

            # Remove from daily_selection
            removed_from_selection = self.remove_word_from_daily_selection(user_data, word_phrase)

            # Replenish daily_selection if it becomes empty
            self.replenish_daily_selection_if_empty(username, user_data)

            # Update user data in state
            self.update_user_daily_selection(username, user_data)

            # Prepare success message
            status_msg = "removed from vocabulary"
            if removed_from_selection:
                status_msg += " and daily selection"

            logger.info(f"User {username} removed word '{word_phrase}' from vocabulary")

            return {
                "success": True,
                "message": f"Word '{word_phrase}' {status_msg}.",
                "removed_from_selection": removed_from_selection,
            }

        except Exception as e:
            logger.error(f"Error removing word '{word_phrase}' for user {username}: {e}")
            return {"success": False, "message": "An error occurred while removing the word"}

    def postpone_word(self, username: str, word_phrase: str) -> Dict[str, Any]:
        """
        Remove word from daily_selection only (postpone learning).

        Args:
            username: Username of the user
            word_phrase: Word phrase to postpone

        Returns:
            Dictionary with 'success' bool and 'message' str
        """
        try:
            user_data = self.state_manager.get_user(username)
            if not user_data:
                return {"success": False, "message": f"User '{username}' not found"}

            # Remove from daily_selection
            removed_from_selection = self.remove_word_from_daily_selection(user_data, word_phrase)

            if removed_from_selection:
                # Replenish daily_selection if it becomes empty
                self.replenish_daily_selection_if_empty(username, user_data)

                # Update user data in state
                self.update_user_daily_selection(username, user_data)

                logger.info(f"User {username} postponed word '{word_phrase}'")
                return {"success": True, "message": f"Word '{word_phrase}' postponed (removed from today's selection)."}
            else:
                return {"success": False, "message": f"Word '{word_phrase}' was not in today's selection."}

        except Exception as e:
            logger.error(f"Error postponing word '{word_phrase}' for user {username}: {e}")
            return {"success": False, "message": "An error occurred while postponing the word"}
