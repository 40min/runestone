from abc import ABC, abstractmethod
from typing import Annotated, Any, Literal

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field, StringConstraints, ValidationError

from runestone.agents.schemas import ChatMessage
from runestone.core.service_llm import extract_message_text
from runestone.schemas.vocabulary_save import WordSaveCandidate

INFO_FOR_TEACHER_MAX_CHARS = 12000


class SpecialistContext(BaseModel):
    """Typed specialist input passed from the manager."""

    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    user: Any
    teacher_response: str | None = None
    vocabulary_candidates: list[WordSaveCandidate] = Field(default_factory=list)
    pre_results: list[dict[str, Any]] = Field(default_factory=list)
    routing_reason: str = ""
    chat_history_size: int = 0


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
    info_for_teacher: Annotated[str, StringConstraints(max_length=INFO_FOR_TEACHER_MAX_CHARS)] = Field(
        "",
        description=(
            "Primary, size-bounded information for the TeacherAgent. "
            "Must be safe to show to the teacher model and should avoid technical noise."
        ),
    )
    artifacts: dict[str, Any] = Field(
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
    async def run(self, context: SpecialistContext) -> SpecialistResult:
        """
        Execute the specialist logic.

        Args:
            context: Typed specialist context containing relevant conversation data and dependencies.

        Returns:
            SpecialistResult: Structured output of the specialist run.
        """
        pass


def parse_specialist_result(payload: dict[str, Any]) -> SpecialistResult | None:
    """Parse a specialist result from structured output or final AI text."""
    structured_response = payload.get("structured_response")
    if isinstance(structured_response, SpecialistResult):
        return structured_response
    if isinstance(structured_response, dict):
        try:
            return SpecialistResult.model_validate(structured_response)
        except ValidationError:
            pass

    for message in reversed(payload.get("messages", [])):
        if not isinstance(message, AIMessage):
            continue
        if getattr(message, "tool_calls", None):
            continue
        text_content = extract_message_text(message)
        if not text_content:
            continue
        json_content = _extract_json_object(text_content)
        if not json_content:
            continue
        try:
            return SpecialistResult.model_validate_json(json_content)
        except (ValidationError, ValueError):
            continue
    return None


def _extract_json_object(content: str) -> str | None:
    """Trim fenced or mixed-content agent output down to the JSON object payload."""
    stripped = content.strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    return stripped[start : end + 1]
