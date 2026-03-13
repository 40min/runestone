from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field

INFO_FOR_TEACHER_MAX_CHARS = 3000


class SpecialistAction(BaseModel):
    """Represents a single tool action taken by a specialist."""

    tool: str = Field(..., description="Name of the tool called")
    status: Literal["success", "error"] = Field(..., description="Outcome of the tool call")
    summary: str = Field(..., description="Brief human-readable summary of the action")


class SpecialistResult(BaseModel):
    """Shared structured result schema for all specialist outputs."""

    status: Literal["no_action", "action_taken", "error"] = Field(
        ..., description="Overall outcome of the specialist run"
    )
    actions: list[SpecialistAction] = Field(default_factory=list, description="List of tool actions performed")
    info_for_teacher: str = Field(
        "",
        description=(
            "Primary, size-bounded information for the TeacherAgent. "
            "Must be safe to show to the teacher model and should avoid technical noise."
        ),
        max_length=INFO_FOR_TEACHER_MAX_CHARS,
    )
    artifacts: dict = Field(
        default_factory=dict,
        description=(
            "Structured, machine-oriented payload for orchestration, persistence, dedupe, or testing. "
            "Not intended to be consumed verbatim by the TeacherAgent."
        ),
    )


class BaseSpecialist(ABC):
    """Base interface for all specialist agents in the swarm."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def run(self, context: dict) -> SpecialistResult:
        """
        Execute the specialist logic.

        Args:
            context: Dictionary containing relevant conversation context and dependencies.

        Returns:
            SpecialistResult: Structured output of the specialist run.
        """
        pass
