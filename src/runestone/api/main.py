"""
Main FastAPI application for Runestone.

This module initializes the FastAPI application, configures middleware,
and includes API routers for the web interface.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from runestone.api.endpoints import router as api_router
from runestone.config import settings
from runestone.core.logging_config import setup_logging
from runestone.db.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    # Startup
    setup_logging()
    # Create database tables
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="Runestone API",
        description="REST API for analyzing Swedish textbook pages using OCR and LLM",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(
        api_router,
        prefix="/api",
        tags=["processing"],
    )

    return app


# Create the FastAPI application instance
app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "runestone.api.main:app",
        host="0.0.0.0",
        port=8010,
        reload=True,
    )
