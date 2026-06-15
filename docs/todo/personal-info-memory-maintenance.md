# Personal Info Memory Maintenance

## Context

Current memory architecture still treats `personal_info` as both:

- the raw durable-fact store
- the Teacher-facing startup memory payload

That coupling is what we want to undo.

The target direction is:

- `MemoryKeeper` should append `personal_info` items only
- duplicate detection, consolidation, and cleanup should belong to
  `memory_maintainer`
- Teacher should consume one consolidated summary field instead of a raw list of
  `personal_info` items

Related existing Dart task:

- `PUxciBG7serB`
- `ref: memory maintainer -- maintain personal info as well`

## Corrections To The Initial Proposal

### 1) Personal-info maintenance should be a separate async maintainer flow

`memory_maintainer` should gain a separate housekeeping process for
`personal_info`.

Requirements:

- run asynchronously like the existing chat-reset maintenance path
- keep CLI support
- keep deterministic, multi-step planning/execution with good dry-run/testability
- avoid folding `personal_info` maintenance into the exact same workflow as
  `area_to_improve`, because the maintenance logic is different

`area_to_improve` remains a merge-oriented deduplication problem.

`personal_info` is instead a fact-consolidation and summary-synthesis problem.

### 2) Refactor maintainer internals into separate modules

The current `memory_maintainer` code is already large enough that adding
`personal_info` logic directly into the same file would make it harder to
reason about, test, and iterate on.

Planned direction:

- keep one high-level `memory_maintainer` entrypoint/orchestrator
- extract `area_to_improve` maintenance routines into a dedicated module
- extract `personal_info` maintenance routines into a dedicated module
- keep shared structured-output helpers and execution utilities in shared
  maintainer support modules where useful

This refactor is part of the planned work, not an optional cleanup.

### 3) Summary field name

Use `personal_info_summary`, not `teacher_profile_summary`.

Reasoning:

- it is more precise
- it keeps the field tied to the source domain
- it avoids implying a broader user profile abstraction than what we actually
  store

### 4) Risk assessment

The previously noted freshness risk is considered negligible for this task.

We do not currently treat it as a blocking architecture concern.

### 5) Scope assumption

The append-only assumption applies to `personal_info`.

`area_to_improve` does not inherit this rule from this task.

## Desired End State

### Raw memory ownership

`personal_info` memory items become the append-only raw evidence layer.

That means:

- `MemoryKeeper` may add new `personal_info` items
- `MemoryKeeper` should not try to deduplicate, consolidate, or decide whether
  an equivalent fact already exists
- broad fact reconciliation belongs to `memory_maintainer`

### Maintainer ownership

`memory_maintainer` becomes responsible for:

- reviewing raw `personal_info` items
- resolving duplicates and near-duplicates
- deciding which old facts should be deleted
- deciding which conflicting facts should be marked outdated or otherwise
  removed from active representation
- producing one solid synthesized summary of the user
- persisting that summary into `users.personal_info_summary`

### Teacher memory read path

Teacher startup context should stop depending on a list of raw `personal_info`
items.

Instead, first-turn Teacher injection should use:

- `personal_info_summary`
- existing `area_to_improve` starter memory

This means the system is moving away from a raw list-shaped `personal_info`
prompt payload and toward one consolidated field in the user profile.

## Planned Changes

### MemoryKeeper

- change `personal_info` write behavior to append-only semantics
- stop using existence checks as a prerequisite for adding `personal_info`
- keep `area_to_improve` behavior unchanged unless explicitly required by a
  separate task

### MemoryMaintainer

- keep the existing async chat-reset entrypoint
- add a separate `personal_info` housekeeping flow
- preserve CLI execution and dry-run support for both maintenance domains
- split the bloated implementation into separate modules for:
  - `area_to_improve`
  - `personal_info`
  - shared maintainer helpers where needed
- make `personal_info` maintenance responsible for building
  `personal_info_summary`

### Persistence

- add `users.personal_info_summary`
- treat it as internal derived state, not as the raw source of truth
- keep raw source facts in `memory_items`

### Teacher integration

- replace first-turn raw `personal_info` starter injection with
  `personal_info_summary`
- keep `area_to_improve` startup injection
- review whether Teacher should stop emitting `personal_info` id-based update
  tags once raw `personal_info` rows are no longer part of Teacher context

### Documentation

Documentation updates are part of the planned implementation, not an
afterthought.

Planned documentation work includes:

- update `docs/memory-maintainer.md` to describe the split maintainer flows
- update `docs/agent-swarm-architecture.md` so memory ownership matches runtime
  reality
- update any Teacher-memory docs that still describe raw `personal_info`
  starter injection as the target design
- keep this note in `docs/todo` as the planning artifact until implementation
  lands

## Suggested Task Split

### Existing task stays focused on maintainer ownership

Keep `PUxciBG7serB` focused on:

- extending maintainer ownership to `personal_info`
- consolidating personal info
- producing and persisting `personal_info_summary`
- refactoring maintainer internals into separate modules

### New follow-up task

Create a separate task for the cross-cutting runtime changes:

- make `MemoryKeeper` append-only for `personal_info`
- switch Teacher startup injection from raw `personal_info` items to
  `personal_info_summary`
- remove or revise Teacher-side `personal_info` update-tag assumptions as needed
- update affected docs as part of the implementation

## Non-Goals

- changing `area_to_improve` to append-only
- redesigning the entire user profile API surface
- treating freshness concerns as a blocker for this iteration
