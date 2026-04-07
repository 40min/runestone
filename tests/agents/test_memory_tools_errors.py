from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agents.tools.memory import promote_to_strength, update_memory_status


@pytest.mark.anyio
async def test_promote_to_strength_returns_tool_error_for_non_mastered_item():
    user = SimpleNamespace(id=42)
    mock_service = MagicMock()
    mock_service.promote_to_strength = AsyncMock(
        side_effect=ValueError("Only mastered items can be promoted to knowledge_strength")
    )

    with patch("runestone.agents.tools.memory.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock(return_value=False)

        runtime = SimpleNamespace(context=SimpleNamespace(user=user))
        result = await promote_to_strength.coroutine(runtime, promote=SimpleNamespace(item_id=7))

    mock_service.promote_to_strength.assert_called_once_with(7, 42)
    assert result == "Tool error in promote_to_strength: Only mastered items can be promoted to knowledge_strength"


@pytest.mark.anyio
async def test_update_memory_status_returns_tool_error_for_invalid_transition():
    user = SimpleNamespace(id=42)
    mock_service = MagicMock()
    mock_service.update_item_status = AsyncMock(
        side_effect=ValueError("Invalid status 'active' for category 'area_to_improve'")
    )

    with patch("runestone.agents.tools.memory.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock(return_value=False)

        runtime = SimpleNamespace(context=SimpleNamespace(user=user))
        result = await update_memory_status.coroutine(
            runtime,
            update=SimpleNamespace(item_id=7, new_status="active"),
        )

    mock_service.update_item_status.assert_called_once_with(7, "active", 42)
    assert result == "Tool error in update_memory_status: Invalid status 'active' for category 'area_to_improve'"
