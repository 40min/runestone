"""
Chat endpoints for the Teacher Agent.

This module provides API endpoints for chat interactions with the teacher agent.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from runestone.agent.schemas import ChatHistoryResponse, ChatMessage, ChatRequest, ChatResponse, ImageChatResponse
from runestone.auth.dependencies import get_current_user
from runestone.core.exceptions import RunestoneError
from runestone.core.processor import RunestoneProcessor
from runestone.db.models import User
from runestone.dependencies import get_chat_service, get_runestone_processor
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
        messages = [ChatMessage(id=m.id, role=m.role, content=m.content, created_at=m.created_at) for m in history]
        return ChatHistoryResponse(messages=messages)
    except Exception as e:
        logger.error(f"Error fetching chat history: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch chat history.")


@router.post("/image", response_model=ImageChatResponse)
async def send_image(
    file: Annotated[UploadFile, File(description="Image file to process")],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    processor: Annotated[RunestoneProcessor, Depends(get_runestone_processor)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ImageChatResponse:
    """
    Upload an image with Swedish text for OCR and translation.

    The endpoint performs OCR on the image and returns a phrase-by-phrase translation
    from the teaching agent. The translation is saved to chat history.
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        logger.warning(f"Invalid file type: {file.content_type}")
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an image file.",
        )

    # Validate file size (max 10MB)
    content = await file.read()
    file_size = len(content)

    if file_size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 10MB.",
        )

    try:
        logger.info(f"User {current_user.email} uploaded image for OCR translation")

        # Run OCR on image bytes
        ocr_result = processor.run_ocr(content)

        if not ocr_result.transcribed_text or not ocr_result.transcribed_text.strip():
            logger.warning("OCR returned empty text")
            raise HTTPException(
                status_code=400,
                detail="Could not recognize text from image",
            )

        logger.info(f"OCR extracted {len(ocr_result.transcribed_text)} characters")

        # Process OCR text through agent for translation
        response_message = await chat_service.process_image_message(current_user.id, ocr_result.transcribed_text)

        logger.info(f"Generated translation response for user {current_user.email}")

        return ImageChatResponse(message=response_message)

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except RunestoneError as e:
        logger.error(f"OCR error: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Could not recognize text from image",
        )
    except Exception as e:
        logger.error(f"Error processing image: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process image. Please try again.",
        )


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
