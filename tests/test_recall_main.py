from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestRecallMain:
    """Test cases for recall_main functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_token = "test_bot_token"
        self.test_state_file = "test_state.json"

    @patch("recall_main.settings")
    @patch("recall_main.setup_logging")
    @patch("recall_main.setup_database", new_callable=AsyncMock)
    @patch("recall_main.StateManager")
    @patch("recall_main.create_scheduler")
    @patch("recall_main.AsyncIOScheduler")
    @pytest.mark.asyncio
    async def test_main_success(
        self,
        mock_async_scheduler,
        mock_create_scheduler,
        mock_state_manager,
        mock_setup_database,
        mock_setup_logging,
        mock_settings,
    ):
        """Test successful main execution."""
        # Setup mocks
        mock_settings.telegram_bot_token = self.test_token
        mock_settings.verbose = False

        mock_scheduler = Mock()
        mock_scheduler.get_jobs.return_value = []
        mock_create_scheduler.return_value = mock_scheduler

        # Mock the shutdown_event wait to exit immediately
        with patch("asyncio.Event.wait", new_callable=AsyncMock):
            from recall_main import main

            await main(self.test_state_file)

        # Verify calls
        mock_setup_logging.assert_called_once_with(level="INFO")
        mock_setup_database.assert_awaited_once()
        mock_state_manager.assert_called_once_with(self.test_state_file)
        mock_create_scheduler.assert_called_once()
        mock_scheduler.start.assert_called_once()

    @patch("recall_main.settings")
    @patch("recall_main.setup_logging")
    @patch("recall_main.setup_database", new_callable=AsyncMock)
    @patch("recall_main.StateManager")
    @patch("recall_main.create_scheduler")
    @patch("recall_main.AsyncIOScheduler")
    @pytest.mark.asyncio
    async def test_main_uses_settings_state_file_path(
        self,
        mock_async_scheduler,
        mock_create_scheduler,
        mock_state_manager,
        mock_setup_database,
        mock_setup_logging,
        mock_settings,
    ):
        """Test main uses settings.state_file_path when no path provided."""
        # Setup mocks
        mock_settings.telegram_bot_token = self.test_token
        mock_settings.verbose = False
        mock_settings.state_file_path = "custom/state.json"

        mock_scheduler = Mock()
        mock_scheduler.get_jobs.return_value = []
        mock_create_scheduler.return_value = mock_scheduler

        # Mock the shutdown_event wait to exit immediately
        with patch("asyncio.Event.wait", new_callable=AsyncMock):
            from recall_main import main

            await main()  # No state_file_path parameter

        # Verify StateManager was called with settings.state_file_path
        mock_state_manager.assert_called_once_with("custom/state.json")

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
    @patch("recall_main.StateManager")
    @patch("recall_main.create_scheduler")
    @patch("recall_main.AsyncIOScheduler")
    @pytest.mark.asyncio
    async def test_main_unexpected_error(
        self,
        mock_async_scheduler,
        mock_create_scheduler,
        mock_state_manager,
        mock_setup_database,
        mock_setup_logging,
        mock_settings,
    ):
        """Test main with unexpected error."""
        mock_settings.telegram_bot_token = self.test_token
        mock_settings.verbose = False

        # Make setup_database raise an exception
        mock_setup_database.side_effect = RuntimeError("Database error")

        from recall_main import main

        with pytest.raises(SystemExit, match="1"):
            await main()

    @patch("recall_main.AsyncIOScheduler")
    @patch("recall_main.settings")
    def test_create_scheduler(self, mock_settings, mock_async_scheduler):
        """Test scheduler creation and job configuration."""
        from recall_main import create_scheduler

        # Create mock state manager
        mock_state_manager = Mock()
        mock_scheduler = Mock()
        mock_async_scheduler.return_value = mock_scheduler
        mock_settings.recall_interval_minutes = 30

        # Create scheduler
        scheduler = create_scheduler(mock_state_manager)

        # Verify scheduler creation
        mock_async_scheduler.assert_called_once()
        assert scheduler == mock_scheduler

        # Verify jobs were added
        assert mock_scheduler.add_job.call_count == 2

        # Check first job (poll commands)
        poll_call = mock_scheduler.add_job.call_args_list[0]
        assert poll_call[1]["id"] == "poll_commands"
        assert poll_call[1]["name"] == "Poll Telegram Commands"
        assert poll_call[1]["max_instances"] == 1
        assert poll_call[1]["replace_existing"] is True
        assert poll_call[1]["args"] == [mock_state_manager]
        # Verify trigger is IntervalTrigger with 5 seconds
        trigger = poll_call[1]["trigger"]
        assert hasattr(trigger, "interval")
        assert trigger.interval.total_seconds() == 5

        # Check second job (recall words)
        daily_call = mock_scheduler.add_job.call_args_list[1]
        assert daily_call[1]["id"] == "send_recall_words"
        assert daily_call[1]["name"] == "Send Recall Vocabulary Words"
        assert daily_call[1]["max_instances"] == 1
        assert daily_call[1]["replace_existing"] is True
        assert daily_call[1]["args"] == [mock_state_manager]
        # Verify trigger is IntervalTrigger
        trigger = daily_call[1]["trigger"]
        assert hasattr(trigger, "interval")

    @patch("runestone.db.database.engine")
    @pytest.mark.asyncio
    async def test_setup_database(self, mock_engine):
        """Test database setup."""
        from runestone.db.database import setup_database

        # Mocking run_sync is tricky, let's mock engine.connect() to return a mock context manager
        mock_conn = AsyncMock()
        mock_engine.connect.return_value.__aenter__.return_value = mock_conn
        mock_conn.run_sync.return_value = []

        await setup_database()

        # Verify connect was called
        mock_engine.connect.assert_called_once()
        mock_conn.run_sync.assert_called_once()

    @patch("recall_main.SessionLocal")
    @patch("recall_main.VocabularyRepository")
    @patch("recall_main.RuneRecallService")
    @patch("recall_main.TelegramCommandService")
    @pytest.mark.asyncio
    async def test_process_updates_job(
        self,
        mock_telegram_service,
        mock_recall_service,
        mock_vocabulary_repository,
        mock_session_local,
    ):
        """Test process_updates_job wrapper function."""
        from recall_main import process_updates_job

        # Setup mocks
        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        mock_state_manager = Mock()

        mock_telegram_instance = AsyncMock()
        mock_telegram_service.return_value = mock_telegram_instance

        # Call the wrapper function
        await process_updates_job(mock_state_manager)

        # Verify session was created
        mock_session_local.assert_called_once()

        # Verify services were created with fresh session
        mock_vocabulary_repository.assert_called_once_with(mock_db)
        mock_recall_service.assert_called_once()
        mock_telegram_service.assert_called_once()

        # Verify telegram service process_updates was awaited
        mock_telegram_instance.process_updates.assert_awaited_once()

    @patch("recall_main.SessionLocal")
    @patch("recall_main.VocabularyRepository")
    @patch("recall_main.RuneRecallService")
    @pytest.mark.asyncio
    async def test_send_recall_word_job(
        self,
        mock_recall_service,
        mock_vocabulary_repository,
        mock_session_local,
    ):
        """Test send_recall_word_job wrapper function."""
        from recall_main import send_recall_word_job

        # Setup mocks
        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        mock_state_manager = Mock()

        mock_recall_instance = AsyncMock()
        mock_recall_service.return_value = mock_recall_instance

        # Call the wrapper function
        await send_recall_word_job(mock_state_manager)

        # Verify session was created
        mock_session_local.assert_called_once()

        # Verify services were created with fresh session
        mock_vocabulary_repository.assert_called_once_with(mock_db)
        mock_recall_service.assert_called_once()

        # Verify recall service send_next_recall_word was awaited
        mock_recall_instance.send_next_recall_word.assert_awaited_once()
