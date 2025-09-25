"""
Configuration for StateManager operations.
"""

import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class StateManagerConfig:
    """Configuration settings for StateManager."""

    # Backup settings
    backup_count: int = 5
    auto_backup_on_save: bool = True
    backup_file_pattern: str = "{path}.backup.{timestamp}"

    # File settings
    file_permissions: int = 0o600
    create_missing_directories: bool = True
    offset_filename: str = "offset.txt"

    # Logging settings
    log_state_operations: bool = True
    log_backup_operations: bool = True

    # Validation settings
    strict_validation: bool = True
    validate_user_data: bool = True

    def get_backup_path(self, original_path: str, timestamp: Optional[int] = None) -> str:
        """Generate backup file path with timestamp."""
        if timestamp is None:
            timestamp = int(time.time())
        return self.backup_file_pattern.format(path=original_path, timestamp=timestamp)
