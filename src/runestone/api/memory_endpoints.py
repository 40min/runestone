"""
API endpoints for memory item operations.

This module defines the FastAPI routes for memory item management.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from runestone.api.memory_item_schemas import (
    MemoryCategory,
    MemoryItemCreate,
    MemoryItemResponse,
    MemoryItemStatusUpdate,
)
from runestone.auth.dependencies import get_current_user
from runestone.core.exceptions import UserNotFoundError
from runestone.core.logging_config import get_logger
from runestone.db.models import User
from runestone.dependencies import get_memory_item_service
from runestone.services.memory_item_service import MemoryItemService

router = APIRouter()
logger = get_logger(__name__)


@router.get(
    "/memory",
    response_model=list[MemoryItemResponse],
    responses={
        200: {"description": "Memory items retrieved successfully"},
        401: {"description": "Not authenticated"},
    },
)
async def list_memory_items(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MemoryItemService, Depends(get_memory_item_service)],
    category: Optional[MemoryCategory] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=200, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> list[MemoryItemResponse]:
    """
    List memory items with optional filters.

    Supports infinite scroll with limit/offset pagination.
    """
    try:
        return service.list_memory_items(current_user.id, category, status, limit, offset)
    except Exception as e:
        logger.error(f"Failed to list memory items for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve memory items")


@router.post(
    "/memory",
    response_model=MemoryItemResponse,
    responses={
        200: {"description": "Memory item created/updated successfully"},
        400: {"description": "Invalid input data"},
        401: {"description": "Not authenticated"},
    },
)
async def create_memory_item(
    item_data: MemoryItemCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MemoryItemService, Depends(get_memory_item_service)],
) -> MemoryItemResponse:
    """
    Create or update a memory item.

    Uses upsert logic based on (user_id, category, key) uniqueness.
    """
    try:
        return service.upsert_memory_item(
            user_id=current_user.id,
            category=item_data.category,
            key=item_data.key,
            content=item_data.content,
            status=item_data.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create memory item for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create memory item")


@router.put(
    "/memory/{item_id}/status",
    response_model=MemoryItemResponse,
    responses={
        200: {"description": "Status updated successfully"},
        400: {"description": "Invalid status"},
        401: {"description": "Not authenticated"},
        404: {"description": "Item not found"},
    },
)
async def update_memory_item_status(
    item_id: int,
    status_data: MemoryItemStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MemoryItemService, Depends(get_memory_item_service)],
) -> MemoryItemResponse:
    """
    Update the status of a memory item.
    """
    try:
        return service.update_item_status(item_id, status_data.status, current_user.id)
    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update status for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update status")


@router.post(
    "/memory/{item_id}/promote",
    response_model=MemoryItemResponse,
    responses={
        200: {"description": "Item promoted successfully"},
        400: {"description": "Cannot promote this item"},
        401: {"description": "Not authenticated"},
        404: {"description": "Item not found"},
    },
)
async def promote_memory_item(
    item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MemoryItemService, Depends(get_memory_item_service)],
) -> MemoryItemResponse:
    """
    Promote a mastered area_to_improve item to knowledge_strength.
    """
    try:
        return service.promote_to_strength(item_id, current_user.id)
    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to promote item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to promote item")


@router.delete(
    "/memory/{item_id}",
    responses={
        204: {"description": "Item deleted successfully"},
        401: {"description": "Not authenticated"},
        404: {"description": "Item not found"},
    },
    status_code=204,
)
async def delete_memory_item(
    item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MemoryItemService, Depends(get_memory_item_service)],
) -> None:
    """
    Delete a memory item.
    """
    try:
        service.delete_item(item_id, current_user.id)
    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete item")


@router.delete(
    "/memory",
    responses={
        200: {"description": "Category cleared successfully"},
        400: {"description": "Invalid category"},
        401: {"description": "Not authenticated"},
    },
)
async def clear_memory_category(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MemoryItemService, Depends(get_memory_item_service)],
    category: MemoryCategory = Query(..., description="Category to clear"),
) -> dict:
    """
    Clear all items in a category.
    """
    try:
        count = service.clear_category(current_user.id, category)
        return {"deleted_count": count, "category": category.value}
    except Exception as e:
        logger.error(f"Failed to clear category {category} for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear category")
