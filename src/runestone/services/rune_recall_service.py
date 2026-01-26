"""
Service for sending daily vocabulary words to users via Telegram.

This module contains the RuneRecallService class that handles the daily word
portion logic for multiple concurrent users.
"""

import logging
from datetime import datetime

import httpx

from runestone.core.exceptions import VocabularyOperationError, WordNotFoundError, WordNotInSelectionError
from runestone.db.vocabulary_repository import VocabularyRepository
from runestone.state.state_manager import StateManager
from runestone.state.state_types import UserData, WordOfDay
from runestone.utils.markdown import escape_markdown

logger = logging.getLogger(__name__)


class RuneRecallService:
    """Service for sending daily vocabulary words to Telegram users."""

    def __init__(
        self,
        vocabulary_repository: VocabularyRepository,
        state_manager: StateManager,
        settings,
    ):
        """
        Initialize the RuneRecallService.

        Args:
            vocabulary_repository: VocabularyRepository instance for database operations
            state_manager: StateManager instance for user state management
            settings: Application settings object
        """
        self.vocabulary_repository = vocabulary_repository
        self.state_manager = state_manager
        self.bot_token = settings.telegram_bot_token
        if not self.bot_token:
            raise ValueError("Telegram bot token is required")

        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.words_per_day = settings.words_per_day
        self.cooldown_days = settings.cooldown_days
        self.recall_start_hour = settings.recall_start_hour
        self.recall_end_hour = settings.recall_end_hour

    def send_next_recall_word(self) -> None:
        """
        Send the next vocabulary word in the daily portion to all active users.

        This method iterates through all active users and sends one word from their
        daily portion if available and within the recall period.
        """
        current_hour = datetime.now().hour

        # Check if we're within recall hours
        if not (self.recall_start_hour <= current_hour < self.recall_end_hour):
            logger.info(f"Outside recall hours ({self.recall_start_hour}-{self.recall_end_hour}), skipping recall")
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

    def _process_user_recall_word(self, username: str, user_data: UserData, max_attempts: int = 3) -> None:
        """
        Process and send the next word from the daily portion for a specific user.

        Args:
            username: Username for logging purposes
            user_data: UserData object for the user
            max_attempts: Maximum number of attempts to retry with new selection (default: 3)
        """
        if not user_data.chat_id:
            logger.warning(f"Missing chat_id for user {username}, skipping recall")
            return

        # Ensure we have a daily selection
        if not self._ensure_daily_selection(username, user_data):
            return

        # Try to send a word, handling missing words by removing them from selection
        max_word_attempts = len(user_data.daily_selection)
        for _ in range(max_word_attempts):
            word_id = self._get_next_word_id_to_send(user_data)
            if word_id is None:
                logger.warning(f"No more words to send for user {username}")
                return

            word = self._fetch_valid_word(word_id, user_data.db_user_id)

            if word:
                # Successfully fetched word, send it
                self._send_and_update_word(username, user_data, word)
                return
            else:
                # Word not found or not in learning - remove from daily selection
                logger.warning(
                    f"Word {word_id} not found or not in learning for user {username}, removing from selection"
                )
                self._remove_word_by_id_from_selection(user_data, word_id)
                self.state_manager.update_user(username, user_data)
                # Continue loop to try next word

        logger.info(f"All words in daily selection were invalid for user {username}, getting new selection")
        self.bump_words(username, user_data)

        if max_attempts > 0:
            # Retry with new selection, but limit attempts to prevent infinite recursion
            logger.info(f"Retrying with new selection for user {username} (attempts left: {max_attempts})")
            self._process_user_recall_word(username, user_data, max_attempts=max_attempts - 1)
        else:
            logger.warning(f"Max retry attempts reached for user {username}, giving up")

    def _ensure_daily_selection(self, username: str, user_data: UserData) -> bool:
        """
        Ensure user has a daily selection, creating one if needed.

        Args:
            username: Username for logging purposes
            user_data: UserData object for the user

        Returns:
            True if daily selection exists or was successfully created, False otherwise
        """
        if user_data.daily_selection:
            return True

        logger.info(f"Selecting new daily portion for user {username}")
        portion_words = self._select_daily_portion(user_data.db_user_id)
        if not portion_words:
            logger.info(f"No words available for daily portion for user {username}")
            return False

        user_data.daily_selection = [
            WordOfDay(id_=word["id"], word_phrase=word["word_phrase"]) for word in portion_words
        ]
        user_data.next_word_index = 0
        self.state_manager.update_user(username, user_data)
        return True

    def _get_next_word_id_to_send(self, user_data: UserData) -> int | None:
        """
        Get the ID of the next word to send based on next_word_index.

        Args:
            user_data: UserData object for the user

        Returns:
            Word ID to send, or None if no words available
        """
        if not user_data.daily_selection:
            return None

        # Reset index if it exceeds the selection length
        if user_data.next_word_index >= len(user_data.daily_selection):
            user_data.next_word_index = 0

        return user_data.daily_selection[user_data.next_word_index].id_

    def _fetch_valid_word(self, word_id: int, db_user_id: int):
        """
        Fetch a word from the database if it exists and is valid for recall.

        Args:
            word_id: ID of the word to fetch
            db_user_id: Database user ID

        Returns:
            Word object if found and valid, None otherwise
        """
        try:
            return self.vocabulary_repository.get_vocabulary_item_for_recall(word_id, db_user_id)
        except ValueError:
            # Word not found or not in learning
            return None

    def _send_and_update_word(self, username: str, user_data: UserData, word) -> None:
        """
        Send a word message and update state on success.

        Args:
            username: Username for logging purposes
            user_data: UserData object for the user
            word: Word object to send
        """
        word_to_send = {
            "id": word.id,
            "word_phrase": word.word_phrase,
            "translation": word.translation,
            "example_phrase": word.example_phrase,
        }

        # chat_id is guaranteed to be non-None due to check in _process_user_recall_word
        assert user_data.chat_id is not None
        if self._send_word_message(user_data.chat_id, word_to_send):
            # Update learned_times for every attempt to show word to user
            self.vocabulary_repository.update_last_learned(word)
            # Update the next word index
            user_data.next_word_index += 1
            self.state_manager.update_user(username, user_data)
            logger.info(
                f"Sent recall word {user_data.next_word_index}/{len(user_data.daily_selection)} to user {username}"
            )
        else:
            logger.error(f"Failed to send recall word to user {username}")

    def _remove_word_by_id_from_selection(self, user_data: UserData, word_id: int) -> bool:
        """
        Remove a word from daily_selection by its ID.

        Args:
            user_data: UserData object for the user
            word_id: ID of the word to remove

        Returns:
            True if word was found and removed, False otherwise
        """
        original_length = len(user_data.daily_selection)
        user_data.daily_selection = [word for word in user_data.daily_selection if word.id_ != word_id]

        # Adjust next_word_index if needed
        if user_data.next_word_index >= len(user_data.daily_selection):
            user_data.next_word_index = 0

        return len(user_data.daily_selection) < original_length

    def _select_daily_portion(self, db_user_id: int) -> list[dict]:
        """
        Select a daily portion of words for recall based on user's vocabulary and cooldown.

        Args:
            db_user_id: Database user ID

        Returns:
            List of word dictionaries for the daily portion
        """
        # Repository method now handles cooldown filtering based on last_learned and returns full word objects
        words = self.vocabulary_repository.select_new_daily_words(
            db_user_id, self.cooldown_days, limit=self.words_per_day
        )

        return [
            {
                "id": word.id,
                "word_phrase": word.word_phrase,
                "translation": word.translation,
                "example_phrase": word.example_phrase,
            }
            for word in words
        ]

    def _send_word_message(self, chat_id: int, word: dict) -> bool:
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

    def maintain_daily_selection(self, username: str, user_data: UserData) -> int:
        """
        Ensure user has target number of words in daily selection.
        Adds replacement words as needed to reach words_per_day target.

        Args:
            username: Username for logging purposes
            user_data: UserData object for the user

        Returns:
            Number of words added (0 if no words added or needed)
        """
        current_count = len(user_data.daily_selection)
        target_count = self.words_per_day

        # Check if we need to add words
        if current_count >= target_count:
            logger.debug(f"User {username} already has {current_count}/{target_count} words, " "no maintenance needed")
            return 0

        # Calculate how many words we need to add
        needed = target_count - current_count
        logger.info(
            f"User {username} has {current_count}/{target_count} words, " f"attempting to add {needed} replacement(s)"
        )

        # Get list of word IDs to exclude (already in selection)
        excluded_ids = [word.id_ for word in user_data.daily_selection]

        # Select replacement words (reusing existing method with exclusions)
        new_words = self.vocabulary_repository.select_new_daily_words(
            user_id=user_data.db_user_id,
            cooldown_days=self.cooldown_days,
            limit=needed,
            excluded_word_ids=excluded_ids if excluded_ids else None,
        )

        if new_words:
            # Add new words to daily selection
            for word in new_words:
                user_data.daily_selection.append(WordOfDay(id_=word.id, word_phrase=word.word_phrase))

            added_count = len(new_words)
            logger.info(
                f"Added {added_count} replacement word(s) for user {username} "
                f"(now {len(user_data.daily_selection)}/{target_count})"
            )
            return added_count
        else:
            logger.info(
                f"No replacement words available for user {username} "
                f"(current: {current_count}/{target_count}, all words in cooldown or exhausted)"
            )
            return 0

    def update_user_daily_selection(self, username: str, user_data: UserData) -> None:
        """
        Centralized method for updating user's daily_selection in state.

        Args:
            username: Username to update
            user_data: UserData object with updated daily_selection
        """
        self.state_manager.update_user(username, user_data)

    def remove_word_completely(self, username: str, word_phrase: str) -> None:
        """
        Remove word from both database and daily_selection.

        Raises:
            WordNotFoundError: If word doesn't exist in user's vocabulary
            VocabularyOperationError: If operation fails
        """
        user_data = self.state_manager.get_user(username)
        if not user_data:
            raise VocabularyOperationError(f"User '{username}' not found")

        matching_word = self.vocabulary_repository.get_vocabulary_item_by_word_phrase(word_phrase, user_data.db_user_id)

        if not matching_word:
            raise WordNotFoundError(word_phrase, username)

        # Reset priority flag before deletion
        matching_word.priority_learn = False

        # Remove from database
        if not self.vocabulary_repository.delete_vocabulary_item_by_word_phrase(word_phrase, user_data.db_user_id):
            raise VocabularyOperationError("Failed to remove word from database")

        # Remove from daily_selection and maintain count
        was_in_selection = self.remove_word_from_daily_selection(user_data, word_phrase)
        if was_in_selection:
            self.maintain_daily_selection(username, user_data)

        self.update_user_daily_selection(username, user_data)
        logger.info(f"User {username} removed word '{word_phrase}'")
        # Returns nothing - success is implicit

    def postpone_word(self, username: str, word_phrase: str) -> None:
        """
        Remove word from daily_selection only (postpone learning).

        Raises:
            WordNotInSelectionError: If word is not in today's selection
            VocabularyOperationError: If operation fails
        """
        user_data = self.state_manager.get_user(username)
        if not user_data:
            raise VocabularyOperationError(f"User '{username}' not found")

        if not self.remove_word_from_daily_selection(user_data, word_phrase):
            raise WordNotInSelectionError(word_phrase)

        # Reset priority flag when postponing
        vocab_item = self.vocabulary_repository.get_vocabulary_item_by_word_phrase(word_phrase, user_data.db_user_id)
        if vocab_item:
            vocab_item.priority_learn = False
            self.vocabulary_repository.update_vocabulary_item(vocab_item)

        self.maintain_daily_selection(username, user_data)
        self.update_user_daily_selection(username, user_data)
        logger.info(f"User {username} postponed word '{word_phrase}'")
        # Returns nothing - success is implicit

    def bump_words(self, username: str, user_data) -> None:
        """
        Replace current daily selection with a new portion of words.

        Raises:
            VocabularyOperationError: If operation fails
        """
        logger.info(f"User {username} requested to bump words")

        user_data.daily_selection = []
        user_data.next_word_index = 0

        portion_words = self._select_daily_portion(user_data.db_user_id)

        if portion_words:
            user_data.daily_selection = [
                WordOfDay(id_=word["id"], word_phrase=word["word_phrase"]) for word in portion_words
            ]

        self.state_manager.update_user(username, user_data)
        logger.info(f"User {username} bumped words - selected {len(portion_words)} new words")
        # Returns nothing - success is implicit
