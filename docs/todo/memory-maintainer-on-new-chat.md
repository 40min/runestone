# Background Memory Maintainer On New Chat

## Context

This change introduces a dedicated background memory-maintenance specialist that runs
when a student starts a new chat session. It is intentionally fire-and-forget and
must not block chat reset.

## Goal

- Run startup memory maintenance after `DELETE /api/chat/history`.
- Keep normal chat reset response latency low.
- Avoid duplicate concurrent maintenance runs for the same user.
- Keep turn-time memory updates and startup maintenance responsibilities separate.

## Implemented Behavior

### 1) New specialist: `memory_maintainer`

Added:

- `src/runestone/agents/specialists/memory_maintainer.py`

The specialist:

- uses a maintenance-specific system prompt
- runs as an internal agent (not user-facing)
- scopes review to `area_to_improve` with status `struggling` / `improving`
- uses maintainer-scoped tools:
  - `maintainer_read_memory`
  - `maintainer_insert_memory_item`
  - `maintainer_delete_memory_item`
  - `maintainer_update_memory_priority`
- enforces merge guardrails at tool runtime:
  - replacement items must stay in category/status scope
  - cross-status replacement in one merge is rejected
  - delete is only allowed for ids explicitly listed in the active merge replacement set
  - duplicate key collisions are handled via DB uniqueness on insert
- clears pending merge state at run start/end to avoid stale blocked state after failures/timeouts
- parses `SpecialistResult` from final JSON (including fenced JSON support)
- returns structured fallback `error` artifacts for invalid output / execution failure

### 2) Manager orchestration and in-memory gating

Updated:

- `src/runestone/agents/manager.py`

Changes:

- instantiate `MemoryMaintainerSpecialist` as `self.memory_maintainer`
- add a dedicated background registry keyed by `user_id`:
  - `self._memory_maintenance_registry`
- add:
  - `start_background_memory_maintenance(user: User) -> bool`
  - `run_memory_maintenance(user: User) -> SpecialistResult`

Scheduling behavior:

- if a maintenance task for `user.id` is already running, skip scheduling and return `False`
- otherwise schedule an `asyncio` background task and return `True`
- timeout background maintenance runs (`MEMORY_MAINTENANCE_TIMEOUT_SECONDS`)
- always unregister the task key on completion/failure
- log structured/sanitized completion result or failures

### 3) Chat reset hook

Updated:

- `src/runestone/services/chat_service.py`

`start_new_chat(user_id)` now:

1. rotates `current_chat_id`
2. loads user
3. schedules background memory maintenance
4. returns immediately

Failure policy:

- if user lookup fails, skip maintenance and keep reset successful
- if scheduling fails, log error and keep reset successful

### 4) MemoryKeeper boundary clarification

Updated:

- `src/runestone/agents/specialists/memory_keeper.py`

Prompt now explicitly states:

- broad startup consolidation / duplicate-cleanup sweeps are owned by `memory_maintainer`
- `memory_keeper` should only act on explicit per-turn signals

## Test Coverage Added/Updated

### New tests

- `tests/agents/specialists/test_memory_maintainer.py`

Validates:

- specialist JSON parsing
- fenced JSON parsing
- invalid-output fallback
- pending merge state cleanup on failed run
- chat-reset payload shape
- expected tool set passed to `create_agent`
- prompt includes scope/tool requirements
- duplicate-key insert rejection and cross-status replacement rejection

### Updated tests

- `tests/agents/specialists/test_memory_keeper.py`
  - asserts startup-compaction responsibility is excluded
- `tests/agents/test_manager.py`
  - schedules maintenance
  - duplicate scheduling skip while running
  - registry cleanup after success/failure/timeout
- `tests/services/test_chat_service.py`
  - new-chat path schedules maintenance
  - user-missing skip path
- `tests/api/conftest.py`
  - mock agent service includes `start_background_memory_maintenance`
- `tests/api/test_chat_endpoints.py`
  - clear history triggers maintenance scheduling

## Validation Run

Executed and passing:

```bash
make check-readiness
```

## Known Tradeoff

- Consolidation remains a multi-step agent tool flow (insert, then delete replaced ids), not a single DB transaction.
- If a run is interrupted between those steps, temporary duplicate overlap can exist until the next maintenance run.

## Changed Files (Implementation Scope)

- `src/runestone/agents/specialists/memory_maintainer.py` (new)
- `src/runestone/agents/manager.py`
- `src/runestone/services/chat_service.py`
- `src/runestone/agents/specialists/memory_keeper.py`
- `tests/agents/specialists/test_memory_maintainer.py` (new)
- `tests/agents/specialists/test_memory_keeper.py`
- `tests/agents/test_manager.py`
- `tests/services/test_chat_service.py`
- `tests/api/conftest.py`
- `tests/api/test_chat_endpoints.py`
