import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agent.tools.memory import start_student_info
from runestone.api.memory_item_schemas import MemoryCategory, MemoryItemResponse


def _extract_json(output: str) -> dict:
    json_str = output.split("<memory_items_json>")[1].split("</memory_items_json>")[0].strip()
    return json.loads(json_str)


@pytest.mark.anyio
async def test_start_student_info_fetches_token_bounded_subset():
    now = datetime(2026, 2, 11, tzinfo=timezone.utc)
    personal = MemoryItemResponse(
        id=1,
        user_id=123,
        category="personal_info",
        key="name",
        content="Alice",
        status="active",
        created_at=now,
        updated_at=now,
        status_changed_at=now,
        metadata_json=None,
    )
    struggling = MemoryItemResponse(
        id=2,
        user_id=123,
        category="area_to_improve",
        key="past_tense",
        content="Struggles with past tense",
        status="struggling",
        created_at=now,
        updated_at=now,
        status_changed_at=now,
        metadata_json=None,
    )
    improving = MemoryItemResponse(
        id=3,
        user_id=123,
        category="area_to_improve",
        key="pronunciation",
        content="Improving pronunciation",
        status="improving",
        created_at=now,
        updated_at=now,
        status_changed_at=now,
        metadata_json=None,
    )

    # Track call count to return different values for each call
    call_count = [0]

    async def _list_memory_items(*, user_id: int, category=None, status=None, limit=100, offset=0):
        assert user_id == 123
        assert offset == 0
        call_num = call_count[0]
        call_count[0] += 1

        if call_num == 0:
            # First call: personal_info, active
            assert category == MemoryCategory.PERSONAL_INFO
            assert status == "active"
            assert limit == 50
            return [personal]
        elif call_num == 1:
            # Second call: area_to_improve, struggling
            assert category == MemoryCategory.AREA_TO_IMPROVE
            assert status == "struggling"
            assert limit == 75
            return [struggling]
        elif call_num == 2:
            # Third call: area_to_improve, improving
            assert category == MemoryCategory.AREA_TO_IMPROVE
            assert status == "improving"
            assert limit == 75
            return [improving]
        return []

    # Mock the provider to return our mocked service
    mock_service = MagicMock()
    mock_service.list_memory_items = AsyncMock(side_effect=_list_memory_items)

    with patch("runestone.agent.tools.memory.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock()

        user = SimpleNamespace(id=123)
        runtime = SimpleNamespace(context=SimpleNamespace(user=user))

        output = await start_student_info.coroutine(runtime)

    payload = _extract_json(output)
    assert "memory" in payload
    assert set(payload["memory"].keys()) == {"personal_info", "area_to_improve"}
    assert payload["memory"]["personal_info"][0]["key"] == "name"
    assert {item["key"] for item in payload["memory"]["area_to_improve"]} == {"past_tense", "pronunciation"}


@pytest.mark.anyio
async def test_start_student_info_no_items():
    # Mock the provider to return our mocked service
    mock_service = MagicMock()
    mock_service.list_memory_items = AsyncMock(return_value=[])

    with patch("runestone.agent.tools.memory.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock()

        user = SimpleNamespace(id=123)
        runtime = SimpleNamespace(context=SimpleNamespace(user=user))

        output = await start_student_info.coroutine(runtime)

    assert output == "No memory items found."
