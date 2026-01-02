"""
Chat endpoints for the Teacher Agent.

This module provides API endpoints for chat interactions with the teacher agent.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from runestone.agent.schemas import ChatRequest, ChatResponse
from runestone.agent.service import AgentService
from runestone.auth.dependencies import get_current_user
from runestone.db.models import User
from runestone.dependencies import get_agent_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatResponse:
    """
    Send a message to the chat agent and receive a response.

    Args:
        request: Chat request containing message and history
        agent_service: Agent service from dependency injection
        current_user: Current authenticated user

    Returns:
        ChatResponse with the agent's reply

    Raises:
        HTTPException: If the agent fails to generate a response
    """
    try:
        logger.info(f"User {current_user.email} sent message: {request.message[:50]}...")

        # Generate response using the agent service
        response_message = agent_service.generate_response(request.message, request.history)

        logger.info(f"Generated response for user {current_user.email}")

        return ChatResponse(message=response_message)

    except Exception as e:
        logger.error(f"Error generating chat response: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate response. Please try again.")
