"""
Authentication endpoints for Runestone.

This module provides registration and login endpoints for user authentication.
"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from runestone.auth.security import create_access_token, hash_password, verify_password
from runestone.config import settings
from runestone.db.database import get_db
from runestone.db.models import User

router = APIRouter()


@router.post("/register")
async def register(user_data: dict, db: Annotated[Session, Depends(get_db)]):
    """
    Register a new user.

    Args:
        user_data: Dictionary containing 'email' and 'password'
        db: Database session

    Returns:
        User creation confirmation

    Raises:
        HTTPException: If email already exists or password is too short
    """
    email = user_data.get("email")
    password = user_data.get("password")

    if not email or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email and password are required")

    if len(password) < settings.min_password_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.min_password_length} characters long",
        )

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Create new user
    hashed_password = hash_password(password)
    db_user = User(
        email=email,
        hashed_password=hashed_password,
        name=email.split("@")[0],  # Use email prefix as default name
        timezone="UTC",
        pages_recognised_count=0,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {"message": "User registered successfully", "user_id": db_user.id}


@router.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Annotated[Session, Depends(get_db)]):
    """
    Authenticate user and return access token.

    Args:
        form_data: OAuth2 form data with username (email) and password
        db: Database session

    Returns:
        Access token and token type

    Raises:
        HTTPException: If credentials are invalid
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(days=settings.jwt_expiration_days)
    access_token = create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)

    return {"access_token": access_token, "token_type": "bearer"}
