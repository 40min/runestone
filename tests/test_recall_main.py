from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest


class TestRecallMain:
    """Test cases for recall_main functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_token = "test_bot_token"
        self.test_offset_file = "test_offset.txt"

    @patch("recall_main.signal.signal")
    @patch("recall_main.settings")
    @patch("recall_main.setup_logging")
    @patch("recall_main.setup_database", new_callable=AsyncMock)
    @patch("recall_main.TelegramUpdateOffsetStore")
    @patch("recall_main.create_scheduler")
    @patch("recall_main.AsyncIOScheduler")
    @pytest.mark.asyncio
    async def test_main_success(
        self,
        mock_async_scheduler,
        mock_create_scheduler,
        mock_offset_store,
        mock_setup_database,
        mock_setup_logging,
        mock_settings,
        mock_signal,
    ):
        """Test successful main execution."""
        mock_settings.telegram_bot_token = self.test_token
        mock_settings.verbose = False

        mock_scheduler = Mock()
        mock_scheduler.get_jobs.return_value = []
        mock_create_scheduler.return_value = mock_scheduler

        with patch("asyncio.Event.wait", new_callable=AsyncMock):
            from recall_main import main

            await main(self.test_offset_file)

        mock_setup_logging.assert_called_once_with(level="INFO")
        mock_setup_database.assert_awaited_once()
        mock_offset_store.assert_called_once_with(self.test_offset_file)
        mock_create_scheduler.assert_called_once_with(mock_offset_store.return_value)
        mock_scheduler.start.assert_called_once()
        mock_scheduler.shutdown.assert_called_once_with(wait=True)
        assert mock_signal.call_count == 2

    @patch("recall_main.signal.signal")
    @patch("recall_main.settings")
    @patch("recall_main.setup_logging")
    @patch("recall_main.setup_database", new_callable=AsyncMock)
    @patch("recall_main.TelegramUpdateOffsetStore")
    @patch("recall_main.create_scheduler")
    @patch("recall_main.AsyncIOScheduler")
    @pytest.mark.asyncio
    async def test_main_uses_settings_offset_file_path(
        self,
        mock_async_scheduler,
        mock_create_scheduler,
        mock_offset_store,
        mock_setup_database,
        mock_setup_logging,
        mock_settings,
        mock_signal,
    ):
        """Test main uses settings.telegram_offset_file_path when no path provided."""
        mock_settings.telegram_bot_token = self.test_token
        mock_settings.verbose = False
        mock_settings.telegram_offset_file_path = "custom/offset.txt"

        mock_scheduler = Mock()
        mock_scheduler.get_jobs.return_value = []
        mock_create_scheduler.return_value = mock_scheduler

        with patch("asyncio.Event.wait", new_callable=AsyncMock):
            from recall_main import main

            await main()

        mock_offset_store.assert_called_once_with("custom/offset.txt")
        mock_scheduler.start.assert_called_once()
        mock_scheduler.shutdown.assert_called_once_with(wait=True)
        assert mock_signal.call_count == 2

    @patch("recall_main.settings")
    @pytest.mark.asyncio
    async def test_main_missing_token(self, mock_settings):
        """Test main with missing telegram bot token."""
        mock_settings.telegram_bot_token = None

        from recall_main import main

        with pytest.raises(SystemExit, match="1"):
            await main()

    @patch("recall_main.settings")
    @patch("recall_main.setup_logging")
    @patch("recall_main.setup_database", new_callable=AsyncMock)
    @patch("recall_main.TelegramUpdateOffsetStore")
    @patch("recall_main.create_scheduler")
    @patch("recall_main.AsyncIOScheduler")
    @pytest.mark.asyncio
    async def test_main_unexpected_error(
        self,
        mock_async_scheduler,
        mock_create_scheduler,
        mock_offset_store,
        mock_setup_database,
        mock_setup_logging,
        mock_settings,
    ):
        """Test main with unexpected error."""
        mock_settings.telegram_bot_token = self.test_token
        mock_settings.verbose = False
        mock_setup_database.side_effect = RuntimeError("Database error")

        from recall_main import main

        with pytest.raises(SystemExit, match="1"):
            await main()

        mock_offset_store.assert_not_called()
        mock_create_scheduler.assert_not_called()

    @patch("recall_main.AsyncIOScheduler")
    @patch("recall_main.settings")
    def test_create_scheduler(self, mock_settings, mock_async_scheduler):
        """Test scheduler creation and job configuration."""
        from recall_main import create_scheduler
        from runestone.state.telegram_update_offset_store import TelegramUpdateOffsetStore

        mock_offset_store = TelegramUpdateOffsetStore("state/offset.txt")
        mock_scheduler = Mock()
        mock_async_scheduler.return_value = mock_scheduler
        mock_settings.recall_interval_minutes = 30

        scheduler = create_scheduler(mock_offset_store)

        mock_async_scheduler.assert_called_once()
        assert scheduler == mock_scheduler
        assert mock_scheduler.add_job.call_count == 2

        poll_call = mock_scheduler.add_job.call_args_list[0]
        assert poll_call[1]["id"] == "poll_commands"
        assert poll_call[1]["name"] == "Poll Telegram Commands"
        assert poll_call[1]["max_instances"] == 1
        assert poll_call[1]["replace_existing"] is True
        assert poll_call[1]["args"] == [mock_offset_store]
        trigger = poll_call[1]["trigger"]
        assert hasattr(trigger, "interval")
        assert trigger.interval.total_seconds() == 5

        daily_call = mock_scheduler.add_job.call_args_list[1]
        assert daily_call[1]["id"] == "send_recall_words"
        assert daily_call[1]["name"] == "Send Recall Vocabulary Words"
        assert daily_call[1]["max_instances"] == 1
        assert daily_call[1]["replace_existing"] is True
        assert "args" not in daily_call[1]
        trigger = daily_call[1]["trigger"]
        assert hasattr(trigger, "interval")

    @patch("runestone.db.database.run_migrations")
    @patch("runestone.db.database.engine")
    @pytest.mark.asyncio
    async def test_setup_database_missing_tables(self, mock_engine, mock_run_migrations):
        """Test database setup when tables are missing - should run migrations."""
        from runestone.db.database import setup_database

        mock_conn = AsyncMock()
        mock_engine.connect.return_value.__aenter__.return_value = mock_conn
        mock_conn.run_sync.side_effect = [["users", "vocabulary"], []]

        await setup_database()

        mock_run_migrations.assert_called_once()
        mock_engine.connect.assert_called_once()
        assert mock_conn.run_sync.call_count == 2

    @patch("runestone.db.database.engine")
    @pytest.mark.asyncio
    async def test_setup_database(self, mock_engine):
        """Test database setup when all tables exist."""
        from runestone.db.database import setup_database

        mock_conn = AsyncMock()
        mock_engine.connect.return_value.__aenter__.return_value = mock_conn
        mock_conn.run_sync.return_value = []

        await setup_database()

        mock_engine.connect.assert_called_once()
        mock_conn.run_sync.assert_called_once()

    @patch("recall_main.SessionLocal")
    @patch("recall_main._create_recall_service")
    @patch("recall_main.TelegramCommandService")
    @pytest.mark.asyncio
    async def test_process_updates_job(
        self,
        mock_telegram_service,
        mock_create_recall_service,
        mock_session_local,
    ):
        """Test process_updates_job wrapper function."""
        from recall_main import process_updates_job

        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        mock_offset_store = Mock()

        mock_telegram_instance = AsyncMock()
        mock_telegram_service.return_value = mock_telegram_instance

        await process_updates_job(mock_offset_store)

        mock_session_local.assert_called_once()
        mock_create_recall_service.assert_called_once_with(mock_db)
        mock_telegram_service.assert_called_once_with(mock_offset_store, mock_create_recall_service.return_value)
        mock_telegram_instance.process_updates.assert_awaited_once()

    @patch("recall_main.SessionLocal")
    @patch("recall_main._create_recall_service")
    @patch("recall_main.TelegramRecallDeliveryService")
    @pytest.mark.asyncio
    async def test_send_recall_word_job(
        self,
        mock_telegram_recall_delivery_service,
        mock_create_recall_service,
        mock_session_local,
    ):
        """Test send_recall_word_job wrapper function."""
        from recall_main import send_recall_word_job

        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        mock_recall_instance = AsyncMock()
        mock_telegram_recall_delivery_service.return_value = mock_recall_instance

        await send_recall_word_job()

        mock_session_local.assert_called_once()
        mock_create_recall_service.assert_called_once_with(mock_db)
        mock_telegram_recall_delivery_service.assert_called_once_with(mock_create_recall_service.return_value, ANY)
        mock_recall_instance.send_next_recall_word.assert_awaited_once()
