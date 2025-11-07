"""
Authentication dependencies for FastAPI.

This module provides dependency functions for user authentication,
including the get_current_user dependency for securing endpoints.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from runestone.auth.security import verify_token
from runestone.db.database import get_db
from runestone.db.models import User

security = HTTPBearer()


def get_current_user(token: str = Depends(security), db: Session = Depends(get_db)) -> User:
    """
    FastAPI dependency to get the current authenticated user.

    Extracts JWT token from Authorization header, verifies it, and retrieves
    the corresponding user from the database.

    Args:
        token: JWT token from Authorization header
        db: Database session

    Returns:
        User model instance for the authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    payload = verify_token(token.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id_int = int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id_int).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
