"""
Tests for the recall_main module.
"""

from unittest.mock import Mock, patch

import pytest


class TestRecallMain:
    """Test cases for recall_main functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_token = "test_bot_token"
        self.test_state_file = "test_state.json"

    @patch("recall_main.settings")
    @patch("recall_main.setup_logging")
    @patch("recall_main.setup_database")
    @patch("recall_main.StateManager")
    @patch("recall_main.create_scheduler")
    @patch("recall_main.BlockingScheduler")
    def test_main_success(
        self,
        mock_blocking_scheduler,
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
        mock_scheduler.get_jobs.return_value = []  # Mock get_jobs to return empty list
        mock_blocking_scheduler.return_value = mock_scheduler
        mock_create_scheduler.return_value = mock_scheduler

        # Mock the scheduler start method to avoid infinite loop
        mock_scheduler.start.side_effect = KeyboardInterrupt()

        # Import and call main
        from recall_main import main

        # Should raise KeyboardInterrupt from scheduler.start()
        with pytest.raises(KeyboardInterrupt):
            main(self.test_state_file)

        # Verify calls
        mock_setup_logging.assert_called_once_with(level="INFO")
        mock_setup_database.assert_called_once()
        mock_state_manager.assert_called_once_with(self.test_state_file)
        mock_create_scheduler.assert_called_once()
        mock_scheduler.start.assert_called_once()

    @patch("recall_main.settings")
    @patch("recall_main.setup_logging")
    @patch("recall_main.setup_database")
    @patch("recall_main.StateManager")
    @patch("recall_main.create_scheduler")
    @patch("recall_main.BlockingScheduler")
    def test_main_uses_settings_state_file_path(
        self,
        mock_blocking_scheduler,
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
        mock_blocking_scheduler.return_value = mock_scheduler
        mock_create_scheduler.return_value = mock_scheduler

        # Mock the scheduler start method to avoid infinite loop
        mock_scheduler.start.side_effect = KeyboardInterrupt()

        # Import and call main without state_file_path parameter
        from recall_main import main

        # Should raise KeyboardInterrupt from scheduler.start()
        with pytest.raises(KeyboardInterrupt):
            main()  # No state_file_path parameter

        # Verify StateManager was called with settings.state_file_path
        mock_state_manager.assert_called_once_with("custom/state.json")

    @patch("recall_main.settings")
    def test_main_missing_token(self, mock_settings):
        """Test main with missing telegram bot token."""
        mock_settings.telegram_bot_token = None

        from recall_main import main

        with pytest.raises(SystemExit, match="1"):
            main()

    @patch("recall_main.settings")
    @patch("recall_main.setup_logging")
    @patch("recall_main.setup_database")
    @patch("recall_main.StateManager")
    @patch("recall_main.create_scheduler")
    @patch("recall_main.BlockingScheduler")
    def test_main_unexpected_error(
        self,
        mock_blocking_scheduler,
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
            main()

    @patch("recall_main.BlockingScheduler")
    @patch("recall_main.settings")
    def test_create_scheduler(self, mock_settings, mock_blocking_scheduler):
        """Test scheduler creation and job configuration."""
        from recall_main import create_scheduler

        # Create mock state manager
        mock_state_manager = Mock()
        mock_scheduler = Mock()
        mock_blocking_scheduler.return_value = mock_scheduler
        mock_settings.recall_interval_minutes = 30

        # Create scheduler
        scheduler = create_scheduler(mock_state_manager)

        # Verify scheduler creation
        mock_blocking_scheduler.assert_called_once()
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

    @patch("runestone.db.database.inspect")
    @patch("runestone.db.database.engine")
    def test_setup_database(self, mock_engine, mock_inspect):
        """Test database setup."""
        from recall_main import setup_database

        # Mock inspector
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ["vocabulary"]
        mock_inspect.return_value = mock_inspector

        # Mock Base metadata
        with patch("runestone.db.database.Base") as mock_base:
            mock_base.metadata.tables.keys.return_value = ["vocabulary"]

            setup_database()

        # Verify inspect was called
        mock_inspect.assert_called_once_with(mock_engine)

    @patch("recall_main.signal")
    @patch("recall_main.settings")
    @patch("recall_main.setup_logging")
    @patch("recall_main.setup_database")
    @patch("recall_main.StateManager")
    @patch("recall_main.create_scheduler")
    @patch("recall_main.BlockingScheduler")
    def test_signal_handlers(
        self,
        mock_blocking_scheduler,
        mock_create_scheduler,
        mock_state_manager,
        mock_setup_database,
        mock_setup_logging,
        mock_settings,
        mock_signal,
    ):
        """Test signal handler setup."""
        mock_settings.telegram_bot_token = self.test_token
        mock_settings.verbose = False

        mock_scheduler = Mock()
        mock_scheduler.get_jobs.return_value = []  # Mock get_jobs to return empty list
        mock_blocking_scheduler.return_value = mock_scheduler
        mock_create_scheduler.return_value = mock_scheduler

        # Mock the scheduler start method to avoid infinite loop
        mock_scheduler.start.side_effect = KeyboardInterrupt()

        from recall_main import main

        with pytest.raises(KeyboardInterrupt):
            main()

        # Verify signal handlers were set
        assert mock_signal.signal.call_count == 2
        # Check that signal.signal was called with the mocked signal constants
        calls = mock_signal.signal.call_args_list
        assert len(calls) == 2
        # The first argument should be the signal constant (mocked), second should be the handler function
        assert calls[0][0][0] is not None  # First signal constant
        assert calls[1][0][0] is not None  # Second signal constant
        assert callable(calls[0][0][1])  # Handler function
        assert callable(calls[1][0][1])  # Handler function

    @patch("recall_main.SessionLocal")
    @patch("recall_main.VocabularyRepository")
    @patch("recall_main.RuneRecallService")
    @patch("recall_main.TelegramCommandService")
    def test_process_updates_job(
        self,
        mock_telegram_service,
        mock_recall_service,
        mock_vocabulary_repository,
        mock_session_local,
    ):
        """Test process_updates_job wrapper function."""
        from recall_main import process_updates_job

        # Setup mocks
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        mock_state_manager = Mock()

        # Call the wrapper function
        process_updates_job(mock_state_manager)

        # Verify session was created and closed
        mock_session_local.assert_called_once()
        mock_db.close.assert_called_once()

        # Verify services were created with fresh session
        mock_vocabulary_repository.assert_called_once_with(mock_db)
        mock_recall_service.assert_called_once()
        mock_telegram_service.assert_called_once()

        # Verify telegram service process_updates was called
        mock_telegram_service.return_value.process_updates.assert_called_once()

    @patch("recall_main.SessionLocal")
    @patch("recall_main.VocabularyRepository")
    @patch("recall_main.RuneRecallService")
    def test_send_recall_word_job(
        self,
        mock_recall_service,
        mock_vocabulary_repository,
        mock_session_local,
    ):
        """Test send_recall_word_job wrapper function."""
        from recall_main import send_recall_word_job

        # Setup mocks
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        mock_state_manager = Mock()

        # Call the wrapper function
        send_recall_word_job(mock_state_manager)

        # Verify session was created and closed
        mock_session_local.assert_called_once()
        mock_db.close.assert_called_once()

        # Verify services were created with fresh session
        mock_vocabulary_repository.assert_called_once_with(mock_db)
        mock_recall_service.assert_called_once()

        # Verify recall service send_next_recall_word was called
        mock_recall_service.return_value.send_next_recall_word.assert_called_once()
