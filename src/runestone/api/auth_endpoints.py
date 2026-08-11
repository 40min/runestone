"""
Authentication endpoints for Runestone.

This module provides registration and login endpoints for user authentication.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from runestone.api.schemas import LoginRequest, RegisterRequest
from runestone.core.exceptions import InactiveUserError, InvalidCredentialsError, RegistrationError
from runestone.dependencies import get_auth_service
from runestone.services.auth_service import AuthService

router = APIRouter()


@router.post("/register")
async def register(
    user_data: RegisterRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Register a new user.

    Args:
        user_data: Registration email and password
        service: Authentication use-case service

    Returns:
        User creation confirmation

    Raises:
        HTTPException: If email already exists or password is too short
    """
    try:
        user = await service.register_user(user_data.email, user_data.password)
    except RegistrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"message": "User registered successfully", "user_id": user.id}


@router.post("/")
async def login(
    login_data: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Authenticate user and return access token.

    Args:
        login_data: Login request with email and password
        service: Authentication use-case service

    Returns:
        Access token and token type

    Raises:
        HTTPException: If credentials are invalid
    """
    try:
        access_token = await service.login(login_data.email, login_data.password)
    except (InvalidCredentialsError, InactiveUserError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return {"access_token": access_token, "token_type": "bearer"}
