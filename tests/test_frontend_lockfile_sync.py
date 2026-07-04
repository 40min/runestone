from __future__ import annotations

import subprocess

from scripts import check_frontend_lockfile_sync


def test_pinned_npm_version_reads_package_manager(tmp_path, monkeypatch) -> None:
    package_json = tmp_path / "package.json"
    package_json.write_text('{"packageManager": "npm@10.8.2"}', encoding="utf-8")
    monkeypatch.setattr(check_frontend_lockfile_sync, "PACKAGE_JSON", package_json)

    assert check_frontend_lockfile_sync.pinned_npm_version() == "10.8.2"


def test_check_updates_stale_lockfile_and_fails(tmp_path, monkeypatch, capsys) -> None:
    package_lock = tmp_path / "package-lock.json"
    package_lock.write_text("old", encoding="utf-8")
    monkeypatch.setattr(check_frontend_lockfile_sync, "FRONTEND_DIR", tmp_path)
    monkeypatch.setattr(check_frontend_lockfile_sync, "PACKAGE_LOCK", package_lock)
    monkeypatch.setattr(check_frontend_lockfile_sync, "pinned_npm_version", lambda: "10.8.2")
    monkeypatch.setattr(check_frontend_lockfile_sync.shutil, "which", lambda _: "/usr/bin/npx")

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
    monkeypatch.setattr(check_frontend_lockfile_sync.shutil, "which", lambda _: "/usr/bin/npx")

    def run(command, *, cwd, check):
        package_lock.write_text("new", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(check_frontend_lockfile_sync.subprocess, "run", run)

    assert check_frontend_lockfile_sync.sync_lockfile(fail_on_change=False) == 0


def test_pre_push_rejects_uncommitted_package_files(monkeypatch, capsys) -> None:
    monkeypatch.setattr(check_frontend_lockfile_sync.shutil, "which", lambda _: "/usr/bin/git")
    monkeypatch.setattr(
        check_frontend_lockfile_sync.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1),
    )

    assert check_frontend_lockfile_sync.package_files_are_committed() is False
    assert "before pushing" in capsys.readouterr().err
