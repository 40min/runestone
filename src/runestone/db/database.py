"""
Database configuration and session management.

This module sets up SQLAlchemy engine, session factory, and base class
for database operations in the Runestone application.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import create_engine, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from alembic import command
from alembic.config import Config
from runestone.config import settings

logger = logging.getLogger(__name__)


db_url_params = {}
settings_url = make_url(settings.database_url)
# QueuePool kwargs are valid for PostgreSQL (asyncpg, psycopg) drivers
if settings_url.get_dialect().name == "postgresql":
    # Create SQLAlchemy async engine with connection pooling for parallel tool execution
    # Increased pool_size and max_overflow to handle concurrent LangGraph tool calls
    db_url_params = {
        "pool_size": 20,
        "max_overflow": 10,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }

logger.error("DB connection params: %s", db_url_params)

engine = create_async_engine(settings.database_url, **db_url_params)

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


@asynccontextmanager
async def provide_db_session() -> AsyncIterator[AsyncSession]:
    """
    Context manager for creating a fresh database session.

    This is intended for use in non-FastAPI contexts (e.g., LangGraph agent tools)
    where each tool call needs its own isolated session for concurrent execution.

    Usage:
        async with provide_db_session() as session:
            repo = SomeRepository(session)
            result = await repo.some_method()
    """
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


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
    """Check if required tables exist, create them if missing."""
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
                logger.warning(
                    f"Missing database tables: {', '.join(missing_tables)}. Running migrations to create tables..."
                )
                # Import here to avoid circular imports
                from runestone.db.database import run_migrations

                run_migrations()

                # Verify tables were created
                missing_tables_after = await conn.run_sync(check_tables)
                if missing_tables_after:
                    logger.error(f"Missing database tables after migrations: {', '.join(missing_tables_after)}")
                    raise ValueError(f"Missing database tables after migrations: {', '.join(missing_tables_after)}")

        logger.info("Database and tables verified successfully.")
    except Exception as e:
        logger.error(f"Database setup check failed: {e}")
        raise
