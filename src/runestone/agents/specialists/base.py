from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field


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
    artifacts: dict = Field(default_factory=dict, description="Structured domain-specific information")
    notes_for_teacher: str = Field("", description="Short summary to help the teacher agent compose a response")


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
