"""
Chat endpoints for the Teacher Agent.

This module provides API endpoints for chat interactions with the teacher agent.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from runestone.agent.schemas import ChatHistoryResponse, ChatMessage, ChatRequest, ChatResponse
from runestone.auth.dependencies import get_current_user
from runestone.db.models import User
from runestone.dependencies import get_chat_service
from runestone.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatResponse:
    """
    Send a message to the chat agent and receive a response.
    History is now managed on the backend.
    """
    try:
        logger.info(f"User {current_user.email} sent message: {request.message[:50]}...")

        # Generate response using the chat service which handles persistence
        response_message = await chat_service.process_message(current_user.id, request.message)

        logger.info(f"Generated response for user {current_user.email}")

        return ChatResponse(message=response_message)

    except Exception as e:
        logger.error(f"Error generating chat response: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate response. Please try again."
        )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_history(
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatHistoryResponse:
    """
    Get the chat history for the current user.
    """
    try:
        history = chat_service.get_history(current_user.id)
        # Convert models to schemas
        messages = [ChatMessage(role=m.role, content=m.content, created_at=m.created_at) for m in history]
        return ChatHistoryResponse(messages=messages)
    except Exception as e:
        logger.error(f"Error fetching chat history: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch chat history.")


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Clear the chat history for the current user.
    """
    try:
        chat_service.clear_history(current_user.id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to clear chat history.")
