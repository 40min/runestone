import json
from typing import Any

from sqlalchemy import delete, desc, select
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
        # This allows callers to compose add/delete work and commit once.
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
        stmt = (
            select(AgentSideEffect)
            .where(
                AgentSideEffect.user_id == user_id,
                AgentSideEffect.chat_id == chat_id,
                AgentSideEffect.phase == phase,
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
        stmt = delete(AgentSideEffect).where(
            AgentSideEffect.user_id == user_id,
            AgentSideEffect.chat_id == chat_id,
            AgentSideEffect.phase == phase,
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
