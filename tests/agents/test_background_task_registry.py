import asyncio
import logging

import pytest

from runestone.agents.background_task_registry import BackgroundTaskRegistry


@pytest.fixture
def registry():
    return BackgroundTaskRegistry(logger=logging.getLogger("test-background-task-registry"), key_name="chat_id")


@pytest.mark.anyio
async def test_register_stores_task(registry):
    async def sleeper():
        await asyncio.sleep(10)

    task = asyncio.create_task(sleeper())
    registry.register("chat-1", task)

    assert registry.tasks["chat-1"] is task

    task.cancel()
    await asyncio.sleep(0)


@pytest.mark.anyio
async def test_register_replaces_and_cancels_existing_live_task(registry):
    async def sleeper():
        await asyncio.sleep(10)

    old_task = asyncio.create_task(sleeper())
    new_task = asyncio.create_task(sleeper())

    registry.register("chat-1", old_task)
    registry.register("chat-1", new_task)

    assert registry.tasks["chat-1"] is new_task
    await asyncio.sleep(0)
    assert old_task.cancelled()

    new_task.cancel()
    await asyncio.sleep(0)


def test_unregister_removes_task(registry):
    task = asyncio.Future()
    registry.tasks["chat-1"] = task

    registry.unregister("chat-1")

    assert "chat-1" not in registry.tasks


@pytest.mark.anyio
async def test_cancel_cancels_live_task_and_returns_true(registry):
    async def sleeper():
        await asyncio.sleep(10)

    task = asyncio.create_task(sleeper())
    registry.register("chat-1", task)

    cancelled = registry.cancel("chat-1")

    assert cancelled is True
    assert "chat-1" not in registry.tasks
    await asyncio.sleep(0)
    assert task.cancelled()


def test_cancel_returns_false_when_task_missing(registry):
    assert registry.cancel("missing-chat") is False


def test_cancel_returns_false_when_task_already_done(registry):
    task = asyncio.Future()
    task.set_result(None)
    registry.tasks["chat-1"] = task

    cancelled = registry.cancel("chat-1")

    assert cancelled is False
    assert "chat-1" not in registry.tasks
