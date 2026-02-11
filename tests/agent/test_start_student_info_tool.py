import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from runestone.agent.tools import memory as memory_tools
from runestone.api.memory_item_schemas import MemoryCategory, MemoryItemResponse


def _extract_json(output: str) -> dict:
    json_str = output.split("<memory_items_json>")[1].split("</memory_items_json>")[0].strip()
    return json.loads(json_str)


@pytest.mark.anyio
async def test_start_student_info_impl_fetches_token_bounded_subset():
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

    def _list_memory_items(*, user_id: int, category=None, status=None, limit=100, offset=0):
        assert user_id == 123
        assert offset == 0
        if category == MemoryCategory.PERSONAL_INFO and status == "active":
            assert limit == 50
            return [personal]
        if category == MemoryCategory.AREA_TO_IMPROVE and status == "struggling":
            assert limit == 75
            return [struggling]
        if category == MemoryCategory.AREA_TO_IMPROVE and status == "improving":
            assert limit == 75
            return [improving]
        return []

    memory_item_service = MagicMock()
    memory_item_service.list_memory_items.side_effect = _list_memory_items

    user = SimpleNamespace(id=123)
    runtime = SimpleNamespace(context=SimpleNamespace(user=user, memory_item_service=memory_item_service))

    output = await memory_tools._start_student_info_impl(runtime)

    payload = _extract_json(output)
    assert "memory" in payload
    assert set(payload["memory"].keys()) == {"personal_info", "area_to_improve"}
    assert payload["memory"]["personal_info"][0]["key"] == "name"
    assert {item["key"] for item in payload["memory"]["area_to_improve"]} == {"past_tense", "pronunciation"}


@pytest.mark.anyio
async def test_start_student_info_impl_no_items():
    memory_item_service = MagicMock()
    memory_item_service.list_memory_items.return_value = []
    user = SimpleNamespace(id=123)
    runtime = SimpleNamespace(context=SimpleNamespace(user=user, memory_item_service=memory_item_service))

    output = await memory_tools._start_student_info_impl(runtime)
    assert output == "No memory items found."
