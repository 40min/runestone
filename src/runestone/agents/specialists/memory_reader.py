"""
Pre-response specialist that summarizes relevant user memory for the teacher.
"""

from runestone.agents.specialists.base import BaseSpecialist, SpecialistAction, SpecialistContext, SpecialistResult
from runestone.agents.tools.service_providers import provide_memory_item_service
from runestone.api.memory_item_schemas import MemoryCategory


class MemoryReaderSpecialist(BaseSpecialist):
    """Loads compact memory context for the teacher response."""

    MAX_ITEMS = 250
    MAX_INFO_LINES = 500

    def __init__(self):
        super().__init__(name="memory_reader")

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        user_id = context.user.id
        async with provide_memory_item_service() as service:
            personal = await service.list_memory_items(
                user_id=user_id,
                category=MemoryCategory.PERSONAL_INFO,
                status="active",
                limit=100,
            )
            struggling = await service.list_memory_items(
                user_id=user_id,
                category=MemoryCategory.AREA_TO_IMPROVE,
                status="struggling",
                limit=100,
            )
            improving = await service.list_memory_items(
                user_id=user_id,
                category=MemoryCategory.KNOWLEDGE_STRENGTH,
                status="improving",
                limit=50,
            )

        combined = [*personal, *struggling, *improving][: self.MAX_ITEMS]
        if not combined:
            return SpecialistResult(
                status="no_action",
                actions=[SpecialistAction(tool="read_memory", status="success", summary="No memory items found")],
                info_for_teacher="",
                artifacts={"memory_count": 0},
            )

        lines: list[str] = []
        for item in combined[: self.MAX_INFO_LINES]:
            lines.append(f"- [{item.category}/{item.status}] {item.key}: {item.content}")

        return SpecialistResult(
            status="action_taken",
            actions=[
                SpecialistAction(
                    tool="read_memory",
                    status="success",
                    summary=f"Loaded {len(combined)} memory items",
                )
            ],
            info_for_teacher="Relevant learner memory:\n" + "\n".join(lines),
            artifacts={"memory_count": len(combined)},
        )
