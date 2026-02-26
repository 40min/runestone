"""
Database configuration and session management.

This module sets up SQLAlchemy engine, session factory, and base class
for database operations in the Runestone application.
"""

import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from alembic import command
from alembic.config import Config
from runestone.config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy async engine with connection pooling
# Built-in pool for asyncpg
engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create async_sessionmaker
SessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False
)

# Create Base class
Base = declarative_base()


async def get_db():
    """Dependency to get database session."""
    async with SessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


def run_migrations() -> None:
    """Run Alembic migrations to upgrade database to latest version."""
    try:
        # Get the alembic.ini path
        alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "alembic.ini"))

        if not os.path.exists(alembic_ini_path):
            logger.warning(f"Alembic configuration not found at {alembic_ini_path}")
            logger.info("Falling back to creating tables with Base.metadata.create_all()")
            # metadata.create_all is blocking and requires a sync engine
            sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
            sync_engine = create_engine(sync_url)
            Base.metadata.create_all(bind=sync_engine)
            sync_engine.dispose()
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


async def setup_database() -> None:
    """Check if required tables exist, raise exception if not."""
    from sqlalchemy import inspect

    def check_tables(connection):
        inspector = inspect(connection)
        existing_tables = inspector.get_table_names()
        expected_tables = Base.metadata.tables.keys()
        return [table for table in expected_tables if table not in existing_tables]

    try:
        async with engine.connect() as conn:
            missing_tables = await conn.run_sync(check_tables)

            if missing_tables:
                logger.error(f"Missing database tables: {', '.join(missing_tables)}")
                raise ValueError(f"Missing database tables: {', '.join(missing_tables)}")

        logger.info("Database and tables verified successfully.")
    except Exception as e:
        logger.error(f"Database setup check failed: {e}")
        raise
