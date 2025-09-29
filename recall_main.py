#!/usr/bin/env python3
"""
Standalone Telegram bot worker application for Runestone.

This application runs scheduled tasks for the Telegram bot:
- Polls for incoming commands via TelegramCommandService
- Sends daily vocabulary words via RuneRecallService

Uses APScheduler for task scheduling and proper configuration management.
"""

import logging
import signal
import sys
from typing import Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from runestone.config import settings
from runestone.core.logging_config import setup_logging
from runestone.db.database import setup_database, SessionLocal
from runestone.db.repository import VocabularyRepository
from runestone.services.rune_recall_service import RuneRecallService
from runestone.state.state_manager import StateManager
from runestone.services.telegram_command_service import TelegramCommandService


def create_scheduler(
    telegram_service: TelegramCommandService,
    recall_service: RuneRecallService
) -> BlockingScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = BlockingScheduler()

    # Poll for Telegram commands every 5 seconds
    scheduler.add_job(
        telegram_service.process_updates,
        trigger=IntervalTrigger(seconds=5),
        id="poll_commands",
        name="Poll Telegram Commands",
        max_instances=1,
        replace_existing=True
    )

    # Send recall words periodically during the day
    scheduler.add_job(
        recall_service.send_next_recall_word,
        trigger=IntervalTrigger(minutes=settings.recall_interval_minutes),
        id="send_recall_words",
        name="Send Recall Vocabulary Words",
        max_instances=1,
        replace_existing=True
    )

    return scheduler


def main(state_file_path: Optional[str] = None) -> None:
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
        setup_database()

        # Initialize services
        state_manager = StateManager(state_file_path or "state/state.json")
        
        # Create database session and repository
        db = SessionLocal()
        vocabulary_repository = VocabularyRepository(db)
        
        recall_service = RuneRecallService(vocabulary_repository, state_manager)
        telegram_service = TelegramCommandService(state_manager, recall_service)

        # Create and configure scheduler
        scheduler = create_scheduler(telegram_service, recall_service)

        # Setup signal handlers for graceful shutdown
        def shutdown_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down scheduler...")
            scheduler.shutdown(wait=True)
            db.close()  # Close database connection
            logger.info("Scheduler shutdown complete")
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

        logger.info("Scheduler configured with jobs:")
        for job in scheduler.get_jobs():
            logger.info(f"  - {job.name}: {job.trigger}")

        logger.info("Starting scheduler...")
        try:
            scheduler.start()
        finally:
            db.close()  # Ensure database connection is always closed

    except Exception as e:
        logger.error(f"Failed to start worker: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()