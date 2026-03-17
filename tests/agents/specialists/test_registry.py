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
