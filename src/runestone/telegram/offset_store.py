"""File-backed storage for the Telegram bot polling cursor."""

import logging
import os

logger = logging.getLogger(__name__)


class TelegramUpdateOffsetStore:
    """Read and write the single Telegram update offset file."""

    def __init__(self, offset_file_path: str = "state/offset.txt"):
        self.offset_file_path = offset_file_path

    def get_update_offset(self) -> int:
        """Return the current Telegram polling offset, defaulting to zero."""
        try:
            if os.path.exists(self.offset_file_path):
                with open(self.offset_file_path) as file:
                    return int(file.read().strip())
            return 0
        except Exception as exc:
            logger.error("Failed to get update offset: %s", exc)
            return 0

    def set_update_offset(self, offset: int) -> None:
        """Persist the next Telegram polling offset."""
        try:
            parent = os.path.dirname(self.offset_file_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.offset_file_path, "w") as file:
                file.write(str(offset))
        except Exception as exc:
            logger.error("Failed to set update offset: %s", exc)
            raise
