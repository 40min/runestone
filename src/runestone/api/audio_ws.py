"""
WebSocket endpoint for audio streaming.

This module provides a WebSocket endpoint for streaming TTS audio to clients.
"""

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from runestone.auth.security import verify_token
from runestone.core.connection_manager import connection_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/audio")
async def audio_websocket(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket endpoint for receiving TTS audio from the server.

    Protocol:
    1. Client connects with auth token as query param
    2. Server validates token and accepts connection
    3. Server pushes binary audio chunks when TTS is generated
    4. Server sends JSON: {"status": "complete"} when audio is done
    5. Connection stays open for subsequent messages

    Args:
        websocket: The WebSocket connection
        token: JWT authentication token
    """
    # Validate token and extract user_id
    try:
        payload = verify_token(token)
        if not payload:
            logger.warning("WebSocket connection rejected: invalid token")
            await websocket.close(code=4001)
            return
        user_id = int(payload.get("sub"))
    except Exception as e:
        logger.warning(f"WebSocket token validation failed: {e}")
        await websocket.close(code=4001)
        return

    await websocket.accept()
    connection_manager.connect(user_id, websocket)
    logger.info(f"Audio WebSocket connected for user {user_id}")

    try:
        # Keep connection alive, waiting for disconnect
        # We don't expect messages from client, just keep-alive pings
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"Audio WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"Audio WebSocket error for user {user_id}: {e}")
    finally:
        connection_manager.disconnect(user_id)
