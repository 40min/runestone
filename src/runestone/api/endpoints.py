"""
API endpoints for Runestone image processing.

This module defines the FastAPI routes for processing Swedish textbook images
and returning structured analysis results.
"""

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from runestone.api.schemas import ErrorResponse, ProcessingResult
from runestone.config import Settings, settings
from runestone.core.exceptions import RunestoneError
from runestone.core.processor import RunestoneProcessor

router = APIRouter()


def get_settings() -> Settings:
    """Dependency injection for application settings."""
    return settings


@router.post(
    "/process",
    response_model=ProcessingResult,
    responses={
        200: {"description": "Successful processing"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Processing error"},
    },
)
async def process_image(
    file: Annotated[UploadFile, File(description="Image file to process")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProcessingResult:
    """
    Process a Swedish textbook image and return analysis results.

    This endpoint accepts an image file, performs OCR, analyzes the content,
    and returns structured learning materials including vocabulary, grammar focus,
    and additional resources.

    Args:
        file: Uploaded image file (JPG, PNG, etc.)
        settings: Application configuration

    Returns:
        ProcessingResult: Complete analysis results

    Raises:
        HTTPException: For various error conditions
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an image file.",
        )

    # Validate file size (max 10MB)
    file_size = 0
    content = await file.read()
    file_size = len(content)

    if file_size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 10MB.",
        )

    # Save uploaded file to temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "image.jpg").suffix) as temp_file:
        temp_file.write(content)
        temp_path = Path(temp_file.name)

    try:
        # Initialize processor with settings
        processor = RunestoneProcessor(settings=settings, verbose=settings.verbose)

        # Process the image
        results = processor.process_image(temp_path)

        # Convert results to Pydantic model
        processing_result = ProcessingResult(**results)

        return processing_result

    except RunestoneError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}",
        )
    finally:
        # Clean up temporary file
        if temp_path.exists():
            temp_path.unlink()


@router.get(
    "/health",
    response_model=dict,
    responses={
        200: {"description": "Service is healthy"},
    },
)
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns basic service status information.
    """
    return {"status": "healthy", "service": "runestone-api"}
