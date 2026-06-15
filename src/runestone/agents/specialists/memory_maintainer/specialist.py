"""High-level memory maintainer orchestrator."""

import asyncio
from typing import Any

from runestone.agents.specialists.base import BaseSpecialist, SpecialistContext, SpecialistResult
from runestone.config import Settings

from .area_to_improve import AreaToImproveMemoryMaintainer
from .personal_info import PersonalInfoMemoryMaintainer
from .shared import build_combined_result


class CombinedMemoryMaintainerSpecialist(BaseSpecialist):
    """Public background entrypoint that runs both memory-maintenance domains."""

    def __init__(self, settings: Settings):
        super().__init__(name="memory_maintainer")
        self.settings = settings
        self.area_to_improve = AreaToImproveMemoryMaintainer(settings)
        self.personal_info = PersonalInfoMemoryMaintainer(settings)

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        """Run the combined background maintenance flow via the specialist contract."""
        return await self.run_for_user(context.user)

    async def run_for_user(self, user: Any) -> SpecialistResult:
        """Run both background maintenance domains for one user."""
        area_result, personal_result = await asyncio.gather(
            self.area_to_improve.run_for_user(user),
            self.personal_info.run_for_user(user),
        )
        return build_combined_result(
            trigger_source="chat_reset",
            dry_run=False,
            area_result=area_result,
            personal_result=personal_result,
        )
