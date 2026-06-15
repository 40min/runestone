#!/usr/bin/env python3
"""Validate that the frontend lockfile can satisfy npm ci on a clean checkout."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
PACKAGE_FILES = ("package.json", "package-lock.json")


def main() -> int:
    """Run npm ci in an isolated temp directory using only the package files."""
    npm_executable = shutil.which("npm")
    if npm_executable is None:
        print("npm is required to validate frontend lockfile sync.", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="runestone-frontend-lockfile-") as temp_dir:
        temp_frontend_dir = Path(temp_dir)
        for filename in PACKAGE_FILES:
            shutil.copy2(FRONTEND_DIR / filename, temp_frontend_dir / filename)

        result = subprocess.run(
            [
                npm_executable,
                "ci",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
            ],
            cwd=temp_frontend_dir,
            check=False,
        )
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
