from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agents.tools.memory import update_memory_item_content, update_memory_status
from runestone.api.memory_item_schemas import MemoryCategory


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


@pytest.mark.anyio
async def test_update_memory_item_content_returns_tool_error_for_blank_content():
    user = SimpleNamespace(id=42)
    mock_service = MagicMock()
    mock_service.update_item_content_in_category = AsyncMock(side_effect=ValueError("content must not be empty"))

    with patch("runestone.agents.tools.memory.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock(return_value=False)

        runtime = SimpleNamespace(context=SimpleNamespace(user=user))
        result = await update_memory_item_content.coroutine(
            runtime,
            update=SimpleNamespace(item_id=7, category=MemoryCategory.PERSONAL_INFO, content="   "),
        )

    mock_service.update_item_content_in_category.assert_called_once_with(
        7,
        MemoryCategory.PERSONAL_INFO,
        "   ",
        42,
    )
    assert result == "Tool error in update_memory_item_content: content must not be empty"
