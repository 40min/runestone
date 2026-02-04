---
name: final-checks
description: Run final verification for a change set by executing `make backend-test` and `make lint`, fixing failures, and rerunning until clean. Use this at the end of feature work or before handing off a PR.
---

# Final Checks

## Overview

Use this skill to finish a change by running the standard checks, fixing any failures, and rerunning until clean.

## Workflow

1. Run `make backend-test` and capture the failing tests.
2. Fix failures with minimal, targeted code changes.
3. Rerun `make backend-test` until green.
4. Run `make lint` and fix any formatting or lint issues.
5. Rerun `make lint` until clean.
6. Summarize what changed, which checks ran, and their status.

## Guardrails

- Use `make backend-test` and `make lint` directly (no `uv run` wrapper).
- If a tool command requires escalation, ask for approval and retry.
- Prefer focused fixes that do not broaden the change scope.
- If failures look unrelated to the current work, call that out before changing behavior.
