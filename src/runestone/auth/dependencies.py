"""
Authentication dependencies for FastAPI.

This module provides dependency functions for user authentication,
including the get_current_user dependency for securing endpoints.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from runestone.core.exceptions import InactiveUserError, InvalidAccessTokenError
from runestone.db.models import User
from runestone.dependencies import get_auth_service
from runestone.services.auth_service import AuthService

security = HTTPBearer()


async def get_current_user(
    token: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    """
    FastAPI dependency to get the current authenticated user.

    Extracts JWT token from Authorization header, verifies it, and retrieves
    the corresponding user from the database.

    Args:
        token: JWT token from Authorization header
        service: Authentication use-case service

    Returns:
        User model instance for the authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        return await service.resolve_access_token(token.credentials)
    except InvalidAccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
