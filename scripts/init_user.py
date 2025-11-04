#!/usr/bin/env python3
"""
User initialization script for Runestone.

This script creates the initial user (id=1) and updates all existing vocabulary
rows to reference this user. This is part of the transition to multi-user support.

WARNING: This script should only be run once during the migration to multi-user support.
After running, change the default credentials in the script or environment variables.

Usage:
    python scripts/init_user.py

Requirements:
    - Database must already exist with vocabulary table
    - No users table should exist yet (script creates it)
    - Run this script BEFORE applying the Alembic migration that adds the foreign key constraint
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from runestone.config import settings  # noqa: E402
from runestone.db.database import Base  # noqa: E402
from runestone.db.models import User  # noqa: E402


def create_user_table(engine):
    """Create the users table if it doesn't exist."""
    print("Creating users table...")
    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    print("✅ Users table created successfully")


def create_initial_user(session):
    """Create the initial user with id=1."""
    print("Creating initial user...")

    # Check if user already exists
    existing_user = session.query(User).filter_by(id=1).first()
    if existing_user:
        print("⚠️  User with id=1 already exists, skipping creation")
        return existing_user

    # Create the initial user
    initial_user = User(
        id=1,
        email="user1@example.com",
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeE8e0zqjzKj1Q9K",  # 'test123test'
        name="40min",
        surname=None,
        timezone="UTC",
        pages_recognised_count=0,
    )

    session.add(initial_user)
    session.commit()
    print("✅ Initial user created successfully")
    return initial_user


def update_vocabulary_user_ids(session):
    """Update all existing vocabulary rows to set user_id = 1."""
    print("Updating vocabulary user_ids...")

    # Update all vocabulary rows that don't have user_id set
    result = session.execute(text("UPDATE vocabulary SET user_id = 1 WHERE user_id IS NULL OR user_id = 0"))
    updated_count = result.rowcount
    session.commit()

    print(f"✅ Updated {updated_count} vocabulary rows to set user_id = 1")


def add_foreign_key_constraint(engine):
    """Add foreign key constraint to vocabulary.user_id."""
    print("Adding foreign key constraint...")

    # This would typically be done by Alembic migration, but we can add it here if needed
    # For now, we'll let Alembic handle this in the migration script
    print("⚠️  Foreign key constraint should be added via Alembic migration")
    print("   Run 'alembic revision --autogenerate -m \"Add user foreign key\"' after this script")


def main():
    """Main script execution."""
    print("🔧 Initializing users for Runestone multi-user support...")
    print(f"📊 Using database: {settings.database_url}")
    print()

    # Create engine
    engine = create_engine(settings.database_url)

    try:
        # Create session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()

        # Execute initialization steps
        # create_user_table(engine)
        create_initial_user(session)
        update_vocabulary_user_ids(session)
        add_foreign_key_constraint(engine)

        print()
        print("✅ User initialization completed successfully!")
        print()
        print("🔐 SECURITY NOTICE:")
        print("   - Default user credentials: user1@example.com / test123test")
        print("   - Change these credentials immediately after first login")
        print("   - Update the password hash in this script if needed")
        print()
        print("📋 NEXT STEPS:")
        print("   1. Run Alembic migration to add foreign key constraints")
        print("   2. Test the application with the new user system")
        print("   3. Remove or secure this initialization script")

    except Exception as e:
        print(f"❌ Error during initialization: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
