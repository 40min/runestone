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
        check=False,
    )
    if result.returncode != 0:
        print(
            "Commit frontend/package.json and frontend/package-lock.json before pushing.",
            file=sys.stderr,
        )
        return False
    return True


def sync_lockfile(*, fail_on_change: bool, require_committed: bool = False) -> int:
    """Regenerate the lockfile and enforce the requested consistency checks."""
    npx_executable = shutil.which("npx")
    if npx_executable is None:
        print("npx is required to synchronize the frontend lockfile.", file=sys.stderr)
        return 1

    try:
        npm_version = pinned_npm_version()
        original_lockfile = PACKAGE_LOCK.read_bytes() if PACKAGE_LOCK.exists() else None
    except (json.JSONDecodeError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1

    result = subprocess.run(
        [
            npx_executable,
            "--yes",
            f"npm@{npm_version}",
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
