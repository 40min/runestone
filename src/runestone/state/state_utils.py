"""
Utility functions and decorators for state management.
"""

import json
import logging
import os
import shutil
from functools import wraps
from typing import Any, Dict, Optional

from .state_config import StateManagerConfig
from .state_exceptions import StateAccessError, StateCorruptionError
from .state_types import StateData

logger = logging.getLogger(__name__)


def with_lock(func):
    """Decorator to automatically acquire lock for method execution."""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return func(self, *args, **kwargs)

    return wrapper


def logged_operation(operation_name: str):
    """Decorator to log state operations."""

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if self.config.log_state_operations:
                logger.debug(f"Starting {operation_name}")
            try:
                result = func(self, *args, **kwargs)
                if self.config.log_state_operations:
                    logger.debug(f"Completed {operation_name}")
                return result
            except Exception as e:
                logger.error(f"Failed {operation_name}: {e}")
                raise

        return wrapper

    return decorator


class StateFileHandler:
    """Handles file operations for state persistence."""

    def __init__(self, file_path: str, config: StateManagerConfig):
        self.file_path = file_path
        self.config = config

    def ensure_directory_exists(self):
        """Ensure the directory for the state file exists."""
        if self.config.create_missing_directories:
            directory = os.path.dirname(self.file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, mode=0o755, exist_ok=True)

    @logged_operation("file load")
    def load_state(self) -> Dict[str, Any]:
        """Load state from file with proper error handling."""
        try:
            with open(self.file_path, "r") as f:
                content = f.read().strip()
                if not content:
                    raise StateCorruptionError(f"State file is empty: {self.file_path}")
                return json.loads(content)
        except FileNotFoundError:
            raise StateAccessError(f"State file not found: {self.file_path}")
        except json.JSONDecodeError as e:
            raise StateCorruptionError(f"Invalid JSON in state file {self.file_path}: {e}")
        except PermissionError:
            raise StateAccessError(f"Permission denied accessing state file: {self.file_path}")

    @logged_operation("file save")
    def save_state(self, state: StateData):
        """Save state to file with proper error handling."""
        try:
            self.ensure_directory_exists()

            # Write to temporary file first for atomic operation
            temp_file = f"{self.file_path}.tmp"
            with open(temp_file, "w") as f:
                json.dump(state.model_dump(), f, indent=2)
                f.flush()
                os.fsync(f.fileno())  # Ensure data is written to disk

            # Atomic move to final location
            os.replace(temp_file, self.file_path)

            # Set file permissions
            os.chmod(self.file_path, self.config.file_permissions)

        except Exception as e:
            # Clean up temporary file if it exists
            if os.path.exists(f"{self.file_path}.tmp"):
                try:
                    os.unlink(f"{self.file_path}.tmp")
                except OSError:
                    pass
            raise StateAccessError(f"Failed to save state file {self.file_path}: {e}")

    def create_default_state(self) -> StateData:
        """Create and save default state file."""
        default_state = StateData(update_offset=0, users={})
        self.save_state(default_state)
        return default_state

    def create_backup(self, timestamp: Optional[int] = None) -> str:
        """Create a backup of the current state file."""
        if not os.path.exists(self.file_path):
            raise StateAccessError(f"Cannot backup non-existent file: {self.file_path}")

        backup_path = self.config.get_backup_path(self.file_path, timestamp)

        try:
            shutil.copy2(self.file_path, backup_path)
            if self.config.log_backup_operations:
                logger.info(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            raise StateAccessError(f"Failed to create backup {backup_path}: {e}")

    def cleanup_old_backups(self):
        """Remove old backup files, keeping only the most recent ones."""
        directory = os.path.dirname(self.file_path)
        basename = os.path.basename(self.file_path)

        if not directory:
            directory = "."

        # Find all backup files
        backup_files = []
        for filename in os.listdir(directory):
            if filename.startswith(f"{basename}.backup."):
                try:
                    timestamp_str = filename.split(".")[-1]
                    timestamp = int(timestamp_str)
                    backup_files.append((timestamp, os.path.join(directory, filename)))
                except (ValueError, IndexError):
                    continue

        # Sort by timestamp (newest first) and remove excess backups
        backup_files.sort(reverse=True)
        for _, backup_path in backup_files[self.config.backup_count :]:
            try:
                os.unlink(backup_path)
                if self.config.log_backup_operations:
                    logger.debug(f"Removed old backup: {backup_path}")
            except OSError as e:
                logger.warning(f"Failed to remove old backup {backup_path}: {e}")
