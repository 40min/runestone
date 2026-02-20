"""
Main FastAPI application for Runestone.

This module initializes the FastAPI application, configures middleware,
and includes API routers for the web interface.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from runestone.agent.service import AgentService
from runestone.api.audio_ws import router as audio_ws_router
from runestone.api.auth_endpoints import router as auth_router
from runestone.api.chat_endpoints import router as chat_router
from runestone.api.endpoints import grammar_router
from runestone.api.endpoints import router as api_router
from runestone.api.memory_endpoints import router as memory_router
from runestone.api.user_endpoints import router as user_router
from runestone.config import settings
from runestone.core.clients.factory import create_llm_client
from runestone.core.logging_config import setup_logging
from runestone.db.database import setup_database
from runestone.rag.index import GrammarIndex
from runestone.services.grammar_service import GrammarService
from runestone.services.tts_service import TTSService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    # Startup
    setup_logging(verbose=settings.verbose)
    # Verify database setup
    setup_database()

    # Initialize expensive services once
    app.state.llm_client = create_llm_client(settings=settings)
    app.state.ocr_llm_client = (
        create_llm_client(
            settings=settings,
            provider=settings.ocr_llm_provider,
            model_name=settings.ocr_llm_model_name,
        )
        if settings.ocr_llm_provider
        else app.state.llm_client
    )
    app.state.grammar_service = GrammarService(settings.cheatsheets_dir)
    app.state.grammar_index = GrammarIndex(settings.cheatsheets_dir, settings.app_base_url)
    app.state.agent_service = AgentService(
        settings,
        grammar_index=app.state.grammar_index,
        grammar_service=app.state.grammar_service,
    )
    app.state.tts_service = TTSService(settings)
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

    # Include grammar router
    app.include_router(
        grammar_router,
        prefix="/api",
        tags=["grammar"],
    )

    # Include auth router
    app.include_router(
        auth_router,
        prefix="/api/auth",
        tags=["auth"],
    )

    # Include user router
    app.include_router(
        user_router,
        prefix="/api",
        tags=["users"],
    )

    # Include chat router
    app.include_router(
        chat_router,
        prefix="/api/chat",
        tags=["chat"],
    )

    # Include audio WebSocket router
    app.include_router(
        audio_ws_router,
        prefix="/api",
        tags=["audio"],
    )

    # Include memory router
    app.include_router(
        memory_router,
        prefix="/api",
        tags=["memory"],
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
