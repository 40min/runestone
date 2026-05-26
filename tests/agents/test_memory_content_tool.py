from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agents.tools.memory import update_memory_item_content
from runestone.api.memory_item_schemas import MemoryCategory


@pytest.mark.anyio
async def test_update_memory_item_content_calls_service():
    user = SimpleNamespace(id=42)
    mock_service = MagicMock()
    mock_service.update_item_content_in_category = AsyncMock(return_value=SimpleNamespace(id=7, key="mother_tongue"))

    with patch("runestone.agents.tools.memory.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock()

        runtime = SimpleNamespace(context=SimpleNamespace(user=user))
        result = await update_memory_item_content.coroutine(
            runtime,
            update=SimpleNamespace(item_id=7, category=MemoryCategory.PERSONAL_INFO, content="Estonian"),
        )

    mock_service.update_item_content_in_category.assert_called_once_with(
        7,
        MemoryCategory.PERSONAL_INFO,
        "Estonian",
        42,
    )
    assert "[ID:7]" in result
