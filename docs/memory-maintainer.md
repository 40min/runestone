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

It does not inspect or rewrite unrelated memory categories.

## Structured Multi-Pass Flow

The maintainer no longer uses a tool-calling agent. Instead it runs a
deterministic structured-output pipeline and executes the resulting plan in
plain Python.

### Step 1: Topic bucketing

The first LLM pass reads the in-scope items and groups them into broad candidate
buckets of related grammar topics.

Rules:

- every in-scope item must appear in exactly one bucket
- buckets may be broad enough to hold close subtopics
- unrelated issues must stay in separate buckets
- each bucket includes a `why` explanation for validation

### Step 2: Bucket review and merge generation

The second phase is intentionally split into smaller decisions so the model does
not jump directly from a broad bucket to a rewritten merged item.

Step 2a reviews one bucket and partitions it into exact same-topic groups.
Singleton groups are left untouched. Multi-item groups continue to merge
generation only if the bucket review says they are one teachable topic.

Step 2b generates the merged key/content for one reviewed multi-item group.

Step 2c validates that generated merge proposal in a separate pass. This is a
conservative quality gate that rejects umbrella merges even when the generation
step produced fluent output.

Rules:

- every bucket item must appear in exactly one final group
- multi-item groups are allowed only for near-duplicate or truly overlapping
  topics
- related but distinct topics must be split into separate final groups
- if near-duplicate items changed status over time, the latest status wins
- merged content is freshly rewritten in `User.mother_tongue` when possible,
  otherwise English
- merged keys are always fresh English versioned keys
- bucket review, merge generation, and merge validation each include
  validation-only `why` explanations
- a generated merge is rejected if the validator judges it broader than one
  exact teachable topic

### Step 3: Optional CLI priority review

The third LLM pass is CLI-only and runs only when
`--with-priority-review` is enabled.

It suggests final priorities based on:

1. general YKI importance
2. visible friction from how many source items were merged

Priority review is not part of the background chat-reset flow.

## Execution Model

V1 persistence is merge-only for background maintenance:

- only final groups with 2+ source items are written
- singleton groups are validation/reporting only
- no standalone content or status rewrites happen outside merges

Each merge group is executed independently:

1. re-read the current source items
2. validate user and scope, then normalize final status to the latest source
   status
3. create the merged item with create-only semantics
4. delete the replaced source items

This is intentionally partial, not all-or-nothing. If one group fails because
of source drift or a duplicate target key, later groups still run.

The bucketing phase also has a deterministic repair layer before step 2 begins:

- first assignment wins when the model duplicates an item across buckets
- unknown ids are dropped
- missing ids are reintroduced as singleton buckets
- missing `why` values for multi-item buckets are synthesized for validation

This keeps the flow moving when the model is slightly sloppy, while still
avoiding unsafe writes.

## CLI Mode

The maintainer can be run manually:

```bash
runestone maintain-memory USER_ID --dry-run
runestone maintain-memory USER_ID --with-priority-review
runestone maintain-memory USER_ID --dry-run --with-priority-review
```

CLI output always includes:

- a readable maintenance summary
- the full structured JSON artifact for validation

`--dry-run` performs planning and validation without writing changes.

`--with-priority-review` enables the optional third step. In dry-run it reports
priority suggestions only. In apply mode it writes priority changes after merge
execution.

## Output And Logging

`MemoryMaintainerSpecialist` still returns `SpecialistResult`, but its
`artifacts` payload is richer than before. It includes:

- reviewed item count
- candidate buckets
- final maintenance groups
- accepted and failed merge groups
- created and deleted ids
- optional priority suggestions or applied priority updates
- validation-only `why` fields
- step errors and summary text

`AgentsManager` logs successful completion and failures. Maintainer results are
not written to `agent_side_effects`; logging remains the persistence surface for
background runs.

## Ownership Boundary

`memory_maintainer` and `MemoryKeeper` intentionally solve different problems.

`memory_maintainer` runs at chat reset and owns broad cleanup across existing
in-scope weakness memory.

`MemoryKeeper` runs from normal conversation flow and owns per-turn durable
memory updates based on the current student message, final teacher response, or
explicit student memory-edit request.

`WordKeeper` remains vocabulary-specific and does not participate in memory
consolidation.
