from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from runestone.agent.tools import memory as memory_tools


@pytest.mark.anyio
async def test_delete_memory_item_impl_calls_service():
    user = SimpleNamespace(id=123)
    memory_item_service = MagicMock()
    runtime = SimpleNamespace(context=SimpleNamespace(user=user, memory_item_service=memory_item_service))

    result = await memory_tools._delete_memory_item_impl(runtime, 7)

    memory_item_service.delete_item.assert_called_once_with(7, 123)
    assert "[ID:7]" in result
