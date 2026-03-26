import json
from typing import Any

from sqlalchemy import delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from runestone.db.models import AgentSideEffect


class AgentSideEffectRepository:
    """Repository for persisted internal specialist side effects."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_many(
        self,
        user_id: int,
        chat_id: str,
        records: list[dict[str, Any]],
        commit: bool = True,
    ) -> list[AgentSideEffect]:
        created: list[AgentSideEffect] = []
        for record in records:
            artifacts = record.get("artifacts")
            model = AgentSideEffect(
                user_id=user_id,
                chat_id=chat_id,
                specialist_name=record["specialist_name"],
                phase=record["phase"],
                status=record["status"],
                info_for_teacher=record.get("info_for_teacher", "") or "",
                artifacts_json=json.dumps(artifacts, ensure_ascii=False, default=str) if artifacts else None,
                routing_reason=record.get("routing_reason"),
                latency_ms=record.get("latency_ms"),
            )
            self.db.add(model)
            created.append(model)

        if commit:
            await self.db.commit()
            for model in created:
                await self.db.refresh(model)
            return created

        # Keep inserts in the current transaction while making instances persistent.
        if created:
            await self.db.flush()

        return created

    async def get_recent_for_teacher(
        self,
        user_id: int,
        chat_id: str,
        *,
        phase: str = "post_response",
        statuses: tuple[str, ...] = ("action_taken",),
        limit: int = 5,
    ) -> list[AgentSideEffect]:
        """Load specialist result rows; excludes coordinator tracking rows."""
        stmt = (
            select(AgentSideEffect)
            .where(
                AgentSideEffect.user_id == user_id,
                AgentSideEffect.chat_id == chat_id,
                AgentSideEffect.phase == phase,
                AgentSideEffect.specialist_name != "coordinator",
                AgentSideEffect.status.in_(statuses),
            )
            .order_by(desc(AgentSideEffect.created_at), desc(AgentSideEffect.id))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        records = list(result.scalars().all())
        return list(reversed(records))

    async def delete_for_chat_phase(
        self,
        user_id: int,
        chat_id: str,
        phase: str = "post_response",
        commit: bool = True,
    ) -> int:
        """Delete specialist result rows for a phase; never touches coordinator rows."""
        stmt = delete(AgentSideEffect).where(
            AgentSideEffect.user_id == user_id,
            AgentSideEffect.chat_id == chat_id,
            AgentSideEffect.phase == phase,
            AgentSideEffect.specialist_name != "coordinator",
        )
        result = await self.db.execute(stmt)
        if commit:
            await self.db.commit()
        return int(result.rowcount or 0)

    # ------------------------------------------------------------------
    # Coordinator tracking row methods
    # ------------------------------------------------------------------

    async def create_coordinator_row(
        self,
        user_id: int,
        chat_id: str,
        status: str = "pending",
    ) -> AgentSideEffect:
        """Create a coordinator lifecycle tracking row and return it."""
        model = AgentSideEffect(
            user_id=user_id,
            chat_id=chat_id,
            specialist_name="coordinator",
            phase="post_response",
            status=status,
            info_for_teacher="",
        )
        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)
        return model

    async def update_coordinator_status(self, row_id: int, status: str) -> None:
        stmt = update(AgentSideEffect).where(AgentSideEffect.id == row_id).values(status=status)
        await self.db.execute(stmt)
        await self.db.commit()

    async def get_latest_coordinator_row(
        self,
        user_id: int,
        chat_id: str,
    ) -> AgentSideEffect | None:
        stmt = (
            select(AgentSideEffect)
            .where(
                AgentSideEffect.user_id == user_id,
                AgentSideEffect.chat_id == chat_id,
                AgentSideEffect.specialist_name == "coordinator",
                AgentSideEffect.phase == "post_response",
            )
            .order_by(desc(AgentSideEffect.id))
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def delete_coordinator_rows(
        self,
        user_id: int,
        chat_id: str,
        commit: bool = True,
    ) -> int:
        """Delete all coordinator tracking rows for a chat (separate from specialist rows)."""
        stmt = delete(AgentSideEffect).where(
            AgentSideEffect.user_id == user_id,
            AgentSideEffect.chat_id == chat_id,
            AgentSideEffect.specialist_name == "coordinator",
        )
        result = await self.db.execute(stmt)
        if commit:
            await self.db.commit()
        return int(result.rowcount or 0)

    @staticmethod
    def deserialize_artifacts(payload: str | None) -> dict[str, Any]:
        if not payload:
            return {}
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
