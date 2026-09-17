"""
Database configuration and session management.

This module sets up SQLAlchemy engine, session factory, and base class
for database operations in the Runestone application.
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from alembic import command
from alembic.config import Config
from runestone.config import settings
from runestone.core.error_tracking import capture_sanitized_exception, duration_bucket

logger = logging.getLogger(__name__)


# Each backend process owns a PostgreSQL pool. Small NAS deployments need lower
# defaults than a workstation, while bursts from parallel agent calls can still
# use max_overflow headroom.
db_url_params = {
    "pool_size": settings.database_pool_size,
    "max_overflow": settings.database_max_overflow,
    "pool_timeout": settings.database_pool_timeout,
    "pool_pre_ping": settings.database_pool_pre_ping,
    "pool_recycle": settings.database_pool_recycle_seconds,
}

logger.info("DB connection params: %s", db_url_params)

engine = create_async_engine(settings.database_url, **db_url_params)

# Create async_sessionmaker
SessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False
)

# Create Base class
Base = declarative_base()


def record_database_boundary_failure(
    operation: str,
    exception: BaseException,
    started_at: float,
) -> None:
    """Emit one bounded failure marker and capture without affecting the boundary.

    The marker carries only the operation label, outcome, and duration bucket;
    exception identity and context come from the companion captured event.
    """
    try:
        logger.error(
            "database boundary failure operation=%s",
            operation,
            extra={
                "runestone_telemetry": {
                    "operation": operation,
                    "outcome": "failed",
                    "duration_bucket": duration_bucket(started_at),
                }
            },
        )
    except Exception:
        # Diagnostics must never change a startup or transaction outcome.
        pass
    try:
        capture_sanitized_exception(exception)
    except Exception:
        # Logging and event capture fail independently.
        pass


async def get_db():
    """Dependency to get database session."""
    async with SessionLocal() as db:
        yield db


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
        yield session


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
    if not settings.startup_db_check:
        logger.info("Skipping startup database verification because STARTUP_DB_CHECK is disabled.")
        return

    started_at = time.monotonic()

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
    except Exception as exc:
        record_database_boundary_failure("database_startup_check", exc, started_at)
        # The marker log above never carries exception text; keep the local
        # traceback here so failures are diagnosable without a configured DSN.
        logger.error("Database setup check failed", exc_info=True)
        raise
