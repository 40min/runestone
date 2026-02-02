"""
Connection manager for WebSocket connections.

This module provides a singleton manager to handle active WebSocket connections
across the application, allowing services to interact with connected clients
without direct dependencies on API endpoints.
"""

import logging
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Singleton manager for active WebSocket connections."""

    _instance = None
    _active_connections: dict[int, WebSocket] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConnectionManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "ConnectionManager":
        """Get the singleton instance of ConnectionManager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def connect(self, user_id: int, websocket: WebSocket):
        """Register a new WebSocket connection for a user."""
        self._active_connections[user_id] = websocket
        logger.debug(f"User {user_id} connected to audio WebSocket")

    def disconnect(self, user_id: int):
        """Unregister a WebSocket connection for a user."""
        if user_id in self._active_connections:
            del self._active_connections[user_id]
            logger.debug(f"User {user_id} disconnected from audio WebSocket")

    def get_connection(self, user_id: int) -> Optional[WebSocket]:
        """Get the active WebSocket connection for a user."""
        return self._active_connections.get(user_id)


# Global instance
connection_manager = ConnectionManager.get_instance()
