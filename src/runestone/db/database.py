"""
Database configuration and session management.

This module sets up SQLAlchemy engine, session factory, and base class
for database operations in the Runestone application.
"""

import logging
import os

from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from alembic import command
from alembic.config import Config
from runestone.config import settings

# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

logger = logging.getLogger(__name__)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """Run Alembic migrations to upgrade database to latest version."""
    try:
        # Get the alembic.ini path
        alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "alembic.ini"))

        if not os.path.exists(alembic_ini_path):
            logger.warning(f"Alembic configuration not found at {alembic_ini_path}")
            logger.info("Falling back to creating tables with Base.metadata.create_all()")
            Base.metadata.create_all(bind=engine)
            return

        # Create Alembic config
        alembic_cfg = Config(alembic_ini_path)

        # Run migrations
        logger.info("Running database migrations...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully.")

    except Exception:
        logger.error("Failed to run migrations", exc_info=True)
        raise


def setup_database() -> None:
    """Check if database and tables exist, raise exception if not."""

    # For SQLite, check if database file exists
    if "sqlite" in str(engine.url):
        db_path = engine.url.database
        if db_path and not os.path.exists(db_path):
            logger.error(f"Database file '{db_path}' does not exist")
            raise FileNotFoundError(f"Database file '{db_path}' does not exist")

    # Check if required tables exist
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Get expected table names from Base metadata
    expected_tables = Base.metadata.tables.keys()

    missing_tables = [table for table in expected_tables if table not in existing_tables]

    if missing_tables:
        logger.error(f"Missing database tables: {', '.join(missing_tables)}")
        raise ValueError(f"Missing database tables: {', '.join(missing_tables)}")

    logger.info("Database and tables verified successfully.")
