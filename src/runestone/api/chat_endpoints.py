"""
Chat endpoints for the Teacher Agent.

This module provides API endpoints for chat interactions with the teacher agent.
"""

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status

from runestone.agents.schemas import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ImageChatResponse,
    VoiceTranscriptionResponse,
)
from runestone.auth.dependencies import get_current_user
from runestone.config import settings
from runestone.core.constants import LANGUAGE_CODE_MAP
from runestone.core.exceptions import RunestoneError
from runestone.db.models import User
from runestone.dependencies import get_chat_service, get_voice_service
from runestone.services.chat_service import ChatService
from runestone.services.voice_service import VoiceService

logger = logging.getLogger(__name__)

router = APIRouter()

SUPPORTED_TRANSCRIPTION_LANGUAGES = set(LANGUAGE_CODE_MAP) | set(LANGUAGE_CODE_MAP.values())


def _validate_transcription_language(language: str | None) -> str | None:
    """Validate explicit speech-to-text language form values."""
    if language is None:
        return None

    selected_language = language.strip()
    if not selected_language or selected_language not in SUPPORTED_TRANSCRIPTION_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported speech language.",
        )

    return selected_language


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
        response_message, sources = await chat_service.process_message(
            current_user.id, request.message, tts_expected=request.tts_expected, speed=request.speed
        )

        logger.info(f"Generated response for user {current_user.email}")

        return ChatResponse(message=response_message, sources=sources)

    except Exception as e:
        logger.error(f"Error generating chat response: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate response. Please try again."
        )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_history(
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    after_id: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    client_chat_id: str | None = Query(None),
) -> ChatHistoryResponse:
    """
    Get active chat history for the current user.
    """
    try:
        return await chat_service.get_history_response(
            current_user.id,
            after_id=after_id,
            limit=limit,
            client_chat_id=client_chat_id,
        )
    except Exception as e:
        logger.error(f"Error fetching chat history: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch chat history.")


@router.post("/image", response_model=ImageChatResponse)
async def send_image(
    file: Annotated[UploadFile, File(description="Image file to process")],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
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

    # Validate file size
    content = await file.read()
    file_size = len(content)
    max_size_bytes = settings.chat_image_max_size_mb * 1024 * 1024

    if file_size > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.chat_image_max_size_mb}MB.",
        )

    try:
        start_time = time.time()
        logger.info(f"[IMAGE_UPLOAD] User {current_user.email} uploaded image ({file_size} bytes), starting OCR")

        # Process OCR text through agent for translation
        response_message = await chat_service.process_image_message(current_user.id, content)

        elapsed = time.time() - start_time
        logger.info(f"[IMAGE_UPLOAD] Image processing completed for user {current_user.email} in {elapsed:.3f}s")

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


@router.delete(
    "/history",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Start a new chat session",
    responses={
        204: {
            "description": (
                "New chat session started. Previous messages are archived and retained according to retention policy."
            )
        },
        500: {"description": "Failed to start new chat session"},
    },
)
async def start_new_chat(
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Start a new chat session for the current user.

    Note:
        This endpoint rotates the active chat session ID and does not physically delete
        previously persisted messages immediately. Old sessions remain archived until
        retention cleanup removes them.
    """
    try:
        await chat_service.start_new_chat(current_user.id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Error starting new chat session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to start new chat session."
        )


@router.post("/transcribe-voice", response_model=VoiceTranscriptionResponse)
async def transcribe_voice(
    file: Annotated[UploadFile, File(description="Audio file to transcribe (WebM format)")],
    improve: Annotated[bool, Form(description="Whether to enhance the transcription")] = True,
    language: Annotated[
        str | None, Form(description="Speech language as a supported full name or ISO-639-1 code")
    ] = None,
    voice_service: Annotated[VoiceService, Depends(get_voice_service)] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> VoiceTranscriptionResponse:
    """
    Transcribe voice audio to text.

    The endpoint accepts audio files (WebM Opus format) and returns transcribed text.
    Optionally, the transcription can be enhanced for grammar and clarity.
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("audio/"):
        logger.warning(f"Invalid file type for voice transcription: {file.content_type}")
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an audio file.",
        )

    # Read and validate file size
    content = await file.read()
    file_size = len(content)
    max_size_bytes = settings.voice_max_file_size_mb * 1024 * 1024

    if file_size > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.voice_max_file_size_mb}MB.",
        )

    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail="Empty audio file.",
        )

    transcription_language = _validate_transcription_language(language)
    if transcription_language is None:
        profile_language = current_user.mother_tongue.strip() if current_user.mother_tongue else None
        transcription_language = (
            profile_language if profile_language in SUPPORTED_TRANSCRIPTION_LANGUAGES else "Swedish"
        )

    try:
        logger.info(f"User {current_user.email} requested voice transcription (improve={improve})")
        transcribed_text = await voice_service.process_voice_input(
            content, improve=improve, language=transcription_language
        )

        logger.info(f"Voice transcription completed for user {current_user.email}")

        return VoiceTranscriptionResponse(text=transcribed_text)

    except RunestoneError as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error processing voice: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to transcribe voice. Please try again.",
        )
