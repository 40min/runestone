"""Telegram command polling, application outcomes, and transport delivery."""

import logging
import re
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import httpx
from sqlalchemy.exc import SQLAlchemyError

from runestone.config import settings
from runestone.core.exceptions import (
    RecallOperationError,
    TelegramUsernameConflictError,
    WordNotFoundError,
    WordNotInSelectionError,
)
from runestone.recall.types import RecallEnableStatus, RecallState
from runestone.telegram.offset_store import TelegramUpdateOffsetStore

if TYPE_CHECKING:
    from runestone.recall.service import RecallService

logger = logging.getLogger(__name__)

SUPPORTED_COMMANDS = frozenset({"/start", "/stop", "/state", "/remove", "/postpone", "/bump_words"})

CommandStatus = Literal["handled", "ignored", "retryable_failure"]
RecallTransactionProvider = Callable[[], AbstractAsyncContextManager["RecallService"]]


@dataclass(frozen=True, slots=True)
class TelegramMessage:
    """One outbound Telegram message prepared by command application."""

    chat_id: int
    text: str
    parse_mode: str | None = None


@dataclass(frozen=True, slots=True)
class CommandOutcome:
    """Application outcome used to separate database work from HTTP delivery."""

    status: CommandStatus
    messages: tuple[TelegramMessage, ...] = ()


class TelegramCommandProcessor:
    """Poll Telegram and apply each relevant update in an isolated transaction."""

    def __init__(
        self,
        offset_store: TelegramUpdateOffsetStore,
        provide_recall_transaction: RecallTransactionProvider,
    ):
        self.offset_store = offset_store
        self.provide_recall_transaction = provide_recall_transaction
        self.bot_token = settings.telegram_bot_token
        if not self.bot_token:
            raise ValueError("Telegram bot token is required")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def process_updates(self) -> None:
        """Fetch updates and acknowledge only the highest handled batch prefix."""
        updates = await self._fetch_updates()
        if not updates:
            return

        acknowledged_offset: int | None = None
        for update in sorted(updates, key=self._update_sort_key):
            update_id = update.get("update_id")
            if not self._is_relevant_command_update(update):
                outcome = CommandOutcome(status="ignored")
            else:
                try:
                    async with self.provide_recall_transaction() as recall_service:
                        outcome = await self._apply_command(update, recall_service)
                except Exception as exc:
                    if self._contains_database_error(exc):
                        logger.exception(
                            "Retryable database failure processing Telegram update %s",
                            update_id,
                        )
                        outcome = CommandOutcome(status="retryable_failure")
                    else:
                        logger.exception("Error processing Telegram update %s", update_id)
                        outcome = self._application_error_outcome(update, exc)

            if outcome.status == "retryable_failure":
                break

            await self._send_outcome_messages(outcome)
            if isinstance(update_id, int):
                acknowledged_offset = update_id + 1

        if acknowledged_offset is not None:
            try:
                self.offset_store.set_update_offset(acknowledged_offset)
            except Exception:
                logger.exception("Failed to update Telegram polling offset")

    async def _fetch_updates(self) -> list[dict]:
        """Fetch updates without opening a database session."""
        try:
            offset = self.offset_store.get_update_offset()
        except Exception:
            logger.exception("Failed to get Telegram polling offset")
            return []

        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                response = await client.get(
                    f"{self.base_url}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.RequestError as exc:
            logger.error("Failed to poll updates (network error): %s", exc)
            return []
        except Exception:
            logger.exception("Unexpected error during Telegram polling")
            return []

        if not isinstance(data, dict) or not data.get("ok"):
            logger.error("Telegram API error: %s", data)
            return []
        updates = data.get("result", [])
        return updates if isinstance(updates, list) else []

    async def _apply_command(self, update: dict, recall_service: "RecallService") -> CommandOutcome:
        """Apply one structurally valid command and prepare its messages."""
        message = update["message"]
        chat_id = message["chat"]["id"]
        username = message["from"]["username"]
        text_value = message.get("text", "")
        text = text_value.strip() if isinstance(text_value, str) else ""

        logger.info("Processing bot command '%s' from %s in chat %s", text, username, chat_id)

        if text == "/start":
            return await self._apply_start(recall_service, username, chat_id)

        normalized_username, state = await recall_service.get_state_for_telegram_username(username)
        if not normalized_username or state is None:
            logger.warning("Unauthorized user %s tried to access the bot", username)
            return self._message_outcome(chat_id, "Sorry, you are not authorized to use this bot.")

        if text == "/stop":
            await recall_service.disable_for_user(state.user_id, chat_id=state.telegram_chat_id)
            logger.info("User %s stopped the bot", normalized_username)
            return self._message_outcome(chat_id, "Bot stopped. You will no longer receive vocabulary words.")
        if text == "/remove":
            return await self._apply_remove(recall_service, message, state, chat_id)
        if text == "/postpone":
            return await self._apply_postpone(recall_service, message, state, chat_id)
        if text == "/state":
            return self._state_outcome(state, chat_id)
        if text == "/bump_words":
            return await self._apply_bump(recall_service, state, chat_id)

        logger.debug("Unknown command '%s' from user %s", text, normalized_username)
        return CommandOutcome(status="ignored")

    async def _apply_start(
        self,
        recall_service: "RecallService",
        username: str,
        chat_id: int,
    ) -> CommandOutcome:
        result = await recall_service.enable_for_username(username, chat_id)
        if result.status is RecallEnableStatus.INVALID_USERNAME:
            logger.warning("Cannot link Telegram user %s because its username is invalid", username)
            return self._message_outcome(chat_id, "Sorry, you are not authorized to use this bot.")
        if result.status is RecallEnableStatus.USER_NOT_FOUND:
            return self._message_outcome(
                chat_id,
                "I couldn't find a Runestone account linked to this Telegram username. "
                "Add your Telegram username in Profile, then send /start again.",
            )
        if result.status is RecallEnableStatus.USER_INACTIVE:
            return self._message_outcome(
                chat_id,
                "Your Runestone account is not active. Please contact an administrator.",
            )
        if (
            result.status is not RecallEnableStatus.ENABLED
            or result.normalized_username is None
            or result.user_id is None
        ):
            logger.error("Unexpected recall enable result status=%s", result.status)
            return self._generic_error_outcome(chat_id)
        if result.was_already_enabled:
            logger.info("Telegram user %s sent /start but recall was already enabled", result.normalized_username)
            return self._message_outcome(
                chat_id,
                "Bot is already active. You will continue receiving daily vocabulary words.",
            )

        logger.info("Linked Telegram user %s to Runestone user %s", result.normalized_username, result.user_id)
        return self._message_outcome(chat_id, "Bot started! You will receive daily vocabulary words.")

    async def _apply_remove(
        self,
        recall_service: "RecallService",
        message: dict,
        state: RecallState,
        chat_id: int,
    ) -> CommandOutcome:
        reply = message.get("reply_to_message")
        if not isinstance(reply, dict):
            return self._message_outcome(chat_id, "Please reply to a word message to remove it.")
        word_phrase = self._parse_word_from_reply_text(reply.get("text", ""))
        if not word_phrase:
            return self._message_outcome(chat_id, "Could not find a word to remove in the replied message.")
        await recall_service.remove_word_completely(state, word_phrase)
        return self._message_outcome(chat_id, f"Word '{word_phrase}' removed from vocabulary.")

    async def _apply_postpone(
        self,
        recall_service: "RecallService",
        message: dict,
        state: RecallState,
        chat_id: int,
    ) -> CommandOutcome:
        reply = message.get("reply_to_message")
        if not isinstance(reply, dict):
            return self._message_outcome(chat_id, "Please reply to a word message to postpone it.")
        word_phrase = self._parse_word_from_reply_text(reply.get("text", ""))
        if not word_phrase:
            return self._message_outcome(chat_id, "Could not find a word to postpone in the replied message.")
        await recall_service.postpone_word(state, word_phrase)
        return self._message_outcome(
            chat_id,
            f"Word '{word_phrase}' postponed (removed from today's selection).",
        )

    async def _apply_bump(
        self,
        recall_service: "RecallService",
        state: RecallState,
        chat_id: int,
    ) -> CommandOutcome:
        refreshed = await recall_service.bump_words(state.user_id)
        count = len(refreshed.daily_selection)
        if count:
            return self._message_outcome(
                chat_id,
                f"Daily selection updated! Selected {count} new words for today.",
            )
        return self._message_outcome(chat_id, "Daily selection cleared. No new words available at this time.")

    @staticmethod
    def _state_outcome(state: RecallState, chat_id: int) -> CommandOutcome:
        is_active_text = "✅ Yes" if state.is_enabled else "❌ No"
        words_list = (
            "\n".join(f"- {word.word_phrase}" for word in state.daily_selection)
            if state.daily_selection
            else "No words selected for today."
        )
        return TelegramCommandProcessor._message_outcome(
            chat_id,
            f"Current State\n\nIs Active: {is_active_text}\n\nDaily Selection:\n{words_list}",
        )

    def _application_error_outcome(self, update: dict, exc: Exception) -> CommandOutcome:
        """Translate a rolled-back non-retryable error into prior command UX."""
        message = update.get("message", {})
        chat = message.get("chat", {}) if isinstance(message, dict) else {}
        chat_id = chat.get("id") if isinstance(chat, dict) else None
        text = message.get("text", "") if isinstance(message, dict) else ""
        text = text.strip() if isinstance(text, str) else ""
        if not isinstance(chat_id, int):
            return CommandOutcome(status="handled")

        if isinstance(exc, TelegramUsernameConflictError):
            if text == "/start":
                return self._message_outcome(
                    chat_id,
                    "This Telegram username is linked to multiple Runestone accounts. "
                    "Please contact an administrator.",
                )
            return CommandOutcome(status="handled")
        if isinstance(exc, WordNotFoundError):
            return self._message_outcome(chat_id, f"Word '{exc.word_phrase}' not found in your vocabulary.")
        if isinstance(exc, WordNotInSelectionError):
            return self._message_outcome(chat_id, f"Word '{exc.word_phrase}' was not in today's selection.")
        if isinstance(exc, RecallOperationError) and text in {"/remove", "/postpone", "/bump_words"}:
            return self._message_outcome(chat_id, f"Error: {exc.message}")
        return self._generic_error_outcome(chat_id)

    async def _send_outcome_messages(self, outcome: CommandOutcome) -> None:
        for message in outcome.messages:
            try:
                sent = await self._send_message(message.chat_id, message.text, message.parse_mode)
            except Exception:
                logger.exception("Unexpected error sending Telegram command response to chat %s", message.chat_id)
                continue
            if not sent:
                logger.error("Failed to send Telegram command response to chat %s", message.chat_id)

    async def _send_message(self, chat_id: int, text: str, parse_mode: str | None = None) -> bool:
        """Send one prepared message after command transaction closure."""
        payload: dict[str, int | str] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{self.base_url}/sendMessage", json=payload)
                response.raise_for_status()
                return True
        except httpx.HTTPError as exc:
            logger.error("Failed to send message to chat %s: %s", chat_id, exc)
            return False

    @staticmethod
    def _message_outcome(chat_id: int, text: str, parse_mode: str | None = None) -> CommandOutcome:
        return CommandOutcome(
            status="handled",
            messages=(TelegramMessage(chat_id=chat_id, text=text, parse_mode=parse_mode),),
        )

    @staticmethod
    def _generic_error_outcome(chat_id: int) -> CommandOutcome:
        return TelegramCommandProcessor._message_outcome(
            chat_id,
            "Sorry, an error occurred while processing your command.",
        )

    @staticmethod
    def _parse_word_from_reply_text(reply_text: str) -> str | None:
        """Extract the Swedish word from a formatted recall message."""
        if not isinstance(reply_text, str) or not reply_text:
            return None
        match = re.search(r"🇸🇪\s+([^\n]+)", reply_text)
        if not match:
            return None
        word_phrase = match.group(1).strip()
        for marker in ("**", "__", "*", "_"):
            if word_phrase.startswith(marker) and word_phrase.endswith(marker):
                return word_phrase[len(marker) : -len(marker)].strip()
        return word_phrase

    @staticmethod
    def _is_relevant_command_update(update: dict) -> bool:
        message = update.get("message")
        if not isinstance(message, dict):
            return False
        chat = message.get("chat")
        sender = message.get("from")
        if not isinstance(chat, dict) or not isinstance(chat.get("id"), int):
            return False
        if not isinstance(sender, dict) or not sender.get("username"):
            return False
        text = message.get("text")
        if not isinstance(text, str) or text.strip() not in SUPPORTED_COMMANDS:
            return False
        entities = message.get("entities", [])
        return isinstance(entities, list) and any(
            isinstance(entity, dict) and entity.get("type") == "bot_command" for entity in entities
        )

    @staticmethod
    def _update_sort_key(update: dict) -> int:
        update_id = update.get("update_id")
        return update_id if isinstance(update_id, int) else -1

    @staticmethod
    def _contains_database_error(exc: BaseException) -> bool:
        """Recognize wrapped SQLAlchemy failures without guessing unknown errors."""
        pending: list[BaseException] = [exc]
        seen: set[int] = set()
        while pending:
            current = pending.pop()
            if id(current) in seen:
                continue
            seen.add(id(current))
            if isinstance(current, SQLAlchemyError):
                return True
            if current.__cause__ is not None:
                pending.append(current.__cause__)
            if current.__context__ is not None:
                pending.append(current.__context__)
        return False
