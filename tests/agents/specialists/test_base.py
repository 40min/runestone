import pytest
from pydantic import ValidationError

from runestone.agents.specialists.base import (
    INFO_FOR_TEACHER_MAX_CHARS,
    BaseSpecialist,
    SpecialistAction,
    SpecialistContext,
    SpecialistResult,
)


def test_specialist_result_validation():
    """Test that SpecialistResult validates correctly."""
    # Valid minimal result
    result = SpecialistResult(status="no_action")
    assert result.status == "no_action"
    assert result.actions == []
    assert result.info_for_teacher == ""
    assert result.artifacts == {}

    # Valid result with actions and artifacts
    action = SpecialistAction(tool="test_tool", status="success", summary="did something")
    result = SpecialistResult(
        status="action_taken", actions=[action], artifacts={"key": "value"}, info_for_teacher="A note"
    )
    assert result.status == "action_taken"
    assert len(result.actions) == 1
    assert result.actions[0].tool == "test_tool"
    assert result.artifacts["key"] == "value"

    # Invalid status
    with pytest.raises(ValidationError):
        SpecialistResult(status="invalid_status")

    with pytest.raises(ValidationError):
        SpecialistResult(status="no_action", info_for_teacher="x" * (INFO_FOR_TEACHER_MAX_CHARS + 1))


def test_base_specialist_is_abstract():
    """Test that BaseSpecialist cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseSpecialist(name="test")


class MockSpecialist(BaseSpecialist):
    """A concrete implementation for testing."""

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        return SpecialistResult(status="no_action")


@pytest.mark.anyio
async def test_concrete_specialist_instantiation():
    """Test that a concrete specialist can be instantiated and run."""
    specialist = MockSpecialist(name="mock")
    assert specialist.name == "mock"
    context = SpecialistContext(message="Hi", history=[], user=object())
    result = await specialist.run(context)
    assert result.status == "no_action"
