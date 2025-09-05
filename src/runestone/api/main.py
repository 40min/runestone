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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    # Startup
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
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"],  # Frontend dev server
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
        port=8000,
        reload=True,
    )
