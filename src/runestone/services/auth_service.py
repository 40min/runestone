"""Authentication use cases over the user account repository."""

from datetime import timedelta

from runestone.auth.security import create_access_token, hash_password, verify_password, verify_token
from runestone.config import Settings
from runestone.core.exceptions import (
    InactiveUserError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    RegistrationError,
    UserEmailAlreadyExistsError,
)
from runestone.db.models import User
from runestone.db.user_repository import UserRepository


class AuthService:
    """Coordinate account registration and authentication for API transports."""

    def __init__(self, user_repository: UserRepository, settings: Settings):
        """Initialize authentication with required persistence and configuration."""
        self.user_repository = user_repository
        self.settings = settings

    async def register_user(self, email: str | None, password: str | None) -> User:
        """Validate and persist a new inactive user in one transaction."""
        if not email or not password:
            raise RegistrationError("Email and password are required")

        if len(password) < self.settings.min_password_length:
            raise RegistrationError(f"Password must be at least {self.settings.min_password_length} characters long")

        if await self.user_repository.get_by_email(email):
            raise UserEmailAlreadyExistsError("Email already registered")

        user = User(
            email=email,
            hashed_password=hash_password(password),
            name=email.split("@")[0],
            timezone="UTC",
            pages_recognised_count=0,
        )

        try:
            await self.user_repository.add_user(user)
            await self.user_repository.commit()
        except Exception:
            await self.user_repository.rollback()
            raise

        return user

    async def login(self, email: str, password: str) -> str:
        """Authenticate active user credentials and return an access token."""
        user = await self.user_repository.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Incorrect email or password")

        if not user.active:
            raise InactiveUserError("User is not active")

        return create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(days=self.settings.jwt_expiration_days),
        )

    async def resolve_access_token(self, token: str) -> User:
        """Verify an access token and return its current active user."""
        payload = verify_token(token)
        if not payload:
            raise InvalidAccessTokenError("Invalid authentication credentials")

        user_id = payload.get("sub")
        if not user_id:
            raise InvalidAccessTokenError("Invalid token payload")

        try:
            user_id_int = int(user_id)
        except (TypeError, ValueError) as exc:
            raise InvalidAccessTokenError("Invalid user ID in token") from exc

        user = await self.user_repository.get_by_id(user_id_int)
        if not user:
            raise InvalidAccessTokenError("User not found")

        if not user.active:
            raise InactiveUserError("User is not active")

        return user
