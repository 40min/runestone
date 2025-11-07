#!/usr/bin/env python3
"""
Password reset script for Runestone.

This script allows administrators to reset a user's password to a default value.
"""

import argparse
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from runestone.auth.security import hash_password  # noqa: E402
from runestone.db.database import get_db  # noqa: E402
from runestone.db.models import User  # noqa: E402


def reset_password(email: str) -> None:
    """
    Reset the password for a user with the given email.

    Args:
        email: Email address of the user

    Raises:
        ValueError: If user not found
    """
    default_password = "test123test"

    # Get database session
    db = next(get_db())

    try:
        # Find user by email
        user = db.query(User).filter(User.email == email).first()

        if not user:
            raise ValueError(f"User with email '{email}' not found")

        # Hash and update password
        user.hashed_password = hash_password(default_password)

        # Commit changes
        db.commit()

        print(f"Password for user '{email}' has been reset to '{default_password}'")

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Reset user password")
    parser.add_argument("email", help="Email address of the user")
    args = parser.parse_args()

    try:
        reset_password(args.email)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
