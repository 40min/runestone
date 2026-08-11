"""Tests for user persistence behavior."""

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from runestone.core.exceptions import UserEmailAlreadyExistsError
from runestone.db.models import User
from runestone.db.user_repository import UserRepository


def make_user(email: str) -> User:
    """Build a valid user row for repository tests."""
    return User(email=email, hashed_password="hashed", name="User", timezone="UTC")


async def test_add_user_flushes_without_committing(user_repository):
    user = make_user("new@example.com")

    returned = await user_repository.add_user(user)

    assert returned is user
    assert user.id is not None
    await user_repository.rollback()


async def test_add_user_translates_email_unique_constraint(user_repository, db_session):
    db_session.add(make_user("taken@example.com"))
    await db_session.commit()

    with pytest.raises(UserEmailAlreadyExistsError, match="Email already registered"):
        await user_repository.add_user(make_user("taken@example.com"))

    await user_repository.rollback()


@pytest.mark.parametrize("constraint_name", ["users_email_key", "ix_users_email"])
def test_email_unique_matcher_supports_postgresql_constraint_names(constraint_name):
    violation = SimpleNamespace(sqlstate="23505", constraint_name=constraint_name)
    error = IntegrityError("INSERT INTO users", {}, violation)

    assert UserRepository._is_user_email_unique_violation(error) is True


def test_email_unique_matcher_supports_exact_sqlite_error():
    error = IntegrityError("INSERT INTO users", {}, Exception("UNIQUE constraint failed: users.email"))

    assert UserRepository._is_user_email_unique_violation(error) is True


def test_email_unique_matcher_ignores_constraint_names_outside_driver_metadata():
    error = IntegrityError(
        "INSERT INTO users /* ix_users_email users_email_key */",
        {"email": "ix_users_email"},
        SimpleNamespace(sqlstate="23505", constraint_name="ix_users_telegram_username"),
    )

    assert UserRepository._is_user_email_unique_violation(error) is False


async def test_add_user_preserves_unrelated_integrity_errors(user_repository):
    invalid_user = User(email="invalid@example.com", hashed_password=None, name="User", timezone="UTC")

    with pytest.raises(IntegrityError):
        await user_repository.add_user(invalid_user)

    await user_repository.rollback()
