from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agents.tools.context import AgentContext
from runestone.agents.tools.memory import read_memory
from runestone.api.memory_item_schemas import MemoryCategory, MemorySortBy, SortDirection


@pytest.mark.anyio
async def test_read_memory_uses_freshness_order_and_limit():
    service = MagicMock()
    service.list_memory_items = AsyncMock(return_value=[])
    runtime = SimpleNamespace(context=AgentContext(user=SimpleNamespace(id=42)))

    @asynccontextmanager
    async def fake_provider():
        yield service

    with patch("runestone.agents.tools.memory.provide_memory_item_service", fake_provider):
        result = await read_memory.coroutine(runtime=runtime, category=MemoryCategory.AREA_TO_IMPROVE)

    assert result == "No memory items found."
    service.list_memory_items.assert_awaited_once_with(
        user_id=42,
        category=MemoryCategory.AREA_TO_IMPROVE,
        status=None,
        sort_by=MemorySortBy.UPDATED_AT,
        sort_direction=SortDirection.DESC,
        limit=100,
        offset=0,
    )
