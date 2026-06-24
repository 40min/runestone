# Personal Info Status Redesign: Chat Summary

This document summarizes the work completed in the `codex/personal-info-status-redesign` worktree during the current chat.

## Goal

Refactor `personal_info` so public CRUD stays simple for users and UI, while agent-only workflow statuses remain internal and are interpreted only by the personal-info maintainer.

## Final direction

- Public API keeps one shared memory shape across categories.
- `personal_info.status` is hidden from public/UI semantics by returning `null` in API responses.
- Public/manual `personal_info` create and edit flows operate on active fact rows only.
- Public status updates for `personal_info` are rejected.
- Agent append flow for `personal_info` uses internal statuses:
  - `active`
  - `correction`
  - `outdated`
- `PersonalMemoryKeeper` remains append-only and read-blind.
- `PersonalInfoMemoryMaintainer` is the only component that interprets non-active personal-info rows.

## API and service changes

- Removed the dedicated public content-only update endpoint in favor of generic update-by-id flow.
- Removed unnecessary public-response masking helper `_to_public_memory_response`.
- Kept shared API structures, but made public `status` handling category-aware.
- Added/kept validation so public status semantics remain for `area_to_improve`, not for `personal_info`.
- Updated backend service behavior so public `personal_info` CRUD acts on active rows only.

## Agent and maintainer changes

- Moved personal-info workflow status ownership to agent-side schemas via `AgentPersonalInfoStatus`.
- Updated `PersonalMemoryKeeper` prompt/tooling to emit:
  - `active` for new durable facts
  - `correction` for replacements
  - `outdated` for forget/remove requests
- Removed the old stale-outdated retention idea from the personal-info maintainer path.

## Deterministic personal-info maintainer flow

The personal-info maintainer was strengthened to follow a more deterministic multi-pass pipeline similar to `area_to_improve`:

1. Load the full `personal_info` scope.
2. Ask the model to group rows into candidate topic buckets.
3. Repair and validate bucket coverage deterministically in Python.
4. Leave singleton buckets untouched.
5. For every multi-item bucket:
   - review it into exact same-topic groups
   - order source rows chronologically
   - bake each multi-item group into either:
     - one final active fact, or
     - full deletion when the fact is retired
6. Build `personal_info_summary` from the final active fact set only.
7. In apply mode:
   - create one baked active row for surviving multi-item groups
   - delete consumed source rows
   - persist the summary

This gives the maintainer a clearer ownership boundary:

- keeper appends evidence rows
- maintainer reconciles and bakes final facts

## Files materially changed during this chat

- `src/runestone/agents/specialists/memory_maintainer/personal_info.py`
- `tests/agents/specialists/test_memory_maintainer_personal_info.py`

Related redesign work already present in the worktree and validated during this chat:

- `src/runestone/agents/schemas.py`
- `src/runestone/agents/specialists/personal_memory_keeper.py`
- `src/runestone/agents/tools/memory.py`
- `src/runestone/api/memory_endpoints.py`
- `src/runestone/api/memory_item_schemas.py`
- `src/runestone/services/memory_item_service.py`
- `tests/api/test_memory_endpoints.py`
- `tests/services/test_memory_item_service.py`
- `frontend/src/components/chat/AgentMemoryModal.tsx`
- `frontend/src/components/chat/AgentMemoryModal.test.tsx`
- `frontend/src/hooks/useMemoryItems.ts`

## Validation run in this chat

Passed:

- `python -m py_compile src/runestone/agents/specialists/memory_maintainer/personal_info.py tests/agents/specialists/test_memory_maintainer_personal_info.py`
- `uv run pytest tests/agents/specialists/test_memory_maintainer_personal_info.py -q`
- `uv run pytest tests/services/test_memory_item_service.py tests/api/test_memory_endpoints.py -q`
- `cd frontend && npm run test:run -- src/components/chat/AgentMemoryModal.test.tsx`

## Notable decisions from the discussion

- We did not re-expand `PersonalMemoryKeeper` beyond append-only behavior.
- We did not introduce deterministic key targeting in the keeper.
- We chose agent-side statuses over status markers embedded in `content`.
- We kept one shared memory API instead of splitting endpoints by category.
- We strengthened the personal-info maintainer with deterministic bucket validation and baking instead of relying on prompt wording alone.
