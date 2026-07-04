from __future__ import annotations

import subprocess

from scripts import check_frontend_lockfile_sync


def test_pinned_npm_version_reads_package_manager(tmp_path, monkeypatch) -> None:
    package_json = tmp_path / "package.json"
    package_json.write_text('{"packageManager": "npm@10.8.2"}', encoding="utf-8")
    monkeypatch.setattr(check_frontend_lockfile_sync, "PACKAGE_JSON", package_json)

    assert check_frontend_lockfile_sync.pinned_npm_version() == "10.8.2"


def test_npm_command_uses_matching_local_npm(monkeypatch) -> None:
    monkeypatch.setattr(
        check_frontend_lockfile_sync.shutil,
        "which",
        lambda command: "/usr/bin/npm" if command == "npm" else None,
    )
    monkeypatch.setattr(
        check_frontend_lockfile_sync.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="10.8.2\n"),
    )

    assert check_frontend_lockfile_sync.npm_command("10.8.2") == ["/usr/bin/npm"]


def test_npm_command_falls_back_to_pinned_npx(monkeypatch) -> None:
    monkeypatch.setattr(
        check_frontend_lockfile_sync.shutil,
        "which",
        lambda command: "/usr/bin/npx" if command == "npx" else None,
    )

    assert check_frontend_lockfile_sync.npm_command("10.8.2") == [
        "/usr/bin/npx",
        "--yes",
        "npm@10.8.2",
    ]


def test_npm_command_falls_back_when_local_npm_version_differs(monkeypatch) -> None:
    monkeypatch.setattr(
        check_frontend_lockfile_sync.shutil,
        "which",
        lambda command: f"/usr/bin/{command}" if command in {"npm", "npx"} else None,
    )
    monkeypatch.setattr(
        check_frontend_lockfile_sync.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="11.6.2\n"),
    )

    assert check_frontend_lockfile_sync.npm_command("10.8.2") == [
        "/usr/bin/npx",
        "--yes",
        "npm@10.8.2",
    ]


def test_check_updates_stale_lockfile_and_fails(tmp_path, monkeypatch, capsys) -> None:
    package_lock = tmp_path / "package-lock.json"
    package_lock.write_text("old", encoding="utf-8")
    monkeypatch.setattr(check_frontend_lockfile_sync, "FRONTEND_DIR", tmp_path)
    monkeypatch.setattr(check_frontend_lockfile_sync, "PACKAGE_LOCK", package_lock)
    monkeypatch.setattr(check_frontend_lockfile_sync, "pinned_npm_version", lambda: "10.8.2")
    monkeypatch.setattr(
        check_frontend_lockfile_sync.shutil,
        "which",
        lambda command: "/usr/bin/npx" if command == "npx" else None,
    )

    def run(command, *, cwd, check):
        assert command[:3] == ["/usr/bin/npx", "--yes", "npm@10.8.2"]
        assert cwd == tmp_path
        assert check is False
        package_lock.write_text("new", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(check_frontend_lockfile_sync.subprocess, "run", run)

    assert check_frontend_lockfile_sync.sync_lockfile(fail_on_change=True) == 1
    assert "commit it and retry" in capsys.readouterr().err


def test_explicit_sync_accepts_lockfile_change(tmp_path, monkeypatch) -> None:
    package_lock = tmp_path / "package-lock.json"
    package_lock.write_text("old", encoding="utf-8")
    monkeypatch.setattr(check_frontend_lockfile_sync, "FRONTEND_DIR", tmp_path)
    monkeypatch.setattr(check_frontend_lockfile_sync, "PACKAGE_LOCK", package_lock)
    monkeypatch.setattr(check_frontend_lockfile_sync, "pinned_npm_version", lambda: "10.8.2")
    monkeypatch.setattr(
        check_frontend_lockfile_sync.shutil,
        "which",
        lambda command: "/usr/bin/npx" if command == "npx" else None,
    )

    def run(command, *, cwd, check):
        package_lock.write_text("new", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(check_frontend_lockfile_sync.subprocess, "run", run)

    assert check_frontend_lockfile_sync.sync_lockfile(fail_on_change=False) == 0


def test_sync_fails_cleanly_when_npm_does_not_create_lockfile(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(check_frontend_lockfile_sync, "FRONTEND_DIR", tmp_path)
    monkeypatch.setattr(check_frontend_lockfile_sync, "PACKAGE_LOCK", tmp_path / "package-lock.json")
    monkeypatch.setattr(check_frontend_lockfile_sync, "pinned_npm_version", lambda: "10.8.2")
    monkeypatch.setattr(check_frontend_lockfile_sync, "npm_command", lambda _: ["/usr/bin/npm"])
    monkeypatch.setattr(
        check_frontend_lockfile_sync.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0),
    )

    assert check_frontend_lockfile_sync.sync_lockfile(fail_on_change=True) == 1
    assert "did not generate" in capsys.readouterr().err


def test_pre_push_rejects_uncommitted_package_files(monkeypatch, capsys) -> None:
    monkeypatch.setattr(check_frontend_lockfile_sync.shutil, "which", lambda _: "/usr/bin/git")

    def run(command, *, cwd, stdout, stderr, check):
        assert cwd == check_frontend_lockfile_sync.REPO_ROOT
        assert stdout is subprocess.DEVNULL
        assert stderr is subprocess.DEVNULL
        assert check is False
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(check_frontend_lockfile_sync.subprocess, "run", run)

    assert check_frontend_lockfile_sync.package_files_are_committed() is False
    assert "before pushing" in capsys.readouterr().err


def test_pre_push_reports_git_verification_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(check_frontend_lockfile_sync.shutil, "which", lambda _: "/usr/bin/git")
    monkeypatch.setattr(
        check_frontend_lockfile_sync.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 128),
    )

    assert check_frontend_lockfile_sync.package_files_are_committed() is False
    assert "Unable to verify" in capsys.readouterr().err
