"""
Service layer for chat agent orchestration.
"""

import asyncio
import json
import logging
import time
from typing import Optional
from urllib.parse import parse_qs, urlparse

from langchain_core.messages import ToolMessage
from sqlalchemy.exc import SQLAlchemyError

from runestone.agents.background_task_registry import BackgroundTaskRegistry
from runestone.agents.coordinator import CoordinatorAgent
from runestone.agents.schemas import ChatMessage, CoordinatorPlan, RoutingItem, TeacherEmotion, TeacherSideEffect
from runestone.agents.service_providers import provide_agent_side_effect_service
from runestone.agents.specialists.base import SpecialistContext
from runestone.agents.specialists.memory_keeper import MemoryKeeperSpecialist
from runestone.agents.specialists.news_agent import NewsAgentSpecialist
from runestone.agents.specialists.registry import SpecialistRegistry
from runestone.agents.specialists.teacher import TeacherAgent
from runestone.agents.specialists.word_keeper import WordKeeperSpecialist
from runestone.agents.tools.utils import serialize_memory_items
from runestone.config import Settings
from runestone.constants import MAX_TEACHER_GRAMMAR_SOURCE_LINKS
from runestone.core.exceptions import RunestoneError
from runestone.core.observability import elapsed_ms_since
from runestone.db.models import User
from runestone.rag.index import GrammarIndex
from runestone.schemas.vocabulary_save import WordSaveCandidate
from runestone.services.agent_side_effect_service import AgentSideEffectService
from runestone.services.grammar_service import GrammarService

logger = logging.getLogger(__name__)


class AgentsManager:
    """
    Service for managing chat agent interactions using specialist agents.

    All log lines should be prefixed with `[agents:manager]` for consistency.
    """

    COORDINATOR_MAX_HISTORY_MESSAGES = 5
    POST_TASK_TIMEOUT_SECONDS = 15
    STARTER_MEMORY_PERSONAL_LIMIT = 50
    STARTER_MEMORY_AREA_LIMIT = 5

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
        self.registry.register(MemoryKeeperSpecialist(settings))
        self.registry.register(NewsAgentSpecialist(settings))
        self.registry.register(WordKeeperSpecialist(settings))

        self._post_task_registry = BackgroundTaskRegistry(logger=logger, key_name="chat_id")

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

    # ------------------------------------------------------------------
    # Phase methods (public, individually testable)
    # ------------------------------------------------------------------

    async def prepare_pre_turn(
        self,
        message: str,
        chat_id: str,
        history: list[ChatMessage],
        user: User,
        memory_item_service,
        side_effect_service: AgentSideEffectService,
    ) -> tuple[CoordinatorPlan, list[dict], str, list[TeacherSideEffect]]:
        """
        Run pre-stage: coordinator planning, pre specialists, side effect loading.

        Returns:
            (plan, pre_results, starter_memory, recent_side_effects)
        """
        starter_memory = ""
        if not history:
            try:
                deleted_count = await memory_item_service.cleanup_old_mastered_areas(
                    user.id,
                    older_than_days=self.settings.memory_mastered_cleanup_days,
                )
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
            try:
                starter_items = await memory_item_service.list_start_student_info_items(
                    user.id,
                    personal_limit=self.STARTER_MEMORY_PERSONAL_LIMIT,
                    area_limit=self.STARTER_MEMORY_AREA_LIMIT,
                )
                if starter_items:
                    starter_memory = serialize_memory_items(starter_items)
            except (SQLAlchemyError, ValueError, RuntimeError) as e:
                logger.warning("[agents:manager] Failed to load starter memory for user %s: %s", user.id, e)

        coordinator_history = history[-self.COORDINATOR_MAX_HISTORY_MESSAGES :] if history else []
        if history and len(history) > self.COORDINATOR_MAX_HISTORY_MESSAGES:
            logger.warning(
                "[agents:manager] Truncated coordinator history from %s to %s messages",
                len(history),
                len(coordinator_history),
            )
        plan: CoordinatorPlan | None = None
        try:
            plan = await self.coordinator.plan_pre_turn(
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

        return plan, pre_results, starter_memory, recent_side_effects

    async def generate_teacher_response(
        self,
        message: str,
        history: list[ChatMessage],
        user: User,
        pre_results: list[dict],
        starter_memory: str,
        recent_side_effects: list[TeacherSideEffect],
    ) -> tuple[str, Optional[list[dict[str, str]]], TeacherEmotion, list[WordSaveCandidate]]:
        """
        Run teacher agent synchronously and return visible response data plus vocabulary candidates.
        """
        try:
            generated = await self.teacher.generate_response(
                message=message,
                history=history,
                user=user,
                pre_results=pre_results,
                starter_memory=starter_memory,
                recent_side_effects=recent_side_effects,
            )
        except (RunestoneError, ValueError, RuntimeError) as e:
            logger.error("[agents:manager] Error generating response: %s", e)
            raise

        sources = self._extract_sources(
            pre_results=pre_results,
            messages=generated.final_messages,
            grammar_source_urls=generated.grammar_source_urls,
        )
        return generated.message, sources, generated.emotion, generated.vocabulary_candidates

    async def process_turn(
        self,
        message: str,
        chat_id: str,
        history: list[ChatMessage],
        user: User,
        memory_item_service,
        side_effect_service: AgentSideEffectService,
    ) -> tuple[str, Optional[list[dict[str, str]]], TeacherEmotion]:
        """
        Run the agent-owned portion of a prepared chat turn.

        The caller is responsible for message/session persistence before this call:
        - user message already saved when applicable
        - history already loaded
        - user already resolved

        The caller also remains responsible for chat delivery concerns after this call:
        - persisting the assistant message
        - optional TTS push to the client
        """
        if history:
            await self.handle_stale_post_task(
                user_id=user.id,
                chat_id=chat_id,
                side_effect_service=side_effect_service,
            )

        _plan, pre_results, starter_memory, recent_side_effects = await self.prepare_pre_turn(
            message=message,
            chat_id=chat_id,
            history=history,
            user=user,
            memory_item_service=memory_item_service,
            side_effect_service=side_effect_service,
        )

        assistant_text, sources, teacher_emotion, vocabulary_candidates = await self.generate_teacher_response(
            message=message,
            history=history,
            user=user,
            pre_results=pre_results,
            starter_memory=starter_memory,
            recent_side_effects=recent_side_effects,
        )

        coordinator_row_id = await side_effect_service.create_post_coordinator_row(
            user_id=user.id,
            chat_id=chat_id,
        )

        await self.start_background_post_turn(
            message=message,
            chat_id=chat_id,
            history=history,
            user=user,
            teacher_response=assistant_text,
            vocabulary_candidates=vocabulary_candidates,
            pre_results=pre_results,
            coordinator_row_id=coordinator_row_id,
        )

        return assistant_text, sources, teacher_emotion

    async def run_post_turn(
        self,
        message: str,
        chat_id: str,
        history: list[ChatMessage],
        user: User,
        teacher_response: str,
        vocabulary_candidates: list[WordSaveCandidate] | None,
        pre_results: list[dict],
        side_effect_service: AgentSideEffectService,
        coordinator_row_id: int,
    ) -> None:
        """
        Run post-stage: post specialists and persist side effects.

        Called from within a background asyncio.Task. Updates coordinator tracking row.
        """
        await side_effect_service.mark_coordinator_running(coordinator_row_id)

        try:
            post_results, coordinator_failed = await self._run_post_branches(
                message=message,
                history=history,
                user=user,
                teacher_response=teacher_response,
                vocabulary_candidates=vocabulary_candidates or [],
                pre_results=pre_results,
            )
            persisted = await side_effect_service.replace_post_specialist_results(
                user_id=user.id,
                chat_id=chat_id,
                results=post_results,
                coordinator_row_id=coordinator_row_id,
            )
            if not persisted:
                logger.warning(
                    "[agents:manager] Skipped stale post-turn persistence: user_id=%s chat_id=%s row_id=%s",
                    user.id,
                    chat_id,
                    coordinator_row_id,
                )
                return
            if coordinator_failed:
                await side_effect_service.mark_coordinator_failed_if_current(
                    row_id=coordinator_row_id,
                    user_id=user.id,
                    chat_id=chat_id,
                )
                logger.warning(
                    "[agents:manager] Post-turn completed with coordinator failure: user_id=%s chat_id=%s",
                    user.id,
                    chat_id,
                )
                return
            await side_effect_service.mark_coordinator_done_if_current(
                row_id=coordinator_row_id,
                user_id=user.id,
                chat_id=chat_id,
            )
            logger.info("[agents:manager] Post-turn completed: user_id=%s chat_id=%s", user.id, chat_id)
        except Exception:
            logger.error("[agents:manager] Post-turn failed: user_id=%s chat_id=%s", user.id, chat_id, exc_info=True)
            await side_effect_service.mark_coordinator_failed_if_current(
                row_id=coordinator_row_id,
                user_id=user.id,
                chat_id=chat_id,
            )
            raise

    async def _run_post_branches(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        user: User,
        teacher_response: str,
        vocabulary_candidates: list[WordSaveCandidate],
        pre_results: list[dict],
    ) -> tuple[list[dict], bool]:
        filtered_vocabulary_candidates = self._filter_post_vocabulary_candidates(
            vocabulary_candidates,
            pre_results=pre_results,
        )

        async def _coordinator_branch() -> list[dict]:
            coordinator_history = history[-self.COORDINATOR_MAX_HISTORY_MESSAGES :] if history else []
            if history and len(history) > self.COORDINATOR_MAX_HISTORY_MESSAGES:
                logger.warning(
                    "[agents:manager] Truncated coordinator history from %s to %s messages",
                    len(history),
                    len(coordinator_history),
                )

            plan = await self.coordinator.plan_post_turn(
                message=message,
                history=coordinator_history,
                teacher_response=teacher_response,
                available_specialists=[
                    name for name in self.registry.list_names() if name not in {"teacher", "word_keeper"}
                ],
            )
            post_items = [item for item in plan.post_response if item.name != "word_keeper"]
            logger.info(
                "[agents:manager] Post-phase selection: user_id=%s specialists=%s",
                user.id,
                ",".join([item.name for item in post_items]) if post_items else "none",
            )
            return await self._run_specialists(
                post_items,
                message=message,
                history=history,
                user=user,
                teacher_response=teacher_response,
                pre_results=pre_results,
            )

        async def _word_keeper_branch() -> list[dict]:
            if not filtered_vocabulary_candidates:
                return []
            return await self._run_specialists(
                [
                    RoutingItem(
                        name="word_keeper",
                        reason="teacher emitted vocabulary_candidates",
                        chat_history_size=0,
                    )
                ],
                message=message,
                history=history,
                user=user,
                teacher_response=teacher_response,
                vocabulary_candidates=filtered_vocabulary_candidates,
                pre_results=pre_results,
            )

        coordinator_results, word_keeper_results = await asyncio.gather(
            _coordinator_branch(),
            _word_keeper_branch(),
            return_exceptions=True,
        )

        post_results: list[dict] = []
        coordinator_failed = False
        if isinstance(coordinator_results, Exception):
            coordinator_failed = True
            logger.error(
                "[agents:manager] Coordinator post branch failed",
                exc_info=(type(coordinator_results), coordinator_results, coordinator_results.__traceback__),
            )
        else:
            post_results.extend(coordinator_results)

        if isinstance(word_keeper_results, Exception):
            logger.error(
                "[agents:manager] Direct WordKeeper post branch failed",
                exc_info=(type(word_keeper_results), word_keeper_results, word_keeper_results.__traceback__),
            )
        else:
            post_results.extend(word_keeper_results)

        return post_results, coordinator_failed

    # ------------------------------------------------------------------
    # Background task registry
    # ------------------------------------------------------------------

    def _register_post_task(self, chat_id: str, task: asyncio.Task) -> None:
        self._post_task_registry.register(chat_id, task)

    def _unregister_post_task(self, chat_id: str) -> None:
        self._post_task_registry.unregister(chat_id)

    def cancel_post_task(self, chat_id: str) -> bool:
        """Cancel any live background post task for chat_id. Returns True if a task was cancelled."""
        return self._post_task_registry.cancel(chat_id)

    async def start_background_post_turn(
        self,
        message: str,
        chat_id: str,
        history: list[ChatMessage],
        user: User,
        teacher_response: str,
        vocabulary_candidates: list[WordSaveCandidate] | None,
        pre_results: list[dict],
        coordinator_row_id: int,
    ) -> None:
        """
        Fire-and-forget: wrap run_post_turn in a timeout and register the task handle.
        """

        async def _run():
            try:
                async with provide_agent_side_effect_service() as background_side_effect_service:
                    try:
                        await asyncio.wait_for(
                            self.run_post_turn(
                                message=message,
                                chat_id=chat_id,
                                history=history,
                                user=user,
                                teacher_response=teacher_response,
                                vocabulary_candidates=vocabulary_candidates or [],
                                pre_results=pre_results,
                                side_effect_service=background_side_effect_service,
                                coordinator_row_id=coordinator_row_id,
                            ),
                            timeout=self.POST_TASK_TIMEOUT_SECONDS,
                        )
                    except asyncio.TimeoutError:
                        logger.error(
                            "[agents:post-task] Post task timed out after %ss: chat_id=%s",
                            self.POST_TASK_TIMEOUT_SECONDS,
                            chat_id,
                        )
                        await background_side_effect_service.mark_coordinator_failed_if_current(
                            row_id=coordinator_row_id,
                            user_id=user.id,
                            chat_id=chat_id,
                        )
                    except asyncio.CancelledError:
                        logger.info("[agents:post-task] Post task cancelled: chat_id=%s", chat_id)
                        await background_side_effect_service.mark_coordinator_failed_if_current(
                            row_id=coordinator_row_id,
                            user_id=user.id,
                            chat_id=chat_id,
                        )
            finally:
                self._unregister_post_task(chat_id)

        task = asyncio.create_task(_run())
        self._register_post_task(chat_id, task)
        logger.info(
            "[agents:post-task] Background task started: chat_id=%s timeout=%ss",
            chat_id,
            self.POST_TASK_TIMEOUT_SECONDS,
        )

    async def handle_stale_post_task(
        self,
        *,
        user_id: int,
        chat_id: str,
        side_effect_service: AgentSideEffectService,
    ) -> None:
        """
        Next-turn check: inspect the previous post coordinator row for this chat.
        Cancel any live background task and mark stale rows as failed.
        """
        coordinator_row = await side_effect_service.load_latest_coordinator_row(user_id=user_id, chat_id=chat_id)
        if coordinator_row is None or coordinator_row.status == "done":
            return

        logger.warning(
            "[agents:post-task] Stale post coordinator row detected: chat_id=%s status=%s — cancelling",
            chat_id,
            coordinator_row.status,
        )

        self.cancel_post_task(chat_id)

        try:
            await side_effect_service.mark_coordinator_failed_if_current(
                row_id=coordinator_row.id,
                user_id=user_id,
                chat_id=chat_id,
            )
        except Exception:
            logger.warning(
                "[agents:post-task] Failed to mark stale coordinator row as failed: chat_id=%s",
                chat_id,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_specialists(
        self,
        routing_items: list[RoutingItem],
        *,
        message: str,
        history: list[ChatMessage],
        user: User,
        teacher_response: str | None = None,
        vocabulary_candidates: list[WordSaveCandidate] | None = None,
        pre_results: list[dict] | None = None,
    ) -> list[dict]:
        if not routing_items:
            return []

        previous_teacher_message = self._previous_teacher_message(history)

        async def _invoke(item, specialist):
            started = time.monotonic()
            effective_history_size = item.chat_history_size
            if item.name == "word_keeper":
                effective_history_size = 0

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
                teacher_response=(
                    None
                    if item.name == "word_keeper" and vocabulary_candidates
                    else previous_teacher_message if item.name == "word_keeper" else teacher_response
                ),
                vocabulary_candidates=vocabulary_candidates or [],
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
    def _previous_teacher_message(history: list[ChatMessage]) -> str | None:
        """Return the immediately preceding assistant message only when it is adjacent."""
        if not history:
            return None
        item = history[-1]
        if item.role == "assistant" and item.content:
            return item.content
        return None

    @classmethod
    def _filter_post_vocabulary_candidates(
        cls,
        candidates: list[WordSaveCandidate],
        *,
        pre_results: list[dict],
    ) -> list[WordSaveCandidate]:
        """Drop teacher candidates that were already saved by pre-response WordKeeper this turn."""
        if not candidates:
            return []

        previously_saved = cls._pre_saved_word_keys(pre_results)
        if not previously_saved:
            return candidates

        return [
            candidate
            for candidate in candidates
            if (dedupe_key := cls._normalize_word_key(candidate.word_phrase)) and dedupe_key not in previously_saved
        ]

    @classmethod
    def _pre_saved_word_keys(cls, pre_results: list[dict]) -> set[str]:
        """Collect normalized word keys already saved by pre-response WordKeeper artifacts."""
        keys: set[str] = set()
        for item in pre_results:
            if item.get("name") != "word_keeper":
                continue
            result = item.get("result")
            if not isinstance(result, dict):
                continue
            artifacts = result.get("artifacts")
            if not isinstance(artifacts, dict):
                continue

            for word in artifacts.get("saved_words", []):
                key = cls._normalize_word_key(word)
                if key:
                    keys.add(key)

        return keys

    @staticmethod
    def _normalize_word_key(word_phrase: object) -> str:
        """Mirror VocabularyService priority-candidate dedupe for manager-level routing guards."""
        if not isinstance(word_phrase, str):
            return ""
        return word_phrase.strip().casefold()

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

    def _extract_sources(
        self,
        *,
        pre_results: list[dict] | None = None,
        messages=None,
        grammar_source_urls: list[str] | None = None,
    ) -> Optional[list[dict[str, str]]]:
        specialist_sources = self._extract_pre_result_sources(pre_results or [])
        merged_sources: list[dict[str, str]] = specialist_sources[:] if specialist_sources else []
        seen_urls = {source["url"] for source in merged_sources}
        grammar_result_urls = self._extract_search_grammar_result_urls(messages or [])
        grammar_sources = self._extract_grammar_sources(grammar_source_urls or [], grammar_result_urls, seen_urls)
        merged_sources.extend(grammar_sources)

        for msg in reversed(messages or []):
            if not isinstance(msg, ToolMessage):
                continue
            payload = self._safe_json_loads(msg.content)
            tool_name = payload.get("tool") if isinstance(payload, dict) else None
            if not payload or tool_name != "search_news_with_dates":
                continue
            if payload.get("error"):
                return None
            results = payload.get("results")
            if not isinstance(results, list):
                return None

            sources: list[dict[str, str]] = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                title = item.get("title")
                url = item.get("url")
                date = item.get("date", "")
                if not title or not url:
                    continue
                if not self._is_safe_url(url):
                    continue
                if url in seen_urls:
                    continue
                sources.append({"title": title, "url": url, "date": date})
                seen_urls.add(url)

            merged_sources.extend(sources)
            return merged_sources or None

        return merged_sources or None

    def _extract_grammar_sources(
        self,
        grammar_source_urls: list[str],
        allowed_urls: set[str],
        seen_urls: set[str],
    ) -> list[dict[str, str]]:
        """Return grammar references explicitly selected by the Teacher response."""
        sources: list[dict[str, str]] = []
        for url in grammar_source_urls:
            if url not in allowed_urls:
                logger.info("[agents:manager] Rejected grammar source URL (not returned by search_grammar): %s", url)
                continue
            if url in seen_urls:
                logger.info("[agents:manager] Rejected grammar source URL (duplicate): %s", url)
                continue
            if not self._is_safe_url(url):
                logger.info("[agents:manager] Rejected grammar source URL (unsafe): %s", url)
                continue
            sources.append({"title": self._format_grammar_source_title(url), "url": url, "date": ""})
            seen_urls.add(url)
            if len(sources) == MAX_TEACHER_GRAMMAR_SOURCE_LINKS:
                break
        return sources

    def _extract_search_grammar_result_urls(self, messages) -> set[str]:
        """Return exact grammar URLs produced by search_grammar during this teacher turn."""
        urls: set[str] = set()
        for msg in messages or []:
            if not isinstance(msg, ToolMessage):
                continue
            payload = self._safe_json_loads(msg.content)
            tool_name = payload.get("tool") if isinstance(payload, dict) else None
            if tool_name != "search_grammar":
                continue
            results = payload.get("results")
            if not isinstance(results, list):
                continue
            for item in results:
                if not isinstance(item, dict):
                    continue
                raw_url = item.get("url")
                if isinstance(raw_url, str) and raw_url:
                    urls.add(raw_url)
        return urls

    @staticmethod
    def _format_grammar_source_title(url: str) -> str:
        """Build a compact display title from a grammar reference URL."""
        parsed = urlparse(url)
        cheatsheet_paths = parse_qs(parsed.query).get("cheatsheet", [])
        raw_title = cheatsheet_paths[0] if cheatsheet_paths else parsed.path.rsplit("/", 1)[-1]
        title = raw_title.replace("/", " / ").replace("-", " ").replace("_", " ").strip()
        return title.title() or parsed.netloc or url

    def _extract_pre_result_sources(self, pre_results: list[dict]) -> Optional[list[dict[str, str]]]:
        sources: list[dict[str, str]] = []
        seen_urls = set()
        for item in pre_results:
            if not isinstance(item, dict) or item.get("name") != "news_agent":
                continue
            result = item.get("result")
            if not isinstance(result, dict):
                continue
            artifacts = result.get("artifacts")
            if not isinstance(artifacts, dict):
                continue
            artifact_sources = artifacts.get("sources")
            if not isinstance(artifact_sources, list):
                continue
            for source in artifact_sources:
                if not isinstance(source, dict):
                    continue
                title = source.get("title")
                raw_url = source.get("url")
                url = str(raw_url) if raw_url else None
                date = source.get("date", "")
                if not title or not url or not self._is_safe_url(url) or url in seen_urls:
                    continue
                sources.append({"title": title, "url": url, "date": date})
                seen_urls.add(url)
        return sources or None

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
