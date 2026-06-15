"""Shared helpers for memory maintainer package modules."""

from typing import Any

from runestone.agents.specialists.base import SpecialistAction, SpecialistResult


def build_combined_result(
    *,
    trigger_source: str,
    dry_run: bool,
    area_result: SpecialistResult,
    personal_result: SpecialistResult,
) -> SpecialistResult:
    """Combine area and personal-info maintenance runs into one background result."""
    statuses = [area_result.status, personal_result.status]
    any_action = any(status == "action_taken" for status in statuses)
    any_error = any(status == "error" for status in statuses)

    if any_error:
        status = "error"
    elif any_action:
        status = "action_taken"
    else:
        status = "no_action"

    area_summary = _extract_summary(area_result.artifacts)
    personal_summary = _extract_summary(personal_result.artifacts)
    summary = f"area_to_improve={area_summary}; personal_info={personal_summary}"

    artifacts: dict[str, Any] = {
        "maintenance_type": "combined_memory_maintenance",
        "trigger_source": trigger_source,
        "dry_run": dry_run,
        "summary": summary,
        "domains": {
            "area_to_improve": area_result.artifacts,
            "personal_info": personal_result.artifacts,
        },
    }
    if any_error:
        artifacts["step_errors"] = {
            "area_to_improve": area_result.status == "error",
            "personal_info": personal_result.status == "error",
        }

    actions = []
    if status != "no_action":
        actions.append(
            SpecialistAction(
                tool="memory_maintainer",
                status="error" if status == "error" else "success",
                summary=summary,
            )
        )
    return SpecialistResult(status=status, actions=actions, info_for_teacher="", artifacts=artifacts)


def _extract_summary(artifacts: Any) -> str:
    if not isinstance(artifacts, dict):
        return "unknown"
    value = artifacts.get("summary")
    if isinstance(value, str) and value.strip():
        return value
    return "noop"
