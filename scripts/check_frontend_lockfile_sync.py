#!/usr/bin/env python3
"""Keep the frontend lockfile synchronized with its package manifest."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
PACKAGE_JSON = FRONTEND_DIR / "package.json"
PACKAGE_LOCK = FRONTEND_DIR / "package-lock.json"


def pinned_npm_version() -> str:
    """Return the npm version declared for frontend dependency operations."""
    package_data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    package_manager = package_data.get("packageManager", "")
    name, separator, version = package_manager.rpartition("@")
    if separator == "" or name != "npm" or not version:
        raise ValueError('frontend/package.json must define "packageManager": "npm@<version>"')
    return version


def package_files_are_committed() -> bool:
    """Return whether the package manifest and lockfile match the current commit."""
    git_executable = shutil.which("git")
    if git_executable is None:
        print("git is required to verify committed frontend package files.", file=sys.stderr)
        return False

    result = subprocess.run(
        [
            git_executable,
            "diff",
            "--quiet",
            "HEAD",
            "--",
            str(PACKAGE_JSON.relative_to(REPO_ROOT)),
            str(PACKAGE_LOCK.relative_to(REPO_ROOT)),
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode == 1:
        print(
            "Commit frontend/package.json and frontend/package-lock.json before pushing.",
            file=sys.stderr,
        )
        return False
    if result.returncode != 0:
        print("Unable to verify committed frontend package files.", file=sys.stderr)
        return False
    return True


def npm_command(pinned_version: str) -> list[str] | None:
    """Use matching local npm when available, otherwise return a pinned npx command."""
    npm_executable = shutil.which("npm")
    if npm_executable is not None:
        try:
            version_result = subprocess.run(
                [npm_executable, "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            version_result = None
        if (
            version_result is not None
            and version_result.returncode == 0
            and version_result.stdout.strip() == pinned_version
        ):
            return [npm_executable]

    npx_executable = shutil.which("npx")
    if npx_executable is None:
        return None
    return [npx_executable, "--yes", f"npm@{pinned_version}"]


def sync_lockfile(*, fail_on_change: bool, require_committed: bool = False) -> int:
    """Regenerate the lockfile and enforce the requested consistency checks."""
    try:
        npm_version = pinned_npm_version()
        original_lockfile = PACKAGE_LOCK.read_bytes() if PACKAGE_LOCK.exists() else None
    except (json.JSONDecodeError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1

    command = npm_command(npm_version)
    if command is None:
        print("npm or npx is required to synchronize the frontend lockfile.", file=sys.stderr)
        return 1

    result = subprocess.run(
        command
        + [
            "install",
            "--package-lock-only",
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
        ],
        cwd=FRONTEND_DIR,
        check=False,
    )
    if result.returncode != 0:
        return result.returncode

    if not PACKAGE_LOCK.exists():
        print("npm did not generate frontend/package-lock.json.", file=sys.stderr)
        return 1

    if fail_on_change and PACKAGE_LOCK.read_bytes() != original_lockfile:
        print(
            "frontend/package-lock.json was updated; commit it and retry.",
            file=sys.stderr,
        )
        return 1

    if require_committed and not package_files_are_committed():
        return 1

    return 0


def main() -> int:
    """Synchronize the lockfile, failing by default when it had been stale."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Update package-lock.json without failing when it changes.",
    )
    parser.add_argument(
        "--require-committed",
        action="store_true",
        help="Fail when the package manifest or lockfile differs from HEAD.",
    )
    args = parser.parse_args()
    return sync_lockfile(
        fail_on_change=not args.sync,
        require_committed=args.require_committed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
