from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agents.specialists.base import SpecialistResult
from runestone.agents.specialists.memory_maintainer.shared import build_combined_result
from runestone.agents.specialists.memory_maintainer.specialist import CombinedMemoryMaintainerSpecialist


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.memory_maintainer_provider = "openrouter"
    settings.memory_maintainer_model = "test-model"
    return settings


@pytest.fixture
def mock_user():
    return SimpleNamespace(id=1, mother_tongue="Finnish")


@pytest.mark.anyio
async def test_combined_result_surfaces_domain_error_even_when_other_domain_acts():
    area_result = SpecialistResult(status="action_taken", actions=[], info_for_teacher="", artifacts={"summary": "ok"})
    personal_result = SpecialistResult(status="error", actions=[], info_for_teacher="", artifacts={"summary": "boom"})

    result = build_combined_result(
        trigger_source="chat_reset",
        dry_run=False,
        area_result=area_result,
        personal_result=personal_result,
    )

    assert result.status == "error"
    assert result.actions[0].status == "error"
    assert result.artifacts["step_errors"]["personal_info"] is True


@pytest.mark.anyio
async def test_combined_memory_maintainer_runs_both_domains_and_combines_artifacts(mock_settings, mock_user):
    area_result = SpecialistResult(
        status="action_taken",
        actions=[],
        info_for_teacher="",
        artifacts={"summary": "area merged"},
    )
    personal_result = SpecialistResult(
        status="no_action",
        actions=[],
        info_for_teacher="",
        artifacts={"summary": "noop"},
    )

    with (
        patch("runestone.agents.specialists.memory_maintainer.specialist.AreaToImproveMemoryMaintainer") as area_cls,
        patch("runestone.agents.specialists.memory_maintainer.specialist.PersonalInfoMemoryMaintainer") as personal_cls,
    ):
        area_instance = area_cls.return_value
        personal_instance = personal_cls.return_value
        area_instance.run_for_user = AsyncMock(return_value=area_result)
        personal_instance.run_for_user = AsyncMock(return_value=personal_result)

        specialist = CombinedMemoryMaintainerSpecialist(mock_settings)
        result = await specialist.run_for_user(mock_user)

    area_instance.run_for_user.assert_awaited_once_with(mock_user)
    personal_instance.run_for_user.assert_awaited_once_with(mock_user)
    assert result.status == "action_taken"
    assert result.artifacts["domains"]["area_to_improve"]["summary"] == "area merged"
    assert result.artifacts["domains"]["personal_info"]["summary"] == "noop"
