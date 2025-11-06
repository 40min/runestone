"""
API endpoints for user profile operations.

This module defines the FastAPI routes for user profile management.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from runestone.api.schemas import UserProfileResponse, UserProfileUpdate
from runestone.auth.dependencies import get_current_user
from runestone.core.logging_config import get_logger
from runestone.db.models import User
from runestone.dependencies import get_user_service
from runestone.services.user_service import UserService

router = APIRouter()
logger = get_logger(__name__)


@router.get(
    "/me",
    response_model=UserProfileResponse,
    responses={
        200: {"description": "User profile retrieved successfully"},
        401: {"description": "Not authenticated"},
    },
)
async def get_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfileResponse:
    """
    Get current user profile with stats.

    Returns user profile information including vocabulary statistics.
    """
    try:
        # TODO: fresh data from db should be fetched, not data from the time
        # of login
        return service.get_user_profile(current_user)
    except Exception as e:
        logger.error(f"Failed to get user profile for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve user profile",
        )


@router.put(
    "/me",
    response_model=UserProfileResponse,
    responses={
        200: {"description": "User profile updated successfully"},
        400: {"description": "Invalid input data"},
        401: {"description": "Not authenticated"},
        422: {"description": "Validation error"},
        500: {"description": "Database error"},
    },
)
async def update_user_profile(
    update_data: UserProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfileResponse:
    """
    Update current user profile.

    Allows updating user information like name, surname, timezone, and password.
    """
    try:
        return service.update_user_profile(current_user, update_data)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to update user profile for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update user profile",
        )
