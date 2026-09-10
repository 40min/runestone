#!/usr/bin/env python3
"""Run Safety in pre-commit without blocking on interactive authentication."""

import os
import shutil
import subprocess
import sys


def main() -> int:
    """Run a dependency scan when Safety credentials are available.

    The scan is optional during ordinary local pre-commit runs. When
    SAFETY_REQUIRED=1 the scan must run; a missing SAFETY_API_KEY is treated
    as a hard failure so CI cannot silently skip dependency checks.
    """
    api_key = os.getenv("SAFETY_API_KEY")
    required = os.getenv("SAFETY_REQUIRED") == "1"
    if not api_key:
        if required:
            print(
                "Safety scan is required (SAFETY_REQUIRED=1) but SAFETY_API_KEY is not set.",
                file=sys.stderr,
            )
            return 1
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
