"""
API endpoints for Runestone image processing.

This module defines the FastAPI routes for processing Swedish textbook images
and returning structured analysis results.
"""

from typing import Annotated, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from runestone.api.schemas import (
    AnalysisRequest,
    ContentAnalysis,
    ErrorResponse,
    OCRResult,
    ResourceRequest,
    ResourceResponse,
    Vocabulary,
    VocabularyImproveRequest,
    VocabularyImproveResponse,
    VocabularyItemCreate,
    VocabularySaveRequest,
    VocabularyUpdate,
)
from runestone.config import Settings
from runestone.core.exceptions import RunestoneError, VocabularyItemExists
from runestone.core.logging_config import get_logger
from runestone.core.processor import RunestoneProcessor
from runestone.dependencies import get_settings, get_vocabulary_service
from runestone.services.vocabulary_service import VocabularyService

router = APIRouter()
logger = get_logger(__name__)


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

        # Convert request data to dict format expected by processor
        analysis_data = {
            "search_needed": {
                "query_suggestions": request.analysis.search_needed.query_suggestions,
                "should_search": request.analysis.search_needed.should_search,
            },
            "core_topics": request.analysis.core_topics,
        }

        # Run resource search with the data
        extra_info = processor.run_resource_search(analysis_data)

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


@router.post(
    "/vocabulary",
    response_model=dict,
    responses={
        200: {"description": "Vocabulary saved successfully"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        500: {"model": ErrorResponse, "description": "Database error"},
    },
)
async def save_vocabulary(
    request: VocabularySaveRequest,
    service: Annotated[VocabularyService, Depends(get_vocabulary_service)],
) -> dict:
    """
    Save vocabulary items to the database.

    This endpoint accepts a list of vocabulary items and saves them to the database,
    ensuring uniqueness based on word_phrase.

    Args:
        request: Vocabulary save request with items
        service: Vocabulary service

    Returns:
        dict: Success message

    Raises:
        HTTPException: For database errors
    """
    try:
        return service.save_vocabulary(request.items)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save vocabulary: {str(e)}",
        )


@router.post(
    "/vocabulary/item",
    response_model=Vocabulary,
    responses={
        200: {"description": "Vocabulary item created successfully"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Database error"},
    },
)
async def save_vocabulary_item(
    request: VocabularyItemCreate,
    service: Annotated[VocabularyService, Depends(get_vocabulary_service)],
) -> Vocabulary:
    """
    Save a single vocabulary item to the database.

    This endpoint accepts a single vocabulary item and saves it to the database,
    ensuring uniqueness based on word_phrase.

    Args:
        request: Vocabulary item create request
        service: Vocabulary service

    Returns:
        Vocabulary: The created vocabulary item

    Raises:
        HTTPException: For database errors
    """
    try:
        return service.save_vocabulary_item(request)

    except VocabularyItemExists as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save vocabulary item: {str(e)}",
        )


@router.get(
    "/vocabulary",
    response_model=List[Vocabulary],
    responses={
        200: {"description": "Vocabulary retrieved successfully"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        500: {"model": ErrorResponse, "description": "Database error"},
    },
)
async def get_vocabulary(
    service: Annotated[VocabularyService, Depends(get_vocabulary_service)],
    limit: int = 100,
    search_query: str | None = None,
) -> List[Vocabulary]:
    """
    Retrieve vocabulary items, optionally filtered by search query.

    This endpoint returns vocabulary items from the database for the current user.
    If a search query is provided, it filters items by word_phrase using case-insensitive
    wildcard (*) pattern matching. Otherwise, returns the most recent items ordered
    by creation date (newest first).

    Args:
        limit: Maximum number of items to return (default: 100)
        search_query: Optional search term to filter vocabulary by word_phrase
        service: Vocabulary service

    Returns:
        List[Vocabulary]: List of vocabulary items

    Raises:
        HTTPException: For database errors or invalid parameters
    """
    try:
        if limit <= 0 or limit > 100:
            raise HTTPException(
                status_code=400,
                detail="Limit must be between 1 and 100",
            )

        return service.get_vocabulary(limit, search_query)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve vocabulary: {str(e)}",
        )


@router.put(
    "/vocabulary/{item_id}",
    response_model=Vocabulary,
    responses={
        200: {"description": "Vocabulary item updated successfully"},
        404: {"model": ErrorResponse, "description": "Vocabulary item not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Database error"},
    },
)
async def update_vocabulary(
    item_id: int,
    request: VocabularyUpdate,
    service: Annotated[VocabularyService, Depends(get_vocabulary_service)],
) -> Vocabulary:
    """
    Update a vocabulary item.

    This endpoint updates a specific vocabulary item by its ID.
    Only the provided fields will be updated.

    Args:
        item_id: The ID of the vocabulary item to update
        request: The update data
        service: Vocabulary service

    Returns:
        Vocabulary: The updated vocabulary item

    Raises:
        HTTPException: For not found or database errors
    """
    try:
        return service.update_vocabulary_item(item_id, request)

    except VocabularyItemExists as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update vocabulary: {str(e)}",
        )


@router.delete(
    "/vocabulary/{item_id}",
    response_model=dict,
    responses={
        200: {"description": "Vocabulary item deleted successfully"},
        404: {"model": ErrorResponse, "description": "Vocabulary item not found"},
        500: {"model": ErrorResponse, "description": "Database error"},
    },
)
async def delete_vocabulary(
    item_id: int,
    service: Annotated[VocabularyService, Depends(get_vocabulary_service)],
) -> dict:
    """
    Delete a vocabulary item completely from the database.

    This endpoint completely removes a vocabulary item by its ID.
    This is a hard delete operation.

    Args:
        item_id: The ID of the vocabulary item to delete
        service: Vocabulary service

    Returns:
        dict: Success message

    Raises:
        HTTPException: For not found or database errors
    """
    try:
        deleted = service.delete_vocabulary_item(item_id)

        if not deleted:
            raise ValueError(f"Vocabulary item with id {item_id} not found")

        return {"message": "Vocabulary item deleted successfully"}

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete vocabulary item: {str(e)}",
        )


@router.post(
    "/vocabulary/improve",
    response_model=VocabularyImproveResponse,
    responses={
        200: {"description": "Vocabulary improvement successful"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "LLM error"},
    },
)
async def improve_vocabulary(
    request: VocabularyImproveRequest,
    service: Annotated[VocabularyService, Depends(get_vocabulary_service)],
) -> VocabularyImproveResponse:
    """
    Improve a vocabulary item using LLM.

    This endpoint accepts a word/phrase and uses LLM to generate translation
    and example phrase for vocabulary improvement.

    Args:
        request: Vocabulary improvement request with word/phrase
        service: Vocabulary service

    Returns:
        VocabularyImproveResponse: Improved vocabulary data

    Raises:
        HTTPException: For LLM errors
    """
    try:
        return service.improve_item(request)

    except Exception:
        logger.exception("Failed to improve vocabulary")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while improving vocabulary.",
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
