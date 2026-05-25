# Teacher Memory Read Slimdown

## Context

Teacher currently has two memory-reading surfaces during chat orchestration:

- first-turn starter memory injected by the manager
- on-demand `read_memory` tool access during response generation

The current first-turn starter bundle is already limited for `area_to_improve`,
but the live `read_memory` tool can still return a much larger payload than we
want for routine teaching. We want to reduce prompt size and latency, with the
main focus on `Teacher` and `MemoryKeeper`.

This note now captures both the agreed direction and the current implementation
status for the Teacher-focused portion.

## Agreed Changes

### 1) Teacher: replace broad memory tool with a narrow focus tool

Replace `read_memory` on `TeacherAgent` with a narrower tool:

- new name: `read_active_learning_focus`
- scope is hardcoded to:
  - category `area_to_improve`
  - status `struggling` or `improving`
- return only the top 5 items
- order by priority first
- no category/status arguments exposed to Teacher
- no `personal_info` lookup through this tool

Reasoning:

- this keeps Teacher able to inspect active learning issues when the student
  explicitly asks about memory or when the reply genuinely needs it
- it removes the broad memory-scan path that can bloat prompt context
- it keeps only one useful live memory surface for Teacher instead of a general
  purpose memory browser

Implementation status:

- implemented
- `TeacherAgent` now exposes `read_active_learning_focus` instead of
  `read_memory`
- the tool performs a single backend read scoped to `area_to_improve` with
  statuses `struggling` and `improving`
- backend filtering was standardized internally on `statuses` to support this
  single-query path

### 2) Teacher: keep first-turn `personal_info` starter load for now

We are intentionally **not** changing the current first-turn `personal_info`
starter load in this step.

Current decision:

- keep starter `personal_info` injection as-is for now
- keep the existing cap for now because those items are typically small

Future direction:

- replace raw `personal_info` JSON starter data with an aggregated
  teacher-facing text summary capped by length

Tracked separately in Dart:

- `Aggregate teacher personal_info prompt context`
- task id: `7mMWNe6uVNxT`
- URL: <https://app.dartai.com/t/7mMWNe6uVNxT-Aggregate-teacher-personal>

Implementation status:

- implemented as a non-change
- starter `personal_info` injection and caps remain unchanged in this pass
- the future aggregation/summarization work is not implemented here

### 3) Teacher: prefer shorter teacher-facing memory formatting

For the narrow active-learning read path, prefer a short teacher-facing format
over the current full JSON payload with ids and timestamps.

Intent:

- keep the returned information easy for the model to use
- avoid paying prompt cost for fields that do not help the teaching reply

This means a compact formatted summary is preferred over the broad
machine-oriented JSON payload used by the general memory tools.

Implementation status:

- implemented
- Teacher now receives a compact, explicitly untrusted quoted-data summary for
  active learning focus
- starter memory and maintainer/broad memory reads now use the same untrusted
  quoted-data style (with id/category/status fields preserved for tool-driven
  workflows)

### 4) Teacher: keep explicit memory lookup capability

We are **not** removing live Teacher memory lookup entirely.

Reason:

- students sometimes explicitly ask the teacher to look into memory during chat

So the target state is:

- starter memory still exists on first turn
- Teacher still has a live lookup path
- but that live lookup path is intentionally tiny and scoped only to active
  `area_to_improve`

Implementation status:

- implemented for Teacher
- the first-turn starter bundle remains unchanged
- `personal_info` is still available only via starter memory, not via Teacher's
  live lookup tool

## MemoryKeeper Update

Implementation status:

- not implemented in this change set
- the current code changes are intentionally limited to Teacher, shared backend
  memory filtering, and the MemoryMaintainer single-read path
- the three-case `MemoryKeeper` simplification below remains planned follow-up
  work

`MemoryKeeper` should move to a three-case split.

### Case A: student explicitly asks to edit memory

Examples:

- remember / forget
- correct memory
- reprioritize memory
- mark something mastered

Behavior:

- keep read-before-write behavior
- inspect relevant existing memory first
- then write/update/delete as needed

Implementation status:

- not implemented in this change set
- current `MemoryKeeper` behavior has not been refactored to explicitly model
  this case split yet

### Case B: teacher explicitly points out a new durable issue

Examples:

- a new recurring struggle
- a newly named durable weakness to remember

Behavior:

- do **not** require memory inspection first
- just append/create the new memory item

Reason:

- this is the fastest path to stop over-reading and reduce post-turn latency
- duplicate cleanup can be handled later by `MemoryMaintainer`

Implementation status:

- not implemented in this change set
- current `MemoryKeeper` has not been simplified to append/create without a
  required pre-read for this case

### Case C: teacher explicitly signals improvement/mastery/replacement/priority change

Behavior:

- allow append/write behavior without forcing a pre-read in this change set
- do not block this simplification on perfect update targeting right now

Note:

- this is intentionally a pragmatic "stop the fire first" decision
- follow-up cleanup and consolidation quality will rely more heavily on
  `MemoryMaintainer`

Implementation status:

- not implemented in this change set
- current `MemoryKeeper` has not yet been simplified to allow this append/write
  path without a forced pre-read

## Important Caveat

This plan intentionally reduces immediate correctness safeguards in favor of
lower prompt cost and lower latency.

Known tradeoff:

- append-first MemoryKeeper behavior can increase duplicate or overlapping
  `area_to_improve` items until `MemoryMaintainer` cleanup is improved and
  re-enabled confidently

That tradeoff is accepted for now as the next-step work will focus on
stabilizing and trusting `MemoryMaintainer`.

Implementation status:

- pending follow-up
- the tradeoff is documented, but the underlying append-first `MemoryKeeper`
  simplification has not landed yet

## Double-Check: critical user facts already provided outside memory

Before removing Teacher access to live `personal_info`, keep relying on direct
non-memory user context that is already injected elsewhere:

- `mother_tongue`
- timezone / current datetime context

This should be verified during implementation so the Teacher still has the
important personalization signals even without live `personal_info` fetches.

Implementation status:

- verified for this pass
- Teacher prompt injection still includes `mother_tongue` when present
- Teacher prompt injection still includes current datetime and timezone context

## Expected Implementation Areas

- `src/runestone/agents/tools/memory.py`
- `src/runestone/agents/tools/utils.py`
- `src/runestone/agents/specialists/teacher.py`
- `src/runestone/agents/tools/memory_maintainer.py`
- `src/runestone/services/memory_item_service.py`
- `src/runestone/db/memory_item_repository.py`
- `src/runestone/api/memory_endpoints.py`
- related tests under `tests/agents/`

## Landed Scope

Implemented in this pass:

- Teacher live lookup narrowed from `read_memory` to
  `read_active_learning_focus`
- shared backend list filtering moved to `statuses`
- `/api/memory` kept backward-compatible with legacy `status` query callers
- `maintainer_read_memory` consolidated to one read for `struggling` and
  `improving`

Not implemented in this pass:

- `MemoryKeeper` workflow simplification
- starter `personal_info` aggregation or summarization
