"""Routing, side-effect, and coordinator lifecycle payloads."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RoutingItem(BaseModel):
    """Routing decision for a specialist agent."""

    name: str = Field(..., description="Specialist name to invoke")
    reason: str = Field(..., description="Why this specialist should run")


class CoordinatorPlan(BaseModel):
    """Coordinator routing plan for a single turn."""

    pre_response: list[RoutingItem] = Field(default_factory=list, description="Pre-response specialists")
    post_response: list[RoutingItem] = Field(default_factory=list, description="Post-response specialists")
    audit: dict = Field(default_factory=dict, description="Audit metadata for observability")


class TeacherSideEffect(BaseModel):
    """Typed side-effect payload consumed by the teacher prompt layer."""

    name: str = Field(..., description="Specialist name")
    phase: str = Field(..., description="Execution phase")
    status: str = Field(..., description="Specialist status")
    info_for_teacher: str = Field("", description="Teacher-facing summary")
    artifacts: dict[str, Any] = Field(default_factory=dict, description="Structured specialist artifacts")
    routing_reason: str = Field("", description="Coordinator rationale")
    latency_ms: int | None = Field(None, description="Specialist execution latency in milliseconds")
    created_at: datetime | None = Field(None, description="Persisted record timestamp")


class CoordinatorRow(BaseModel):
    """Coordinator lifecycle row used to track background post-stage state."""

    id: int = Field(..., description="Persisted coordinator row id")
    status: str = Field(..., description="Coordinator status")
    created_at: datetime | None = Field(None, description="Persisted row timestamp")
