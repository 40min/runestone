from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agent.tools.memory import update_memory_priority


@pytest.mark.anyio
async def test_update_memory_priority_calls_service():
    user = SimpleNamespace(id=42)
    mock_service = MagicMock()
    mock_service.update_item_priority = AsyncMock(return_value=SimpleNamespace(id=7, key="verb_tense", priority=1))

    with patch("runestone.agent.tools.memory.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock()

        runtime = SimpleNamespace(context=SimpleNamespace(user=user))
        result = await update_memory_priority.coroutine(runtime, update=SimpleNamespace(item_id=7, priority=1))

    mock_service.update_item_priority.assert_called_once_with(7, 1, 42)
    assert "[ID:7]" in result
    assert "1" in result


@pytest.mark.anyio
async def test_update_memory_priority_null_maps_to_lowest_calls_service():
    user = SimpleNamespace(id=42)
    mock_service = MagicMock()
    mock_service.update_item_priority = AsyncMock(return_value=SimpleNamespace(id=7, key="verb_tense", priority=9))

    with patch("runestone.agent.tools.memory.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock()

        runtime = SimpleNamespace(context=SimpleNamespace(user=user))
        result = await update_memory_priority.coroutine(runtime, update=SimpleNamespace(item_id=7, priority=None))

    mock_service.update_item_priority.assert_called_once_with(7, None, 42)
    assert "9" in result
