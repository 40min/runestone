from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agent.tools.memory import delete_memory_item


@pytest.mark.anyio
async def test_delete_memory_item_calls_service():
    user = SimpleNamespace(id=123)

    # Mock the provider to return our mocked service
    mock_service = MagicMock()
    mock_service.delete_item = AsyncMock()

    with patch("runestone.agent.tools.memory.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock()

        runtime = SimpleNamespace(context=SimpleNamespace(user=user))
        result = await delete_memory_item.coroutine(runtime, delete=SimpleNamespace(item_id=7))

    mock_service.delete_item.assert_called_once_with(7, 123)
    assert "[ID:7]" in result
