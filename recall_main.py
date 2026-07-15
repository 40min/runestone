#!/usr/bin/env python3
"""
Standalone Telegram bot worker application for Runestone.

This application runs scheduled tasks for the Telegram bot:
- Polls for incoming commands via TelegramCommandService
- Sends daily vocabulary words via TelegramRecallDeliveryService

Uses APScheduler for task scheduling and proper configuration management.
"""

import asyncio
import logging
import signal
import sys
from functools import lru_cache
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from runestone.config import settings
from runestone.core.logging_config import setup_logging
from runestone.core.service_llm import build_service_llm_model
from runestone.db.database import SessionLocal, setup_database
from runestone.db.recall_repository import RecallRepository
from runestone.db.user_repository import UserRepository
from runestone.db.vocabulary_repository import VocabularyRepository
from runestone.services.recall_service import RecallService
from runestone.services.telegram_command_service import TelegramCommandService
from runestone.services.telegram_recall_delivery_service import TelegramRecallDeliveryService
from runestone.services.user_service import UserService
from runestone.services.vocabulary_service import VocabularyService
from runestone.state.telegram_update_offset_store import TelegramUpdateOffsetStore


@lru_cache(maxsize=1)
def _get_service_llm_model():
    """Reuse the stateless service model across short-lived worker sessions."""
    return build_service_llm_model(settings)


def _create_recall_service(db) -> RecallService:
    """Assemble recall collaborators over one worker-scoped database session."""
    vocabulary_service = VocabularyService(VocabularyRepository(db), settings, _get_service_llm_model())
    user_service = UserService(UserRepository(db))
    return RecallService(RecallRepository(db), vocabulary_service, user_service, settings)


async def process_updates_job(offset_store: TelegramUpdateOffsetStore) -> None:
    """Wrapper function for processing Telegram updates with fresh session."""
    async with SessionLocal() as db:
        try:
            recall_service = _create_recall_service(db)
            telegram_service = TelegramCommandService(offset_store, recall_service)
            await telegram_service.process_updates()
        except Exception:
            logging.getLogger(__name__).exception("Error in process_updates_job")


async def send_recall_word_job() -> None:
    """Wrapper function for sending recall words with fresh session."""
    async with SessionLocal() as db:
        try:
            recall_service = _create_recall_service(db)
            telegram_recall_delivery_service = TelegramRecallDeliveryService(recall_service, settings)
            await telegram_recall_delivery_service.send_next_recall_word()
        except Exception:
            logging.getLogger(__name__).exception("Error in send_recall_word_job")


def create_scheduler(offset_store: TelegramUpdateOffsetStore) -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler()

    # Poll for Telegram commands every 5 seconds
    scheduler.add_job(
        process_updates_job,
        args=[offset_store],
        trigger=IntervalTrigger(seconds=5),
        id="poll_commands",
        name="Poll Telegram Commands",
        max_instances=1,
        replace_existing=True,
    )

    # Send recall words periodically during the day
    scheduler.add_job(
        send_recall_word_job,
        trigger=IntervalTrigger(minutes=settings.recall_interval_minutes),
        id="send_recall_words",
        name="Send Recall Vocabulary Words",
        max_instances=1,
        replace_existing=True,
    )

    return scheduler


async def main(offset_file_path: Optional[str] = None) -> None:
    """Main entry point for the recall worker application."""
    # Setup logging
    log_level = "DEBUG" if settings.verbose else "INFO"
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)

    logger.info("Starting Runestone Telegram Bot Worker")

    try:
        # Validate required configuration
        if not settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

        # Setup database
        logger.info("Setting up database...")
        await setup_database()

        offset_store = TelegramUpdateOffsetStore(offset_file_path or settings.telegram_offset_file_path)

        # Create and configure scheduler with wrapper functions
        scheduler = create_scheduler(offset_store)

        # Signal event for graceful shutdown
        shutdown_event = asyncio.Event()

        # Setup signal handlers for graceful shutdown
        def shutdown_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            shutdown_event.set()

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

        logger.info("Scheduler configured with jobs:")
        for job in scheduler.get_jobs():
            logger.info(f"  - {job.name}: {job.trigger}")

        logger.info("Starting scheduler...")
        scheduler.start()

        # Wait until shutdown signal is received
        await shutdown_event.wait()

        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=True)
        logger.info("Scheduler shutdown complete")

    except Exception as e:
        logger.error(f"Failed to start worker: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
