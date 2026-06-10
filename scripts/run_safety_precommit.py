#!/usr/bin/env python3
"""Run Safety in pre-commit without blocking on interactive authentication."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def main() -> int:
    """Run a dependency scan when Safety credentials are available."""
    if not os.getenv("SAFETY_API_KEY"):
        print(
            "Skipping Safety scan: set SAFETY_API_KEY to enable non-interactive dependency checks.",
            file=sys.stderr,
        )
        return 0

    safety_executable = shutil.which("safety")
    if safety_executable is None:
        print("Safety executable is unavailable in the hook environment.", file=sys.stderr)
        return 1

    result = subprocess.run(
        [
            safety_executable,
            "--disable-optional-telemetry",
            "scan",
            "--target",
            ".",
            "--output",
            "bare",
        ],
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
