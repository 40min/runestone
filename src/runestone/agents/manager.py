"""
Service layer for chat agent orchestration.
"""

import json
import logging
from typing import Optional
from urllib.parse import urlparse

from langchain_core.messages import ToolMessage
from sqlalchemy.exc import SQLAlchemyError

from runestone.agents.schemas import ChatMessage
from runestone.agents.specialists.teacher import TeacherAgent
from runestone.config import Settings
from runestone.core.exceptions import RunestoneError
from runestone.db.models import User
from runestone.rag.index import GrammarIndex
from runestone.services.grammar_service import GrammarService

logger = logging.getLogger(__name__)


class AgentsManager:
    """
    Service for managing chat agent interactions using specialist agents.

    All log lines should be prefixed with `[agents:manager]` for consistency.
    """

    def __init__(
        self,
        settings: Settings,
        grammar_index: GrammarIndex | None = None,
        grammar_service: GrammarService | None = None,
    ):
        """
        Initialize the agent manager.
        """
        self.settings = settings
        self._init_allowed_ports()
        self.teacher = TeacherAgent(
            settings=settings,
            grammar_index=grammar_index,
            grammar_service=grammar_service,
        )

        logger.info(
            "[agents:manager] Initialized AgentsManager with provider=%s, model=%s, persona=%s",
            settings.chat_provider,
            settings.chat_model,
            settings.agent_persona,
        )

    def _init_allowed_ports(self):
        self.allowed_ports = {80, 443}
        try:
            for origin in self.settings.allowed_origins.split(","):
                app_parsed = urlparse(origin.strip())
                if app_parsed.port:
                    self.allowed_ports.add(app_parsed.port)
        except (ValueError, AttributeError) as e:
            logger.warning("[agents:manager] Configuration issue with allowed_origins: %s", e)

    async def generate_response(
        self,
        message: str,
        history: list[ChatMessage],
        user: User,
        memory_item_service,
    ) -> tuple[str, Optional[list[dict[str, str]]]]:
        """
        Generate a response to a user message using the teacher specialist.
        """
        if not history:
            try:
                deleted_count = await memory_item_service.cleanup_old_mastered_areas(user.id, older_than_days=90)
                if deleted_count:
                    logger.info("Cleaned up %s old mastered memory items for user %s", deleted_count, user.id)
            except (SQLAlchemyError, ValueError, RuntimeError) as e:
                logger.warning("Failed to cleanup old mastered memory items for user %s: %s", user.id, e)

        try:
            result = await self.teacher.generate_response(
                message=message,
                history=history,
                user=user,
            )
        except (RunestoneError, ValueError, RuntimeError) as e:
            logger.error("[agents:manager] Error generating response: %s", e)
            raise

        response = result.artifacts.get("response", "I'm sorry, I couldn't generate a response.")
        final_messages = result.artifacts.get("final_messages") or []
        sources = self._extract_sources(final_messages)
        return response, sources

    @staticmethod
    def _safe_json_loads(payload):
        if isinstance(payload, dict):
            return payload
        if not isinstance(payload, str):
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def _extract_sources(self, messages) -> Optional[list[dict[str, str]]]:

        for msg in reversed(messages):
            if not isinstance(msg, ToolMessage):
                continue
            payload = self._safe_json_loads(msg.content)
            tool_name = payload.get("tool") if isinstance(payload, dict) else None
            if not payload or tool_name not in ["search_news_with_dates", "search_grammar"]:
                continue
            if payload.get("error"):
                return None
            results = payload.get("results")
            if not isinstance(results, list):
                return None

            sources: list[dict[str, str]] = []
            seen_urls = set()
            for item in results:
                if not isinstance(item, dict):
                    continue
                title = item.get("title")
                url = item.get("url")
                date = item.get("date", "")  # Date is optional for grammar
                if not title or not url:
                    continue
                if not self._is_safe_url(url):
                    continue
                if url in seen_urls:
                    continue
                sources.append({"title": title, "url": url, "date": date})
                seen_urls.add(url)

            return sources or None

        return None

    def _is_safe_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
        except ValueError:
            logger.info("[agents:manager] Rejected source URL (parse error): %s", url)
            return False
        if parsed.username or parsed.password:
            logger.info("[agents:manager] Rejected source URL (credentials not allowed): %s", url)
            return False
        try:
            port = parsed.port
        except ValueError:
            logger.info("[agents:manager] Rejected source URL (invalid port): %s", url)
            return False
        if parsed.scheme not in {"http", "https"}:
            logger.info("[agents:manager] Rejected source URL (scheme not allowed): %s", url)
            return False

        if port is not None and port not in self.allowed_ports:
            logger.info("[agents:manager] Rejected source URL (port not allowed): %s", url)
            return False
        if not parsed.netloc:
            logger.info("[agents:manager] Rejected source URL (missing netloc): %s", url)
            return False
        return True
