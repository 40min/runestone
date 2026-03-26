import logging

from sqlalchemy.exc import SQLAlchemyError

from runestone.agents.schemas import TeacherSideEffect
from runestone.db.agent_side_effect_repository import AgentSideEffectRepository

logger = logging.getLogger(__name__)


class AgentSideEffectService:
    """Service for coordinator tracking rows and specialist side effect persistence."""

    RECENT_SIDE_EFFECT_LIMIT = 10

    def __init__(self, repository: AgentSideEffectRepository):
        self.repository = repository

    # ------------------------------------------------------------------
    # Teacher-facing loading
    # ------------------------------------------------------------------

    async def load_recent_for_teacher(self, user_id: int, chat_id: str) -> list[TeacherSideEffect]:
        """Load recent successful specialist results for teacher context. Excludes coordinator rows."""
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
            logger.debug(
                "[agents:side-effects] Loaded recent side effects: user_id=%s chat_id=%s count=%s",
                user_id,
                chat_id,
                len(loaded),
            )
        return loaded

    # ------------------------------------------------------------------
    # Coordinator tracking row lifecycle
    # ------------------------------------------------------------------

    async def create_post_coordinator_row(self, user_id: int, chat_id: str) -> int:
        """Create a pending coordinator row and return its id."""
        try:
            # Clean up old coordinator rows before creating a fresh one.
            deleted = await self.repository.delete_coordinator_rows(user_id=user_id, chat_id=chat_id, commit=False)
            await self.repository.db.commit()
            if deleted:
                logger.debug(
                    "[agents:side-effects] Cleaned up %s old coordinator rows: user_id=%s chat_id=%s",
                    deleted,
                    user_id,
                    chat_id,
                )
            row = await self.repository.create_coordinator_row(user_id=user_id, chat_id=chat_id, status="pending")
            logger.debug(
                "[agents:side-effects] Coordinator row created: user_id=%s chat_id=%s row_id=%s",
                user_id,
                chat_id,
                row.id,
            )
            return row.id
        except (SQLAlchemyError, ValueError, RuntimeError) as e:
            logger.warning(
                "[agents:side-effects] Failed to create coordinator row for user %s chat %s: %s",
                user_id,
                chat_id,
                e,
            )
            raise

    async def mark_coordinator_running(self, row_id: int) -> None:
        await self._update_status(row_id, "running")

    async def mark_coordinator_done(self, row_id: int) -> None:
        await self._update_status(row_id, "done")
        logger.debug("[agents:side-effects] Coordinator row marked done: row_id=%s", row_id)

    async def mark_coordinator_failed(self, row_id: int) -> None:
        await self._update_status(row_id, "failed")
        logger.warning("[agents:side-effects] Coordinator row marked failed: row_id=%s", row_id)

    async def mark_coordinator_done_if_current(self, row_id: int, user_id: int, chat_id: str) -> bool:
        if not await self.is_latest_coordinator_row(row_id=row_id, user_id=user_id, chat_id=chat_id):
            logger.warning(
                "[agents:side-effects] Skipping stale coordinator done update: row_id=%s user_id=%s chat_id=%s",
                row_id,
                user_id,
                chat_id,
            )
            return False
        await self.mark_coordinator_done(row_id)
        return True

    async def mark_coordinator_failed_if_current(self, row_id: int, user_id: int, chat_id: str) -> bool:
        if not await self.is_latest_coordinator_row(row_id=row_id, user_id=user_id, chat_id=chat_id):
            logger.warning(
                "[agents:side-effects] Skipping stale coordinator failed update: row_id=%s user_id=%s chat_id=%s",
                row_id,
                user_id,
                chat_id,
            )
            return False
        await self.mark_coordinator_failed(row_id)
        return True

    async def _update_status(self, row_id: int, status: str) -> None:
        try:
            await self.repository.update_coordinator_status(row_id=row_id, status=status)
        except (SQLAlchemyError, ValueError, RuntimeError) as e:
            logger.warning("[agents:side-effects] Failed to update coordinator row %s to %s: %s", row_id, status, e)

    async def is_latest_coordinator_row(self, row_id: int, user_id: int, chat_id: str) -> bool:
        try:
            record = await self.repository.get_latest_coordinator_row(user_id=user_id, chat_id=chat_id)
        except (SQLAlchemyError, ValueError, RuntimeError) as e:
            logger.warning(
                "[agents:side-effects] Failed to verify latest coordinator row for user %s chat %s: %s",
                user_id,
                chat_id,
                e,
            )
            return False
        return bool(record and record.id == row_id)

    async def load_latest_coordinator_row(self, user_id: int, chat_id: str) -> TeacherSideEffect | None:
        """Return the latest coordinator tracking row for a chat, or None."""
        try:
            record = await self.repository.get_latest_coordinator_row(user_id=user_id, chat_id=chat_id)
        except (SQLAlchemyError, ValueError, RuntimeError) as e:
            logger.warning(
                "[agents:side-effects] Failed to load coordinator row for user %s chat %s: %s",
                user_id,
                chat_id,
                e,
            )
            return None
        if record is None:
            return None
        return TeacherSideEffect(
            name=record.specialist_name,
            phase=record.phase,
            status=record.status,
            info_for_teacher=record.info_for_teacher,
            artifacts=self.repository.deserialize_artifacts(record.artifacts_json),
            routing_reason=record.routing_reason or "",
            latency_ms=record.latency_ms,
            created_at=record.created_at,
        )

    # ------------------------------------------------------------------
    # Specialist result persistence (separated cleanup paths)
    # ------------------------------------------------------------------

    async def replace_post_specialist_results(
        self,
        user_id: int,
        chat_id: str,
        results: list[dict],
        coordinator_row_id: int,
    ) -> bool:
        """Replace specialist result rows without touching the coordinator tracking row."""
        records = [
            {
                "specialist_name": item.get("name", "unknown"),
                "phase": "post_response",
                "status": (item.get("result") or {}).get("status", "unknown"),
                "info_for_teacher": (item.get("result") or {}).get("info_for_teacher", ""),
                "artifacts": (item.get("result") or {}).get("artifacts", {}),
                "routing_reason": item.get("routing_reason", ""),
                "latency_ms": item.get("latency_ms"),
            }
            for item in results
            if isinstance(item, dict)
        ]

        try:
            if not await self.is_latest_coordinator_row(
                row_id=coordinator_row_id,
                user_id=user_id,
                chat_id=chat_id,
            ):
                logger.warning(
                    "[agents:side-effects] Skipping stale post specialist write: user_id=%s chat_id=%s row_id=%s",
                    user_id,
                    chat_id,
                    coordinator_row_id,
                )
                return False
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
            logger.debug(
                "[agents:side-effects] Replaced post specialist results: "
                "user_id=%s chat_id=%s deleted=%s inserted=%s",
                user_id,
                chat_id,
                deleted_count,
                len(records),
            )
            return True
        except (SQLAlchemyError, ValueError, RuntimeError) as e:
            await self.repository.db.rollback()
            logger.warning(
                "[agents:side-effects] Failed to replace post specialist results for user %s chat %s: %s",
                user_id,
                chat_id,
                e,
            )
            raise
