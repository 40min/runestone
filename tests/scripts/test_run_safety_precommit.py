import subprocess
from unittest.mock import MagicMock

from scripts.run_safety_precommit import main


def test_optional_skip_when_api_key_missing(monkeypatch, capsys):
    monkeypatch.delenv("SAFETY_API_KEY", raising=False)
    monkeypatch.delenv("SAFETY_REQUIRED", raising=False)

    assert main() == 0

    captured = capsys.readouterr()
    assert "Skipping Safety scan" in captured.err
    assert "SAFETY_API_KEY" in captured.err


def test_required_missing_api_key_fails_closed(monkeypatch, capsys):
    monkeypatch.delenv("SAFETY_API_KEY", raising=False)
    monkeypatch.setenv("SAFETY_REQUIRED", "1")

    assert main() == 1

    captured = capsys.readouterr()
    assert "required" in captured.err.lower()
    assert "SAFETY_API_KEY" in captured.err


def test_authenticated_run_invokes_safety_and_propagates_exit_code(monkeypatch):
    monkeypatch.setenv("SAFETY_API_KEY", "test-key")
    monkeypatch.setenv("SAFETY_REQUIRED", "1")
    monkeypatch.setattr("shutil.which", lambda _name: "/fake/safety")

    mock_run = MagicMock(return_value=subprocess.CompletedProcess(args=[], returncode=7))
    monkeypatch.setattr("subprocess.run", mock_run)

    assert main() == 7

    mock_run.assert_called_once()
    command = mock_run.call_args[0][0]
    assert command[0] == "/fake/safety"
    assert "scan" in command
    assert "--target" in command
    assert "." in command
    assert "--output" not in command
    assert "bare" not in command
    assert mock_run.call_args.kwargs["cwd"].name.startswith("runestone-safety-")
    assert not mock_run.call_args.kwargs["cwd"].exists()
