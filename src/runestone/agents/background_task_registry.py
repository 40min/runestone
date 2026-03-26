"""
In-memory registry for background asyncio tasks.
"""

import asyncio
import logging


class BackgroundTaskRegistry:
    """Track live background tasks by key and handle replacement/cancellation."""

    def __init__(
        self,
        logger: logging.Logger,
        *,
        log_prefix: str = "[agents:post-task]",
        key_name: str = "key",
    ):
        self._logger = logger
        self._log_prefix = log_prefix
        self._key_name = key_name
        self._tasks: dict[str, asyncio.Task] = {}

    @property
    def tasks(self) -> dict[str, asyncio.Task]:
        return self._tasks

    def register(self, key: str, task: asyncio.Task) -> None:
        old = self._tasks.pop(key, None)
        if old and not old.done():
            self._logger.warning("%s Replacing still-alive task for %s=%s", self._log_prefix, self._key_name, key)
            old.cancel()
        self._tasks[key] = task

    def unregister(self, key: str) -> None:
        self._tasks.pop(key, None)

    def cancel(self, key: str) -> bool:
        """Cancel any live background task for key."""
        task = self._tasks.pop(key, None)
        if task and not task.done():
            task.cancel()
            self._logger.info("%s Cancelled stale task: %s=%s", self._log_prefix, self._key_name, key)
            return True
        return False
