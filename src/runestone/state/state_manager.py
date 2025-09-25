"""
Optimized StateManager with improved architecture and error handling.
"""

import logging
import os
import threading
from typing import Any, Dict, Optional

from src.runestone.core.exceptions import UserNotAuthorised

from .state_config import StateManagerConfig
from .state_exceptions import StateAccessError, StateCorruptionError
from .state_types import StateData, UserData
from .state_utils import StateFileHandler, logged_operation, with_lock

logger = logging.getLogger(__name__)


class StateManager:
    """
    Optimized singleton state manager with thread-safe operations.

    Features:
    - Thread-safe singleton pattern
    - Atomic transactions
    - Backup and recovery
    - Comprehensive validation
    - Proper error handling
    - Configurable behavior
    """

    _instance: Optional["StateManager"] = None
    _initialized: bool = False
    _lock_creation = threading.Lock()  # For singleton creation

    @classmethod
    def _reset_for_testing(cls):
        """Reset singleton for testing purposes."""
        with cls._lock_creation:
            cls._instance = None
            cls._initialized = False

    def __new__(cls, state_file_path: str = "state/state.json", config: Optional[StateManagerConfig] = None):
        """Create or return existing singleton instance."""
        with cls._lock_creation:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self, state_file_path: str = "state/state.json", config: Optional[StateManagerConfig] = None):
        """Initialize StateManager instance (only once due to singleton pattern)."""
        if StateManager._initialized:
            return

        # Initialize instance attributes
        self.state_file_path = state_file_path
        self.config = config or StateManagerConfig()
        self._state: Optional[StateData] = None
        self._lock = threading.RLock()

        # Initialize components
        self.file_handler = StateFileHandler(self.state_file_path, self.config)

        # Ensure state file exists
        self._ensure_state_file_exists()

        # Mark as initialized
        StateManager._initialized = True

        logger.info(f"StateManager initialized with file: {self.state_file_path}")

    def _ensure_state_file_exists(self):
        """Ensure the state file exists, creating it if necessary."""
        if not os.path.exists(self.state_file_path):
            logger.info(f"Creating new state file: {self.state_file_path}")
            with self._lock:
                self._state = self.file_handler.create_default_state()

    @with_lock
    @logged_operation("state load")
    def _get_state(self) -> StateData:
        """Get current state, loading from file if necessary."""
        if self._state is None:
            try:
                raw_state = self.file_handler.load_state()

                # Handle migration: extract update_offset from state.json to separate file
                if 'update_offset' in raw_state:
                    offset_value = raw_state.pop('update_offset')
                    try:
                        offset_file = self._get_offset_file_path()
                        os.makedirs(os.path.dirname(offset_file), exist_ok=True)
                        with open(offset_file, 'w') as f:
                            f.write(str(offset_value))
                        logger.info(f"Migrated update_offset {offset_value} to separate file")
                    except Exception as e:
                        logger.warning(f"Failed to migrate update_offset: {e}")

                # Pydantic will validate the structure automatically
                self._state = StateData(**raw_state)
            except (StateAccessError, StateCorruptionError, ValueError) as e:
                logger.error(f"Failed to load state: {e}")
                raise

        # Return direct reference - StateManager controls all access
        return self._state  # type: ignore

    @with_lock
    @logged_operation("state save")
    def save_state_to_file(self):
        """Explicitly save current state to file."""
        if self._state is None:
            raise StateAccessError("No state to save")

        try:
            # Create backup if configured
            if self.config.auto_backup_on_save and os.path.exists(self.state_file_path):
                self.file_handler.create_backup()
                self.file_handler.cleanup_old_backups()

            # Save state (Pydantic handles validation)
            self.file_handler.save_state(self._state)

        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            raise

    # Public API methods

    def get_user(self, username: str) -> Optional[UserData]:
        """Get user data by username."""
        try:
            state = self._get_state()
            return state.users.get(username)
        except Exception as e:
            logger.error(f"Failed to get user '{username}': {e}")
            raise

    def update_user(self, username: str, user_data: UserData):
        """Update existing user data."""
        try:
            state = self._get_state()  # Already thread-safe via @with_lock

            if username not in state.users:
                raise UserNotAuthorised(f"User '{username}' does not exist and cannot be updated.")

            # If user_data is a dict, convert it to UserData
            if isinstance(user_data, dict):
                user_data = UserData(**user_data)

            state.users[username] = user_data

            # Explicitly save changes to file
            self.save_state_to_file()
            logger.debug(f"Updated user '{username}'")

        except UserNotAuthorised:
            raise
        except Exception as e:
            logger.error(f"Failed to update user '{username}': {e}")
            raise

    def get_active_users(self) -> Dict[str, UserData]:
        """Get dictionary of active users (username -> UserData)."""
        try:
            state = self._get_state()
            return {username: user_data for username, user_data in state.users.items() if user_data.is_active}
        except Exception as e:
            logger.error(f"Failed to get active users: {e}")
            raise

    @with_lock
    def get_update_offset(self) -> int:
        """Get current update offset from separate file."""
        try:
            offset_file = self._get_offset_file_path()
            if os.path.exists(offset_file):
                with open(offset_file, 'r') as f:
                    return int(f.read().strip())
            return 0
        except Exception as e:
            logger.error(f"Failed to get update offset: {e}")
            return 0

    @with_lock
    def set_update_offset(self, offset: int):
        """Set update offset to separate file (no backup triggered)."""
        try:
            offset_file = self._get_offset_file_path()
            # Ensure directory exists
            os.makedirs(os.path.dirname(offset_file), exist_ok=True)

            with open(offset_file, 'w') as f:
                f.write(str(offset))
            logger.debug(f"Set update offset to {offset}")
        except Exception as e:
            logger.error(f"Failed to set update offset: {e}")
            raise

    def _get_offset_file_path(self) -> str:
        """Get path to offset file based on state file path."""
        state_dir = os.path.dirname(self.state_file_path)
        return os.path.join(state_dir, self.config.offset_filename)

    # Additional utility methods
    def force_reload(self):
        """Force reload of state from file."""
        logger.info("Forcing state reload from file")
        with self._lock:
            self._state = None
        self._get_state()  # This will trigger a reload

    def get_state_info(self) -> Dict[str, Any]:
        """Get information about current state for debugging."""
        return {
            "state_file_path": self.state_file_path,
            "file_exists": os.path.exists(self.state_file_path),
            "state_loaded": self._state is not None,
            "config": self.config.__dict__,
        }
