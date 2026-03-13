"""
Registry for specialist agents.
"""

from collections import OrderedDict

from runestone.agents.specialists.base import BaseSpecialist


class SpecialistRegistry:
    """Simple registry to manage specialist instances by name."""

    def __init__(self):
        self._specialists: OrderedDict[str, BaseSpecialist] = OrderedDict()

    def register(self, specialist: BaseSpecialist) -> None:
        self._specialists[specialist.name] = specialist

    def get(self, name: str) -> BaseSpecialist | None:
        return self._specialists.get(name)

    def list_names(self) -> list[str]:
        return list(self._specialists.keys())
