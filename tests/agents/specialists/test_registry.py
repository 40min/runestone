import pytest

from runestone.agents.specialists.base import BaseSpecialist, SpecialistContext, SpecialistResult
from runestone.agents.specialists.registry import SpecialistRegistry


class _MockSpecialist(BaseSpecialist):
    async def run(self, context: SpecialistContext) -> SpecialistResult:
        return SpecialistResult(status="no_action")


def test_registry_register_and_get():
    registry = SpecialistRegistry()
    specialist = _MockSpecialist(name="mock")
    registry.register(specialist)

    assert registry.get("mock") is specialist
    assert registry.list_names() == ["mock"]


def test_registry_register_raises_on_duplicate_name():
    registry = SpecialistRegistry()
    specialist = _MockSpecialist(name="mock")

    registry.register(specialist)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_MockSpecialist(name="mock"))


def test_registry_register_overwrite_replaces_existing():
    registry = SpecialistRegistry()
    first = _MockSpecialist(name="mock")
    second = _MockSpecialist(name="mock")

    registry.register(first)
    registry.register(second, overwrite=True)

    assert registry.get("mock") is second
    assert registry.list_names() == ["mock"]
