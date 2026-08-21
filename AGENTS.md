# Agent Instructions (Runestone)

## `__init__.py` Policy

Keep package `__init__.py` files empty unless there is an explicit, reviewed reason to add code.

Prefer module-level imports; avoid local imports where possible.

## Python API Conventions

- Do not use `from __future__ import annotations`. Quote genuine forward references as needed for Python 3.13.
- Prefer explicit named parameters. Do not introduce a bare keyword-only `*` or variadic `*args`/`**kwargs` in application-owned APIs unless required by a framework, protocol, inherited method, or decorator boundary. Keep unavoidable forwarding at that boundary.

## Dependency And Service Boundaries

- Treat constructor collaborators as required unless their absence is a deliberate, supported runtime mode. Do not make repositories, services, clients, or other injected collaborators optional merely to simplify tests, and do not construct fallback collaborators inside a service. Assemble the complete dependency graph at composition roots such as FastAPI dependencies, CLI entry points, workers, and test fixtures.
- A service may access only the repository for the domain it owns. When a workflow crosses domains, call the owning service or introduce an application-level coordinator; do not reach directly into another domain's repository.
- Keep transport layers such as API endpoints and Telegram workers dependent on services rather than repositories. Prefer a dedicated coordinator or unit of work for cross-service transactions. When endpoint-level orchestration is explicitly accepted as temporary technical debt, the endpoint may coordinate multiple services and commit or roll back their shared injected session, but it must not access repositories or row locks directly.
- Make transaction ownership explicit at the outer use-case boundary. Collaborating service operations that participate in the same transaction must not commit independently, and the outer service must commit or roll back exactly once.
- Preserve aggregate invariants in the same transaction as the triggering mutation. For recall queues this includes referential integrity, contiguous ordering, a valid cursor, and best-effort refill to the configured target size when an item is removed.
- Name repository and service methods for the aggregate or outcome they return. Avoid generic names such as `get_by_id` or `list_enabled` when the returned entity or eligibility rule is not obvious.
- Distinguish missing aggregates, missing domain entities, and missing collection membership in exception handling. A missing row during `SELECT ... FOR UPDATE` is not a lock-acquisition failure.
- Remove public methods that have no production callers. Tests alone do not justify retaining a public API.

## Development Workflows

Prefer the Makefile targets over spelling out raw tool commands; the Makefile also keeps the `uv` cache inside the repo for reproducible local and CI runs.

- While iterating on a change, prefer the narrowest checks available so feedback stays fast. In practice, that usually means targeted `uv run pytest tests/path -v` for backend work or running a specific frontend test file with `npm run test:run -- <file>` inside `frontend` rather than repo-wide or area-wide Make targets.
- Before opening a PR, pushing a review-round update, or otherwise sending changes upstream, run the broader validation pass. Start with `make check-readiness` for the standard repo-wide gate: read-only lint checks, backend and frontend tests, frontend lockfile validation, and a frontend build dry-run. Use `make backend-lint` or `make frontend-lint` when you want broader auto-fix formatting and linting, and `make backend-test` or `make frontend-test` when you specifically need those broader per-surface test runs outside the full gate.
- Add final-stage checks only when they match the change: run `make frontend-lockfile-sync` to regenerate `frontend/package-lock.json` after modifying `frontend/package.json`, followed by `make frontend-lockfile-check` to verify the sync, and commit both `frontend/package.json` and `frontend/package-lock.json` together before pushing. Run `make security-check` before sending changes that touch dependencies, security-sensitive code paths, or auth/configuration surfaces.
- For optional Better Stack Errors reporting, configure `SENTRY_DSN` only through deployment secrets; `SENTRY_ENVIRONMENT` and `SENTRY_RELEASE` provide optional metadata. Leave `SENTRY_DSN` empty in local development to disable reporting; the integration does not send default PII, request bodies, or tracing data.
- For manual broader sweeps outside the standard gate, prefer the composed Make workflows: make dev-test, make dev-full, make ci-lint, and make ci-test.
  - When you specifically want the standard aggregate entry points, use:
    - make lint for auto-fix linting across backend and frontend.
    - make test for both test suites without coverage.
    - make test-coverage when you need the backend coverage report plus the frontend test run.
- Use `make install` for production-only dependencies, `make install-dev` for the full Python development set, and `make install-all` when bootstrapping a fresh worktree. Use `make install-backend` and `make install-frontend` for partial dependency refreshes; `make install-backend` currently runs the same backend development dependency sync as `make install-dev`. In a fresh worktree, run `make install-dev` before readiness checks if tools such as `black` are missing, and run `make install-frontend` before focused frontend tests if Vitest is missing. Run `make setup` to install pre-commit hooks (which also runs `install-dev` under the hood).
- OpenCode LSP support is enabled by `opencode.json`; keep its project-local servers available with `make install-dev` for Pyright and `npm install` at the repository root for TypeScript and `typescript-language-server`, then restart OpenCode and inspect effective configuration/logs before relying on navigation. LSP setup is separate from the readiness gate.
- Start services with `make run-backend` (applies Alembic migrations, serves FastAPI on port 8010), `make run-frontend` (Vite on port 5173), or `make run-dev` for both.
- For CLI and prompt-debugging workflows, use `make run IMAGE_PATH=...`, `make load-vocab CSV_PATH=... [USER_ID=1] [SKIP_EXISTENCE_CHECK=true]`, and the prompt targets `make test-prompts-ocr`, `make test-prompts-analysis TEXT=...`, `make test-prompts-vocabulary WORD=... [MODE=example_only|extra_info_only|all_fields]`, and `make test-grammar-search QUERY=...`.
- For model-cost pricing maintenance, use `make update-model-prices` to refresh `state/model_prices.json`; use `uv run python scripts/update-model-prices.py --check` to validate live sources without replacing the runtime snapshot.
- Database-backed tests use the PostgreSQL database configured in `.env.test` and are intended to run serially against the shared schema. Do not use `pytest -n auto` there; mark tests that genuinely require independent connections with `@pytest.mark.db_schema_reset`.
- When touching the Telegram recall worker or containerized dev stack, use `make run-recall`, `make init-state`, `make docker-up`, `make docker-down`, and `make docker-build`.
- For the guarded PostgreSQL recall integration workflow, read `integration_tests/recall/README.md`: it is outside pytest and readiness checks, previews with `UV_CACHE_DIR=.uv-cache uv run --extra dev python integration_tests/recall/run_recall_workflow.py --show-coverage`, and requires deliberate `--apply` plus matching user, host, and database confirmations before temporarily mutating user 5's state.
- For refreshing running containers, prefer `make restart-recall`, `make rebuild-restart-recall`, or `make rebuild-restart-all` over ad hoc Docker commands.
- Use `make rebuild-container NAMES="..."` only for explicit full container rebuilds; **note** that this target also runs `git pull` and `sudo docker` cleanup steps, which may affect local changes.
- Manage schema changes through Alembic targets: `make db-init`, `make db-migrate MESSAGE="..."`, `make db-upgrade`, `make db-downgrade REVISION=...`, `make db-current`, and `make db-history`.
- Use `make clean` when caches or generated artifacts may be skewing local results, and `make info` when you need a quick environment snapshot while debugging setup issues.

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
- Avoid comments that just restate the next line, numbered “step” comments for routine CRUD flow, or stale references to old architecture. Use concise numbered phase comments for genuinely multi-step algorithms when locking, transaction order, retries, or external side effects make the sequence important.
- When useful, explain why an operation happens in a specific order, especially around persistence, background tasks, and history trimming.
