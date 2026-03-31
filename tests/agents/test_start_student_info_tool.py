import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agents.tools.memory import start_student_info
from runestone.api.memory_item_schemas import MemoryItemResponse


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
    strength = MemoryItemResponse(
        id=4,
        user_id=123,
        category="knowledge_strength",
        key="reading_comprehension",
        content="Strong reading comprehension",
        status="active",
        created_at=now,
        updated_at=now,
        status_changed_at=now,
        metadata_json=None,
    )

    # Mock the provider to return our mocked service
    mock_service = MagicMock()
    mock_service.list_start_student_info_items = AsyncMock(return_value=[personal, struggling, improving, strength])

    with patch("runestone.agents.tools.memory.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock()

        user = SimpleNamespace(id=123)
        runtime = SimpleNamespace(context=SimpleNamespace(user=user))

        output = await start_student_info.coroutine(runtime)

    mock_service.list_start_student_info_items.assert_awaited_once_with(
        user_id=123,
        personal_limit=50,
        area_limit=5,
        knowledge_limit=50,
    )
    payload = _extract_json(output)
    assert "memory" in payload
    assert set(payload["memory"].keys()) == {"personal_info", "area_to_improve", "knowledge_strength"}
    assert payload["memory"]["personal_info"][0]["key"] == "name"
    assert {item["key"] for item in payload["memory"]["area_to_improve"]} == {"past_tense", "pronunciation"}
    assert payload["memory"]["knowledge_strength"][0]["key"] == "reading_comprehension"


@pytest.mark.anyio
async def test_start_student_info_returns_only_top_five_area_to_improve_items():
    base_time = datetime(2026, 2, 11, tzinfo=timezone.utc)
    personal = MemoryItemResponse(
        id=1,
        user_id=123,
        category="personal_info",
        key="name",
        content="Alice",
        status="active",
        created_at=base_time,
        updated_at=base_time,
        status_changed_at=base_time,
        metadata_json=None,
    )

    def _area_item(item_id: int, key: str, status: str, priority: int) -> MemoryItemResponse:
        return MemoryItemResponse(
            id=item_id,
            user_id=123,
            category="area_to_improve",
            key=key,
            content=f"Practice {key}",
            status=status,
            priority=priority,
            created_at=base_time,
            updated_at=base_time,
            status_changed_at=base_time,
            metadata_json=None,
        )

    area_items = [
        _area_item(10, "word_order", "struggling", 0),
        _area_item(20, "pronunciation", "improving", 1),
        _area_item(11, "articles", "struggling", 2),
        _area_item(21, "prepositions", "improving", 3),
        _area_item(12, "plural_forms", "struggling", 4),
    ]

    strength = MemoryItemResponse(
        id=30,
        user_id=123,
        category="knowledge_strength",
        key="listening",
        content="Strong listening skills",
        status="active",
        priority=None,
        created_at=base_time,
        updated_at=base_time,
        status_changed_at=base_time,
        metadata_json=None,
    )

    mock_service = MagicMock()
    mock_service.list_start_student_info_items = AsyncMock(return_value=[personal, *area_items, strength])

    with patch("runestone.agents.tools.memory.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock()

        user = SimpleNamespace(id=123)
        runtime = SimpleNamespace(context=SimpleNamespace(user=user))

        output = await start_student_info.coroutine(runtime)

    payload = _extract_json(output)
    area_keys = [item["key"] for item in payload["memory"]["area_to_improve"]]

    assert area_keys == [
        "word_order",
        "pronunciation",
        "articles",
        "prepositions",
        "plural_forms",
    ]
    assert len(area_keys) == 5
    assert "past_tense" not in area_keys
    assert payload["memory"]["knowledge_strength"][0]["key"] == "listening"


@pytest.mark.anyio
async def test_start_student_info_no_items():
    # Mock the provider to return our mocked service
    mock_service = MagicMock()
    mock_service.list_start_student_info_items = AsyncMock(return_value=[])

    with patch("runestone.agents.tools.memory.provide_memory_item_service") as mock_provider:
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_provider.return_value.__aexit__ = AsyncMock()

        user = SimpleNamespace(id=123)
        runtime = SimpleNamespace(context=SimpleNamespace(user=user))

        output = await start_student_info.coroutine(runtime)

    assert output == "No memory items found."
