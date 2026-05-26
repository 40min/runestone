# MemoryKeeper Category-Aware Tags And Terminal No-Op Failures

## Context

`Teacher` can currently emit a temporary visible memory-update tag in its reply so
`MemoryKeeper` can target an existing memory item without an extra lookup.

Today that tag only carries the item id:

- `[memory:ID]`

This is too weak for reliable updates because:

- `Teacher` can see `personal_info` only from first-turn starter memory
- `Teacher` can live-read only `area_to_improve` via `read_active_learning_focus`
- `MemoryKeeper` receives only the current `teacher_response` and `student_message`
- a bare id loses category information during the Teacher -> MemoryKeeper handoff

This can lead to category-mixing failures, especially when `MemoryKeeper` tries to
apply an `area_to_improve`-only operation such as priority update to a
`personal_info` item.

There is also an undesirable fallback behavior after targeted-update failures:

- `MemoryKeeper` may keep trying additional writes after a failed targeted update
- this can produce duplicate creation attempts
- this can also contribute to multi-item reprioritization in a single turn

## Goal

- Preserve category information in the temporary memory-update tag.
- Keep the fix prompt-driven; do not add a new by-id lookup tool.
- Make targeted-update misses and wrong-category operations terminal no-ops for
  `MemoryKeeper`.
- Keep priority-scope boundaries prompt-only for now; do not add programmatic
  enforcement in this step.

## Agreed Changes

### 1) Change the temporary Teacher memory tag format

Replace:

- `[memory:ID]`

With:

- `[memory:<category>:<id>]`

Examples:

- `[memory:personal_info:42]`
- `[memory:area_to_improve:17]`

Decision:

- use the compact colon-triplet form
- do not use key-value syntax
- do not use dual tags

This keeps the tag short, parseable, and sufficient for category-aware handling.

### 2) Keep the fix prompt-driven instead of adding a by-id lookup tool

Decision:

- do not add a new `get_memory_item_by_id` or equivalent lookup tool
- do not change the service or repository surface for this task

Instead:

- `Teacher` must emit category together with id when it is confident both are correct
- `MemoryKeeper` must use that category-aware tag to select the correct write path

This is intentionally a prompt-contract change, not a new runtime capability.

### 3) Make targeted-update misses terminal no-ops

When `MemoryKeeper` attempts a targeted update and receives one of these expected
guardrail failures, it must stop immediately:

- `Memory item with id ... not found`
- `priority is only applicable to category 'area_to_improve'`

Decision:

- treat these as terminal no-ops
- log the failure
- return `status="no_action"`
- include a skip reason in artifacts / notes

`MemoryKeeper` must **not** do any of the following after such a failure:

- retry with another write tool
- create a replacement item
- create a duplicate item
- perform reprioritization of other items
- continue a broader "repair" flow in the same turn

### 4) Keep priority boundaries prompt-only for now

Decision:

- do not add programmatic caps such as "only one priority update per run"
- do not add runtime guards in tools or manager orchestration for this task

Instead, strengthen prompt guidance so that:

- `MemoryKeeper` may reprioritize only directly implicated item(s)
- single-item urgency changes are acceptable when the Teacher explicitly points to
  that item
- broad reprioritization, cleanup, and rebalancing remain `MemoryMaintainer`
  responsibilities

## Expected Implementation Areas

### Teacher prompt

Update `TeacherAgent` prompt instructions so that:

- all references to `[memory:ID]` become `[memory:<category>:<id>]`
- examples use both `personal_info` and `area_to_improve`
- Teacher is told to include the category only when it is confident the id and
  category match the intended item
- the temporary visible-tag behavior remains unchanged for now

### MemoryKeeper prompt

Update `MemoryKeeper` prompt instructions so that:

- Case C expects the category-aware tag format
- category from the tag drives the intended operation family
- targeted-update guardrail failures are terminal stop conditions
- fallback duplicate creation is no longer acceptable after targeted-update failure
- multi-item reprioritization remains out of scope for `MemoryKeeper`

### Tests

Update tests to match the new contract:

- replace prompt assertions that mention `[memory:ID]`
- replace fixture/history examples such as `[memory:137]` with
  `[memory:area_to_improve:137]`
- add prompt assertions for terminal no-op behavior on:
  - missing item
  - wrong-category priority attempt
- add prompt assertions that no fallback creation should occur after those failures

## Public Contract Change

The temporary visible Teacher memory-update tag changes from:

- `[memory:ID]`

To:

- `[memory:<category>:<id>]`

No new API endpoint, tool, schema, or repository method is introduced.

## Acceptance Criteria

- `Teacher` prompt documents only the category-aware tag format.
- `MemoryKeeper` prompt documents only the category-aware tag format.
- `MemoryKeeper` prompt explicitly stops on targeted-update `not found` and
  wrong-category priority failures.
- `MemoryKeeper` prompt explicitly forbids fallback duplicate creation after those
  failures.
- Existing tests that reference old tag format are updated.
- New tests cover the no-op stop behavior at the prompt-contract level.

## Chosen Defaults And Assumptions

- No backward-compatibility bridge for legacy `[memory:ID]` tags is required.
- The expected wrong-category guardrail for this task is the existing priority error:
  `priority is only applicable to category 'area_to_improve'`.
- Logging can stay at current tool / specialist boundaries.
- This task does not move the tag out of visible reply text; that remains a separate
  follow-up.
