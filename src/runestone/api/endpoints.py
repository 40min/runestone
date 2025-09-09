"""
API endpoints for Runestone image processing.

This module defines the FastAPI routes for processing Swedish textbook images
and returning structured analysis results.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from runestone.api.schemas import (
    AnalysisRequest,
    ContentAnalysis,
    ErrorResponse,
    OCRResult,
    ResourceRequest,
    ResourceResponse,
)
from runestone.config import Settings, settings
from runestone.core.exceptions import RunestoneError
from runestone.core.processor import RunestoneProcessor

router = APIRouter()


def get_settings() -> Settings:
    """Dependency injection for application settings."""
    return settings


@router.post(
    "/ocr",
    response_model=OCRResult,
    responses={
        200: {"description": "OCR successful"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "OCR error"},
    },
)
async def process_ocr(
    file: Annotated[UploadFile, File(description="Image file to process")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OCRResult:
    """
    Extract text from a Swedish textbook image using OCR.

    This endpoint accepts an image file and returns the extracted text.

    Args:
        file: Uploaded image file (JPG, PNG, etc.)
        settings: Application configuration

    Returns:
        OCRResult: Extracted text and metadata

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
    content = await file.read()
    file_size = len(content)

    if file_size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 10MB.",
        )

    try:
        # Initialize processor with settings
        processor = RunestoneProcessor(settings=settings, verbose=settings.verbose)

        # Run OCR on image bytes
        ocr_result = processor.run_ocr(content)

        # Convert to Pydantic model
        return OCRResult(**ocr_result)

    except RunestoneError as e:
        raise HTTPException(
            status_code=500,
            detail=f"OCR failed: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}",
        )


@router.post(
    "/analyze",
    response_model=ContentAnalysis,
    responses={
        200: {"description": "Analysis successful"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Analysis error"},
    },
)
async def analyze_content(
    request: AnalysisRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ContentAnalysis:
    """
    Analyze extracted text content.

    This endpoint accepts OCR text and returns grammar focus and vocabulary analysis.

    Args:
        request: Analysis request with extracted text
        settings: Application configuration

    Returns:
        ContentAnalysis: Grammar and vocabulary analysis

    Raises:
        HTTPException: For various error conditions
    """
    try:
        # Initialize processor with settings
        processor = RunestoneProcessor(settings=settings, verbose=settings.verbose)

        # Run content analysis
        analysis_result = processor.run_analysis(request.text)

        # Convert to Pydantic model
        return ContentAnalysis(**analysis_result)

    except RunestoneError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}",
        )


@router.post(
    "/resources",
    response_model=ResourceResponse,
    responses={
        200: {"description": "Resource search successful"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Resource search error"},
    },
)
async def find_resources(
    request: ResourceRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResourceResponse:
    """
    Find additional learning resources based on content analysis.

    This endpoint accepts analysis results and returns supplementary learning information.

    Args:
        request: Resource request with analysis data
        settings: Application configuration

    Returns:
        ResourceResponse: Additional learning resources

    Raises:
        HTTPException: For various error conditions
    """
    try:
        # Initialize processor with settings
        processor = RunestoneProcessor(settings=settings, verbose=settings.verbose)

        # Run resource search
        extra_info = processor.run_resource_search(request.analysis.model_dump())

        # Return response
        return ResourceResponse(extra_info=extra_info)

    except RunestoneError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Resource search failed: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}",
        )


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
