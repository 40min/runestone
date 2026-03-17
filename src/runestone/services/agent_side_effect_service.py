import logging

from sqlalchemy.exc import SQLAlchemyError

from runestone.agents.schemas import TeacherSideEffect
from runestone.db.agent_side_effect_repository import AgentSideEffectRepository

logger = logging.getLogger(__name__)


class AgentSideEffectService:
    """Service for teacher-facing loading and replacement of persisted specialist side effects."""

    RECENT_SIDE_EFFECT_LIMIT = 10

    def __init__(self, repository: AgentSideEffectRepository):
        self.repository = repository

    async def load_recent_for_teacher(self, user_id: int, chat_id: str) -> list[TeacherSideEffect]:
        try:
            records = await self.repository.get_recent_for_teacher(
                user_id=user_id,
                chat_id=chat_id,
                limit=self.RECENT_SIDE_EFFECT_LIMIT,
            )
        except (SQLAlchemyError, ValueError, RuntimeError) as e:
            logger.warning("[agents:side-effects] Failed to load recent side effects for user %s: %s", user_id, e)
            return []

        loaded = [
            TeacherSideEffect(
                name=record.specialist_name,
                phase=record.phase,
                status=record.status,
                info_for_teacher=record.info_for_teacher,
                artifacts=self.repository.deserialize_artifacts(record.artifacts_json),
                routing_reason=record.routing_reason or "",
                latency_ms=record.latency_ms,
                created_at=record.created_at,
            )
            for record in records
        ]
        if loaded:
            logger.info(
                "[agents:side-effects] Loaded recent side effects: user_id=%s chat_id=%s count=%s",
                user_id,
                chat_id,
                len(loaded),
            )
        return loaded

    async def replace_post_response_side_effects(self, user_id: int, chat_id: str, results: list[dict]) -> None:
        records = []
        for item in results:
            result = item.get("result", {}) if isinstance(item, dict) else {}
            records.append(
                {
                    "specialist_name": item.get("name", "unknown"),
                    "phase": "post_response",
                    "status": result.get("status", "unknown"),
                    "info_for_teacher": result.get("info_for_teacher", ""),
                    "artifacts": result.get("artifacts", {}),
                    "routing_reason": item.get("routing_reason", ""),
                    "latency_ms": item.get("latency_ms"),
                }
            )

        try:
            deleted_count = await self.repository.delete_for_chat_phase(
                user_id=user_id,
                chat_id=chat_id,
                phase="post_response",
                commit=False,
            )
            if records:
                await self.repository.add_many(
                    user_id=user_id,
                    chat_id=chat_id,
                    records=records,
                    commit=False,
                )
            await self.repository.db.commit()
            logger.info(
                "[agents:side-effects] Replaced post-response side effects: "
                "user_id=%s chat_id=%s deleted=%s inserted=%s",
                user_id,
                chat_id,
                deleted_count,
                len(records),
            )
        except (SQLAlchemyError, ValueError, RuntimeError) as e:
            await self.repository.db.rollback()
            logger.warning(
                "[agents:side-effects] Failed to replace post-response side effects for user %s chat %s: %s",
                user_id,
                chat_id,
                e,
            )
            raise
