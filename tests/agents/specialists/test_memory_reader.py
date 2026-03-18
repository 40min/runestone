from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agents.specialists.base import INFO_FOR_TEACHER_MAX_CHARS, SpecialistContext
from runestone.agents.specialists.memory_reader import MemoryReaderSpecialist
from runestone.api.memory_item_schemas import MemoryCategory


def _service_provider(service):
    @asynccontextmanager
    async def _provider():
        yield service

    return _provider


def _memory_item(category: MemoryCategory, status: str, key: str, content: str):
    now = datetime.now()
    return SimpleNamespace(
        id=1,
        user_id=1,
        category=category.value,
        key=key,
        content=content,
        status=status,
        priority=None,
        created_at=now,
        updated_at=now,
        status_changed_at=None,
        metadata_json=None,
    )


@pytest.fixture
def specialist():
    return MemoryReaderSpecialist()


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    return user


@pytest.mark.anyio
async def test_memory_reader_returns_no_action_when_empty(specialist, mock_user):
    service = MagicMock()
    service.list_memory_items = AsyncMock(side_effect=[[], [], []])

    with patch(
        "runestone.agents.specialists.memory_reader.provide_memory_item_service",
        _service_provider(service),
    ):
        result = await specialist.run(SpecialistContext(message="Hi", history=[], user=mock_user))

    assert result.status == "no_action"
    assert result.info_for_teacher == ""
    assert result.artifacts == {"memory_count": 0}


@pytest.mark.anyio
async def test_memory_reader_packs_memory_to_fit_budget(specialist, mock_user):
    oversized = [
        _memory_item(
            MemoryCategory.PERSONAL_INFO,
            "active",
            f"key-{idx}",
            "x" * 300,
        )
        for idx in range(80)
    ]
    service = MagicMock()
    service.list_memory_items = AsyncMock(side_effect=[oversized, [], []])

    with patch(
        "runestone.agents.specialists.memory_reader.provide_memory_item_service",
        _service_provider(service),
    ):
        result = await specialist.run(SpecialistContext(message="Hi", history=[], user=mock_user))

    assert result.status == "action_taken"
    assert len(result.info_for_teacher) <= INFO_FOR_TEACHER_MAX_CHARS
    assert result.artifacts["memory_count"] == 80
    assert result.artifacts["included_memory_count"] < 80
    assert result.artifacts["omitted_memory_count"] > 0
    assert "omitted to fit context" in result.info_for_teacher


@pytest.mark.anyio
async def test_memory_reader_logs_when_limits_hit(specialist, mock_user, caplog):
    oversized = [
        _memory_item(
            MemoryCategory.PERSONAL_INFO,
            "active",
            f"key-{idx}",
            "x" * 10,
        )
        for idx in range(300)
    ]
    service = MagicMock()
    service.list_memory_items = AsyncMock(side_effect=[oversized, [], []])

    with patch(
        "runestone.agents.specialists.memory_reader.provide_memory_item_service",
        _service_provider(service),
    ):
        with caplog.at_level("WARNING"):
            await specialist.run(SpecialistContext(message="Hi", history=[], user=mock_user))

    assert "Truncated combined memory items" in caplog.text


@pytest.mark.anyio
async def test_memory_reader_logs_when_char_budget_is_hit(specialist, mock_user, caplog):
    oversized = [
        _memory_item(
            MemoryCategory.PERSONAL_INFO,
            "active",
            f"key-{idx}",
            "x" * 500,
        )
        for idx in range(80)
    ]
    service = MagicMock()
    service.list_memory_items = AsyncMock(side_effect=[oversized, [], []])

    with patch(
        "runestone.agents.specialists.memory_reader.provide_memory_item_service",
        _service_provider(service),
    ):
        with caplog.at_level("WARNING"):
            await specialist.run(SpecialistContext(message="Hi", history=[], user=mock_user))

    assert "Stopped adding memory lines" in caplog.text
    assert "Omitted" in caplog.text
