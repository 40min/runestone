# Teacher Session Focus Freeze

## Context

Teacher currently receives starter `area_to_improve` memory by reselecting the
top high-priority active items. That selection is derived from mutable memory
statuses such as `struggling` and `improving`.

This becomes unstable within one chat session:

- Teacher may discuss one batch of items on an early turn.
- `LearningMemoryKeeper` or `memory_maintainer` may update statuses later.
- The next turn can then inject a different subset or ordering.
- Teacher can lose track of the exact items it was teaching and may reference
  stale or mismatched ids.

The goal of this work is to keep the active learning batch stable for the whole
chat session without introducing a second parallel status workflow.

## Agreed Direction

Freeze the selected learning-focus item ids once per chat session.

Rules:

- At session start, select the ordered batch from the current top
  `area_to_improve` items in `struggling` or `improving`.
- Persist that ordered id set for the active `chat_id`.
- On each teacher turn, reload those same ids from live memory rows and inject
  their current content and statuses.
- Keep reusing the frozen batch while at least one item is not `mastered`.
- When all items in the frozen batch are `mastered`, inject an explicit
  teacher-facing completion note and rotate to a newly selected batch.

Non-goal:

- Do not introduce a separate per-session status machine such as
  `planned`/`introduced`/`done-for-session`.

## Current Code Seam

The current starter selection happens in `AgentsManager.prepare_pre_turn()`,
which calls `memory_item_service.list_start_area_to_improve_items()` and
serializes the resulting rows into teacher prompt context.

That is the main seam to replace:

- selection should become session-aware and stable by `chat_id`
- teacher injection should hydrate a stored ordered id set, not reselect a new
  mutable subset on every turn

## Proposed Implementation Plan

- [x] Confirm the exact starter-memory call chain and identify the narrowest
  service boundary for session-focus selection and hydration.
- [x] Add a chat-session-scoped persistence surface for the frozen ordered item
  ids keyed by `user_id` and `chat_id`.
  Preferred direction: a dedicated structured persistence path rather than
  piggybacking on free-form `artifacts_json`.
- [x] Add a service method that returns the active session focus bundle:
  create the batch on first use for a chat session, otherwise reload the stored
  ids in stored order.
- [x] Keep live hydration semantics: after loading the stored ids, fetch current
  memory rows so Teacher always sees the latest `content`, `status`, and
  `priority` for those same items.
- [x] Add batch-completion logic: when every stored item is currently
  `mastered`, create a new batch from the latest eligible high-priority items
  and return an explicit completion note for Teacher.
- [x] Preserve deterministic ordering across the whole chat session, including
  after hydration.
- [x] Handle drift safely when an id disappears, is deleted, or is merged away:
  keep the remaining stored ids, log the drift, and replace only when the batch
  would otherwise become invalid or empty.
- [x] Decide and document the minimum validity threshold for partial drift.
  Default direction: do not silently refill a partially intact batch mid-session.
- [x] Update teacher-facing serialization only as needed to expose the frozen
  batch and completion note clearly without adding prompt bloat.
- [x] Add targeted tests for:
  - stable reuse of the same ordered ids across turns
  - live status hydration for frozen ids
  - batch rotation when all frozen items become `mastered`
  - missing-id drift behavior
  - preserved ordering after hydration and rotation

## Open Design Notes

### Persistence shape

The implementation needs one stable place to store:

- `user_id`
- `chat_id`
- ordered `memory_item_ids`
- timestamps for debugging if useful

Preferred direction is a dedicated structured record because this is session
state, not incidental logging.

### Completion note

Do not rely on prompt wording alone for batch completion. Compute completion in
code and inject an explicit teacher-facing note such as:

- current learning batch completed
- acknowledge progress
- move to a new batch

The exact text can be refined during implementation, but the signal should be
backend-generated and deterministic.

### Drift policy

If a stored id no longer resolves:

- log which id drifted
- continue with the remaining frozen ids when the batch is still viable
- avoid silently swapping one target topic for another in the middle of the
  session
- only reseed when the whole batch has completed or the remaining batch is no
  longer usable (in this case we need to send a completion note to teacher and
  the teacher must have an instruction on how to react to it in the chat
  (Example: "it seems we have learned all current grammar topics I'll select a new portion if you wish"))

## Validation Plan

During implementation, start with targeted backend tests around the session
focus service and the manager seam that injects starter memory. Before closing
the work item, run the broader repo gate required by project instructions.
