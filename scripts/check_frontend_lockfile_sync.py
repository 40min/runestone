#!/usr/bin/env python3
"""Validate that the frontend lockfile can satisfy npm ci on a clean checkout."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
PACKAGE_FILES = ("package.json", "package-lock.json")


def pinned_npm_version() -> str:
    """Return the npm version shared by local checks and the frontend image."""
    package_data = json.loads((FRONTEND_DIR / "package.json").read_text())
    package_manager = package_data.get("packageManager", "")
    name, separator, version = package_manager.rpartition("@")
    if separator == "" or name != "npm" or not version:
        raise ValueError('frontend/package.json must define "packageManager": "npm@<version>"')
    return version


def run_pinned_npm(arguments: list[str], cwd: Path) -> int:
    """Run pinned npm on the same Linux image used by the frontend build."""
    docker_executable = shutil.which("docker")
    if docker_executable is None:
        print("Docker is required to validate frontend lockfile sync.", file=sys.stderr)
        return 1

    try:
        npm_version = pinned_npm_version()
    except (json.JSONDecodeError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1

    result = subprocess.run(
        [
            docker_executable,
            "run",
            "--rm",
            "--volume",
            f"{cwd.resolve()}:/app",
            "--workdir",
            "/app",
            "--env",
            f"NPM_VERSION={npm_version}",
            "node:20-alpine",
            "sh",
            "-c",
            'npm install --global "npm@$NPM_VERSION" >/dev/null && npm "$@"',
            "npm",
            *arguments,
        ],
        check=False,
    )
    return result.returncode


def main() -> int:
    """Sync or validate the lockfile with the deployment npm version."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Regenerate package-lock.json with the pinned npm version.",
    )
    args = parser.parse_args()

    if args.sync:
        with tempfile.TemporaryDirectory(prefix="runestone-frontend-lockfile-sync-") as temp_dir:
            temp_frontend_dir = Path(temp_dir)
            shutil.copy2(FRONTEND_DIR / "package.json", temp_frontend_dir / "package.json")
            result = run_pinned_npm(
                ["install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund"],
                temp_frontend_dir,
            )
            if result == 0:
                shutil.copy2(temp_frontend_dir / "package-lock.json", FRONTEND_DIR / "package-lock.json")
            return result

    with tempfile.TemporaryDirectory(prefix="runestone-frontend-lockfile-") as temp_dir:
        temp_frontend_dir = Path(temp_dir)
        for filename in PACKAGE_FILES:
            shutil.copy2(FRONTEND_DIR / filename, temp_frontend_dir / filename)

        return run_pinned_npm(
            [
                "ci",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
            ],
            temp_frontend_dir,
        )


if __name__ == "__main__":
    raise SystemExit(main())
