from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from runestone.agent.tools.memory import delete_memory_item


@pytest.mark.anyio
async def test_delete_memory_item_calls_service():
    user = SimpleNamespace(id=123)
    memory_item_service = MagicMock()
    memory_item_service.delete_item = AsyncMock()
    runtime = SimpleNamespace(context=SimpleNamespace(user=user, memory_item_service=memory_item_service))

    result = await delete_memory_item.coroutine(runtime, delete=SimpleNamespace(item_id=7))

    memory_item_service.delete_item.assert_called_once_with(7, 123)
    assert "[ID:7]" in result
