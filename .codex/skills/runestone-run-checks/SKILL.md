---
name: runestone-run-checks
description: Run Runestone quality checks when the user asks "run checks". Select the smallest safe make-target set based on changed files (backend-only, frontend-only, or mixed scope).
---

# Runestone Run Checks

Use this skill in `/Users/40min/www/runestone` when the user asks to "run checks".

## Goal

Run tests and lint checks with the smallest safe command set, using only `make` targets from `/Users/40min/www/runestone/Makefile`.

## Command Policy

- Always execute checks via `make` targets only.
- Do not invoke raw `pytest`, `ruff`, `black`, `npm test`, or `npm run lint` directly when this skill is active.
- Prefer scoped targets when the changed surface is clearly backend-only or frontend-only.

## Scope Detection

Determine changed files from git working tree (staged, unstaged, and untracked) before choosing commands.

Treat as frontend files:

- `frontend/**`

Treat as backend files:

- `src/**`
- `tests/**`
- `alembic/**`
- `scripts/**`
- `recall_main.py`
- `pyproject.toml`
- `uv.lock`

Treat as global/mixed-impact files (force full checks):

- `Makefile`
- `docker-compose.yml`
- `README.md`
- `.env*`
- Any change set containing both frontend and backend files

If scope is unclear, run full checks.

## Command Matrix

1. Backend-only changes
- `make backend-test`
- `make backend-lint`

2. Frontend-only changes
- `make frontend-test`
- `make frontend-lint`

3. Mixed/global/unclear changes
- `make test`
- `make lint-check`

## Reporting

After running checks, report:

- Commands executed
- Pass/fail per command
- First actionable failure summary when a command fails
