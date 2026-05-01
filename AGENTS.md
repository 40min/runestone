# Agent Instructions (Runestone)

## `__init__.py` Policy

Keep package `__init__.py` files empty unless there is an explicit, reviewed reason to add code.

## Development Workflows

Prefer the Makefile targets over spelling out raw tool commands; the Makefile also keeps the `uv` cache inside the repo for reproducible local and CI runs.

- Use `make check-readiness` before commit-sized changes. It runs lint checks, backend and frontend tests, then a frontend build dry-run.
- Use scoped checks while iterating: `make backend-test`, `make frontend-test`, `make lint-check`, or targeted `uv run pytest tests/path -v` for backend tests.
- Bootstrap a fresh worktree with `make setup` or `make install-dev`; use `make install-backend` and `make install-frontend` when only one side of the stack needs dependency refreshes.
- Use `make run IMAGE_PATH=... GEMINI_API_KEY=...` for the CLI image-processing flow and `make load-vocab CSV_PATH=...` for vocabulary imports instead of calling the package entry points directly.
- Start services with `make run-backend` (applies Alembic migrations, serves FastAPI on port 8010), `make run-frontend` (Vite on port 5173), or `make run-dev` for both.
- When touching the Telegram recall worker or containerized dev stack, use `make run-recall`, `make docker-up`, `make docker-down`, and `make docker-build`; when refreshing running containers, prefer `make restart-recall`, `make rebuild-restart-recall`, `make rebuild-restart-all`, or `make rebuild-container NAMES="..."` over ad hoc Docker commands.
- Manage schema changes through Alembic targets: `make db-init`, `make db-migrate MESSAGE="..."`, `make db-upgrade`, `make db-downgrade REVISION=...`, `make db-current`, and `make db-history`.
- Use prompt and RAG smoke targets when touching prompt construction or grammar retrieval: `make test-prompts-ocr`, `make test-prompts-analysis TEXT="..."`, `make test-prompts-vocabulary WORD="..."`, and `make test-grammar-search QUERY="..."`.

For LangChain `@tool` tests, use `.ainvoke()` for tools without `ToolRuntime`; use `.coroutine(runtime, ...)` with a manually constructed runtime for tools that depend on `ToolRuntime` context.

## Docstrings And Comments

Write docstrings and comments to explain intent, invariants, and business rules, not to narrate obvious code.

- Add module docstrings for service, agent, and other orchestration-heavy files when they benefit from a one-line responsibility summary.
- Add class docstrings for public services/managers that explain ownership boundaries and what the class coordinates.
- Add method docstrings for public or non-trivial internal methods when behavior, side effects, lifecycle, or return semantics are not obvious.
- At public entry points, describe parameters when the name alone is ambiguous or domain-specific, for example flags, cursors, ids, and tuning values such as playback `speed`.
- Prefer documenting parameters at the first meaningful boundary where another reader would need the explanation; do not repeat the same parameter prose through every downstream helper.
- Prefer concise prose in sentence case. Keep docstrings current with the actual async/background behavior and collaborator names.
- Use inline comments sparingly for non-obvious decisions, phase boundaries, truncation/capping rules, persistence order guarantees, or intentionally surprising behavior.
- Avoid comments that just restate the next line, numbered “step” comments for routine CRUD flow, or stale references to old architecture.
- When useful, explain why an operation happens in a specific order, especially around persistence, background tasks, and history trimming.
