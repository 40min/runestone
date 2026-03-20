"""
Service layer for chat agent orchestration.
"""

import asyncio
import json
import logging
import time
from typing import Optional
from urllib.parse import urlparse

from langchain_core.messages import ToolMessage
from sqlalchemy.exc import SQLAlchemyError

from runestone.agents.coordinator import CoordinatorAgent
from runestone.agents.schemas import ChatMessage, CoordinatorPlan, RoutingItem
from runestone.agents.specialists.base import SpecialistContext

# from runestone.agents.specialists.memory_reader import MemoryReaderSpecialist
from runestone.agents.specialists.registry import SpecialistRegistry
from runestone.agents.specialists.teacher import TeacherAgent
from runestone.agents.specialists.word_keeper import WordKeeperSpecialist
from runestone.config import Settings
from runestone.core.exceptions import RunestoneError
from runestone.core.observability import elapsed_ms_since
from runestone.db.models import User
from runestone.rag.index import GrammarIndex
from runestone.services.agent_side_effect_service import AgentSideEffectService
from runestone.services.grammar_service import GrammarService

logger = logging.getLogger(__name__)


class AgentsManager:
    """
    Service for managing chat agent interactions using specialist agents.

    All log lines should be prefixed with `[agents:manager]` for consistency.
    """

    COORDINATOR_MAX_HISTORY_MESSAGES = 5
    WORD_KEEPER_MAX_HISTORY_MESSAGES = 2

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
        self.coordinator = CoordinatorAgent(settings=settings)
        self.teacher = TeacherAgent(
            settings=settings,
            grammar_index=grammar_index,
            grammar_service=grammar_service,
        )
        self.registry = SpecialistRegistry()
        # todo: enable memory reader after we finish memory tools
        # migrations to agents
        # self.registry.register(MemoryReaderSpecialist())
        self.registry.register(WordKeeperSpecialist(settings))

        logger.info(
            "[agents:manager] Initialized AgentsManager with provider=%s, model=%s, persona=%s",
            settings.teacher_provider,
            settings.teacher_model,
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
        chat_id: str,
        history: list[ChatMessage],
        user: User,
        memory_item_service,
        side_effect_service: AgentSideEffectService,
    ) -> tuple[str, Optional[list[dict[str, str]]]]:
        """
        Generate a response to a user message using the teacher specialist.
        """
        if not history:
            try:
                deleted_count = await memory_item_service.cleanup_old_mastered_areas(user.id, older_than_days=90)
                if deleted_count:
                    logger.info(
                        "[agents:manager] Cleaned up %s old mastered memory items for user %s",
                        deleted_count,
                        user.id,
                    )
            except (SQLAlchemyError, ValueError, RuntimeError) as e:
                logger.warning(
                    "[agents:manager] Failed to cleanup old mastered memory items for user %s: %s", user.id, e
                )

        coordinator_history = history[-self.COORDINATOR_MAX_HISTORY_MESSAGES :] if history else []
        if history and len(history) > self.COORDINATOR_MAX_HISTORY_MESSAGES:
            logger.warning(
                "[agents:manager] Truncated coordinator history from %s to %s messages",
                len(history),
                len(coordinator_history),
            )
        plan = None
        try:
            plan = await self.coordinator.plan(
                message=message,
                history=coordinator_history,
                available_specialists=[name for name in self.registry.list_names() if name != "teacher"],
            )
        except (RunestoneError, ValueError, RuntimeError) as e:
            logger.error("[agents:manager] Coordinator failed, falling back to teacher only: %s", e)

        if plan is None:
            plan = CoordinatorPlan(
                pre_response=[],
                post_response=[],
                audit={"fallback": "coordinator_error"},
            )
        logger.info(
            "[agents:manager] Pre-phase selection: user_id=%s specialists=%s",
            user.id,
            ",".join([item.name for item in plan.pre_response]) if plan.pre_response else "none",
        )

        pre_results = await self._run_specialists(
            plan.pre_response,
            message=message,
            history=history,
            user=user,
        )
        recent_side_effects = await side_effect_service.load_recent_for_teacher(
            user_id=user.id,
            chat_id=chat_id,
        )

        try:
            teacher_response, final_messages = await self.teacher.generate_response(
                message=message,
                history=history,
                user=user,
                pre_results=pre_results,
                recent_side_effects=recent_side_effects,
            )
        except (RunestoneError, ValueError, RuntimeError) as e:
            logger.error("[agents:manager] Error generating response: %s", e)
            raise

        logger.info(
            "[agents:manager] Post-phase selection: user_id=%s specialists=%s",
            user.id,
            ",".join([item.name for item in plan.post_response]) if plan.post_response else "none",
        )
        post_results = await self._run_specialists(
            plan.post_response,
            message=message,
            history=history,
            user=user,
            teacher_response=teacher_response,
            pre_results=pre_results,
        )
        await side_effect_service.replace_post_response_side_effects(
            user_id=user.id,
            chat_id=chat_id,
            results=post_results,
        )

        response = teacher_response
        sources = self._extract_sources(final_messages)
        return response, sources

    async def _run_specialists(
        self,
        routing_items: list[RoutingItem],
        *,
        message: str,
        history: list[ChatMessage],
        user: User,
        teacher_response: str | None = None,
        pre_results: list[dict] | None = None,
    ) -> list[dict]:
        if not routing_items:
            return []

        async def _invoke(item, specialist):
            started = time.monotonic()
            effective_history_size = item.chat_history_size
            if item.name == "word_keeper":
                effective_history_size = min(item.chat_history_size, self.WORD_KEEPER_MAX_HISTORY_MESSAGES)
                if item.chat_history_size != effective_history_size:
                    logger.warning(
                        "[agents:manager] Capped specialist history for '%s' from %s to %s messages",
                        item.name,
                        item.chat_history_size,
                        effective_history_size,
                    )

            history_window = history[-effective_history_size:] if effective_history_size else []
            if effective_history_size and len(history) > effective_history_size:
                logger.warning(
                    "[agents:manager] Truncated specialist history for '%s' from %s to %s messages",
                    item.name,
                    len(history),
                    len(history_window),
                )
            context = SpecialistContext(
                message=message,
                history=history_window,
                user=user,
                teacher_response=teacher_response,
                pre_results=pre_results or [],
                routing_reason=item.reason,
                chat_history_size=effective_history_size,
            )
            try:
                result = await specialist.run(context)
                latency_ms = elapsed_ms_since(started)
                logger.info(
                    "[agents:%s] Result: status=%s latency_ms=%s",
                    item.name,
                    result.status,
                    latency_ms,
                )
                if result.artifacts and isinstance(result.artifacts, dict):
                    try:
                        artifacts_json = json.dumps(result.artifacts, ensure_ascii=False, default=str)
                    except (TypeError, ValueError):
                        artifacts_json = repr(result.artifacts)
                    logger.info("[agents:%s] Artifacts: %s", item.name, artifacts_json)
                return {
                    "name": item.name,
                    "result": result.model_dump(),
                    "latency_ms": latency_ms,
                    "routing_reason": item.reason,
                }
            except Exception:
                latency_ms = elapsed_ms_since(started)
                logger.warning("[agents:manager] Specialist '%s' failed", item.name, exc_info=True)
                return {
                    "name": item.name,
                    # Avoid feeding verbose/technical error details back into the teacher context.
                    "result": {"status": "error", "info_for_teacher": ""},
                    "latency_ms": latency_ms,
                    "routing_reason": item.reason,
                }

        tasks = []
        for item in routing_items:
            specialist = self.registry.get(item.name)
            if specialist is None:
                logger.info("[agents:manager] Missing specialist '%s' - skipping", item.name)
                continue
            logger.info("[agents:manager] Running specialist '%s' reason=%s", item.name, item.reason)
            tasks.append(_invoke(item, specialist))

        if not tasks:
            return []

        # Fan-out / fan-in: run specialists concurrently but preserve routing order.
        return await asyncio.gather(*tasks)

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
