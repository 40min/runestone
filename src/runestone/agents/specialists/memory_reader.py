"""
Pre-response specialist that summarizes relevant user memory for the teacher.
"""

import logging

from runestone.agents.service_providers import provide_memory_item_service
from runestone.agents.specialists.base import (
    INFO_FOR_TEACHER_MAX_CHARS,
    BaseSpecialist,
    SpecialistAction,
    SpecialistContext,
    SpecialistResult,
)
from runestone.api.memory_item_schemas import MemoryCategory

logger = logging.getLogger(__name__)


class MemoryReaderSpecialist(BaseSpecialist):
    """Loads compact memory context for the teacher response."""

    MAX_ITEMS = 250
    MAX_INFO_LINES = 500
    HEADER = "Relevant learner memory:"

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

        source_items = [*personal, *struggling, *improving]
        if len(source_items) > self.MAX_ITEMS:
            logger.warning(
                "[agents:memory_reader] Truncated combined memory items from %s to %s due to MAX_ITEMS",
                len(source_items),
                self.MAX_ITEMS,
            )
        combined = source_items[: self.MAX_ITEMS]
        if not combined:
            return SpecialistResult(
                status="no_action",
                actions=[SpecialistAction(tool="read_memory", status="success", summary="No memory items found")],
                info_for_teacher="",
                artifacts={"memory_count": 0},
            )

        info_for_teacher, included_count = self._build_info_for_teacher(combined)
        omitted_count = max(len(combined) - included_count, 0)
        artifacts = {"memory_count": len(combined), "included_memory_count": included_count}
        if omitted_count:
            artifacts["omitted_memory_count"] = omitted_count
            logger.warning(
                "[agents:memory_reader] Omitted %s memory item(s) from teacher context due to info budget",
                omitted_count,
            )

        return SpecialistResult(
            status="action_taken",
            actions=[
                SpecialistAction(
                    tool="read_memory",
                    status="success",
                    summary=f"Loaded {len(combined)} memory items",
                )
            ],
            info_for_teacher=info_for_teacher,
            artifacts=artifacts,
        )

    @classmethod
    def _build_info_for_teacher(cls, items: list) -> tuple[str, int]:
        lines = [cls.HEADER]
        remaining_chars = INFO_FOR_TEACHER_MAX_CHARS - len(cls.HEADER)
        included_count = 0
        visible_items = items[: cls.MAX_INFO_LINES]
        if len(items) > cls.MAX_INFO_LINES:
            logger.warning(
                "[agents:memory_reader] Truncated memory line candidates from %s to %s due to MAX_INFO_LINES",
                len(items),
                cls.MAX_INFO_LINES,
            )

        for item in visible_items:
            line = f"- [{item.category}/{item.status}] {item.key}: {item.content}"
            required_chars = len(line) + 1
            if required_chars > remaining_chars:
                logger.warning(
                    "[agents:memory_reader] Stopped adding memory lines after %s item(s) due to %s-char limit",
                    included_count,
                    INFO_FOR_TEACHER_MAX_CHARS,
                )
                break
            lines.append(line)
            remaining_chars -= required_chars
            included_count += 1

        omitted_count = max(len(items) - included_count, 0)
        if omitted_count:
            suffix = f"... ({omitted_count} more memory item(s) omitted to fit context)"
            required_chars = len(suffix) + 1
            if required_chars <= remaining_chars:
                lines.append(suffix)
            elif included_count > 0:
                last_line = lines[-1]
                budget = max(len(last_line) - (required_chars - remaining_chars), 0)
                trimmed_last_line = last_line[: max(budget - 3, 0)] + "..." if budget >= 4 else ""
                if trimmed_last_line:
                    lines[-1] = trimmed_last_line
                    lines.append(suffix)

        return "\n".join(lines), included_count
