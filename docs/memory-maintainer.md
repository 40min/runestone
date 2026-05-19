# Memory Maintainer

`memory_maintainer` is an internal background specialist that performs routine
memory cleanup when a student starts a new chat session.

It exists to keep long-lived learner memory usable without adding latency to the
student-facing reset flow.

## Runtime Flow

The trigger is `DELETE /api/chat/history`, handled by
`ChatService.start_new_chat()`.

At reset time:

1. `ChatService` rotates the user's `current_chat_id`.
2. `ChatService` loads the `User`.
3. `AgentsManager.start_background_memory_maintenance(user)` schedules the
   maintainer task.
4. The reset endpoint returns immediately.

The maintenance task is fire-and-forget. New chat startup does not wait for the
agent to finish, and students can begin the next session using the memory state
that existed before the background cleanup completed.

## Duplicate Run Guard

`AgentsManager` keeps an in-memory per-user maintenance registry.

If a maintenance task is already running for `user.id`, another reset for the
same user does not schedule a second maintainer run. This is intentionally
process-local and is acceptable for the current single-process deployment.

If the backend later runs multiple worker processes or instances, this guard
should move to a shared store or durable job system.

## Scope

The maintainer only works on:

- category: `area_to_improve`
- statuses: `struggling`, `improving`

It should not inspect or rewrite unrelated memory categories, and it should not
merge across statuses. The scope is enforced both in the prompt and in the
maintainer-specific tools.

## Responsibilities

The maintainer owns broad start-of-session cleanup:

- conservatively consolidate obvious duplicate or overlapping weaknesses
- preserve meaningful sub-cases and examples during consolidation
- keep separate items when different contexts still carry instructional value
- conservatively adjust priority when an item is recurring or YKI-critical
- return structured JSON describing what happened
- log the structured maintenance result at info level

No action is a valid successful outcome when memory is already clear.

## Tool Flow

The specialist uses dedicated tools from
`src/runestone/agents/tools/memory_maintainer.py`:

- `maintainer_read_memory`
- `maintainer_insert_memory_item`
- `maintainer_delete_memory_item`
- `maintainer_update_memory_priority`

These tools are narrower than the normal memory tools. They reject out-of-scope
categories/statuses and protect the sequential merge flow.

For a consolidation, the agent must:

1. Read in-scope memory.
2. Insert a new consolidated item with a new versioned key and
   `replaced_item_ids` containing all original ids.
3. Delete only the original ids listed in that active replacement set.
4. Finish deleting the active replacement set before starting another merge.

The delete tool refuses to delete the newly created consolidated item and refuses
deletes outside the active replacement set. Pending merge state is cleared at the
start and end of each specialist run so failed or timed-out runs do not leave the
next run blocked by stale state.

## Persistence And Atomicity

The maintainer uses normal agent tool calls, not a single database transaction.
This preserves the same operational model as other specialists, but it means a
consolidation can be temporarily half-complete if the run is interrupted after
insert and before all deletes finish.

The next maintenance run can clean up that overlap. The tools reduce accidental
damage by constraining deletes to the active replacement plan.

## Output And Logging

`MemoryMaintainerSpecialist` expects the final agent message to be valid JSON
matching `SpecialistResult` conventions:

- `status`: `no_action`, `action_taken`, or `error`
- `actions`: tool action summaries
- `artifacts`: maintenance metadata, reviewed count, merge groups, priority
  updates, summary, and no-change reason

Fenced JSON is accepted. Invalid output or agent execution failure becomes a
structured `error` result.

`AgentsManager` logs successful completion and failures. Maintainer results are
not written to `agent_side_effects`; logging is the only persistence surface for
this maintenance run.

## Ownership Boundary

`memory_maintainer` and `MemoryKeeper` intentionally solve different problems.

`memory_maintainer` runs at chat reset and owns broad cleanup across existing
in-scope weakness memory.

`MemoryKeeper` runs from normal conversation flow and owns per-turn durable
memory updates based on the current student message, final teacher response, or
explicit student memory-edit request.

`WordKeeper` remains vocabulary-specific and does not participate in memory
consolidation.
