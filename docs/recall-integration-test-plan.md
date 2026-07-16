# Recall Integration Test Plan

This plan verifies the recall feature against a local PostgreSQL database. It covers the Telegram command surface, scheduled delivery, vocabulary mutations, queue and cursor invariants, transaction rollback, eligibility, concurrency, and the remaining file-backed Telegram update offset.

The one-off executable harness lives outside the normal `tests/` suite under `integration_tests/recall/`. Its default target is local user ID `5`.

The executable coverage mapping is maintained in `integration_tests/recall/coverage_manifest.json`. It maps 83 scenario IDs: the original A01-I02 engineering/baseline matrix plus the deployed-consumer J01-N05 matrix. A01 is retained as an explicitly excluded migration check. Consumer scheduler boundaries run as deterministic production-adapter tests, while PostgreSQL lifecycle, vocabulary/context, worker restart, and cross-surface race cases run in the guarded harness.

Inspect the mapping without database access:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python \
  integration_tests/recall/run_recall_workflow.py --show-coverage
```

The guarded live invocation and recovery procedure are documented in `integration_tests/recall/README.md`. A live run is a separate deliberate action and must not be inferred from creating or validating the harness.

## Goals

- Exercise real repositories and services over PostgreSQL rather than mocked persistence.
- Inspect database state after every action, not only returned DTOs or Telegram text.
- Verify that vocabulary, recall state, queue rows, and cursor changes are committed atomically.
- Record enough before/action/after evidence to diagnose a failed invariant.
- Avoid network calls and preserve all pre-existing data belonging to user `5`.

## Consumer-facing coverage contract

This plan assumes the recall migration has already been applied successfully. Migration ordering,
schema creation, SQL query counts, session identity, and harness cleanup are supporting engineering
checks rather than consumer-facing recall behavior. They may be validated separately, but they do
not define the deployed feature's behavioral coverage.

Consumer-facing coverage is complete only when every supported interaction below is exercised
against PostgreSQL through its production application boundary. For each interaction, cover every
meaningfully different starting state that can be produced through supported behavior:

- account: active or inactive;
- profile linkage: missing Telegram username, matching username, changed username, or conflicting
  username where the public profile API permits the attempt;
- recall state: absent, disabled, or enabled, including a refreshed Telegram chat ID;
- queue: absent/empty, shorter than target, full, cursor at the first/middle/last item, or containing
  an item that became ineligible through a supported vocabulary mutation;
- candidate pool: enough alternatives, fewer than the target, one eligible word, or none;
- transport outcome: accepted, rejected, timed out, or errored;
- concurrency: the same interaction serialized against another delivery or supported mutation.

The finite consumer interaction inventory is:

### 1. Profile linking and recall lifecycle

- First `/start` links an active Runestone profile, enables recall, and stores the current Telegram
  chat ID without selecting or sending a word prematurely.
- Repeated `/start` is idempotent, preserves queue/cursor, and refreshes a changed chat ID.
- `/start` after `/stop` re-enables the existing state without losing its queue or cursor.
- `/start` handles case and leading-`@` normalization, a missing Telegram username, an unlinked
  username, an inactive account, and a username conflict with the documented response and no
  unintended state.
- Changing the profile Telegram username makes the old username unauthorized and lets the new
  username operate the same existing user recall state after `/start`; a conflicting profile update
  is rejected without changing the existing link.
- `/stop` works for enabled, already-disabled, and active linked users with no persisted recall row;
  it disables delivery without deactivating the account or discarding the queue.
- Account deactivation stops commands and delivery immediately. Reactivation plus `/start` restores
  supported use without duplicating state.

### 2. Telegram command surface

- `/state` reports enabled and disabled states, empty/short/full queues, persisted queue order, and
  words containing Markdown-significant or Unicode characters without mutating state.
- `/bump_words` replaces the current queue and resets the cursor when enough, few, or no alternative
  candidates exist; it also handles an initially empty queue and reports the resulting count/empty
  state accurately.
- `/remove`, used as a reply to a delivered word, soft-deactivates a queued or non-queued owned word,
  removes any queue membership, repairs the cursor, and refills when possible.
- `/postpone`, used as a reply to a delivered word, keeps the vocabulary active, lowers its urgency,
  removes it from the current queue, repairs the cursor, excludes it from immediate refill, and
  refills when possible.
- `/remove` and `/postpone` cover no reply, empty/malformed reply, supported Markdown variants,
  leading underscores, an unknown word, and a known word outside the current queue.
- Every mutating command covers success plus a database failure: the user receives the documented
  outcome, no partial mutation remains, and the following update in the same fetched batch can run.
- Unknown commands, ordinary text, edited/channel/non-message updates, and messages missing a
  username or chat ID produce no recall mutation or unintended reply.

### 3. Scheduled delivery and Telegram presentation

- A job inside the configured delivery window processes every eligible user; a job before the start,
  exactly at the start, just before the end, and exactly at/after the end follows the configured
  inclusive/exclusive boundaries in the deployment timezone.
- State absent, disabled state, missing chat ID, inactive account, or an empty candidate pool sends
  nothing and leaves learning metadata/cursor unchanged.
- An empty queue is filled from eligible vocabulary; enough, few, one, and zero candidates produce a
  full, short, single-item, or empty queue without duplicates.
- Accepted delivery uses the cursor-selected item, renders word/translation/optional example safely
  in Telegram MarkdownV2, increments learning metadata once, and advances/wraps the cursor once.
- Telegram rejection, HTTP 4xx/5xx, timeout, malformed response, or transport exception does not
  advance learning metadata or the cursor and does not prevent later users from being processed.
- A queued item made ineligible through a supported action is skipped/removed, the queue is repaired
  and refilled, and only a currently learnable owned word can be sent; an entirely invalid queue
  terminates within the retry bound.
- Multiple active users receive only their own words and chat IDs in deterministic processing order;
  one user's empty queue or failure does not affect another user.
- Two overlapping delivery jobs for one user do not send the same cursor item twice after successful
  commits. The documented accepted-send/process-crash-before-commit window remains a known external
  side-effect limitation rather than a promise of exactly-once delivery.

### 4. Vocabulary interactions from Runestone

- Creating or reactivating an eligible vocabulary item does not rewrite the current queue, but makes
  it available to the next fill, refill, or bump according to selection rules.
- Editing the phrase, translation, or example of a queued item is reflected by `/state`, Teacher
  context, and the next Telegram delivery; queue membership and cursor stay unchanged.
- Changing priority affects future selection without silently reordering the persisted current queue.
- Setting `in_learn=false` for queued items at every cursor-relative position compacts/refills the
  queue atomically; doing so for a non-queued item leaves queue/cursor unchanged.
- Hard-deleting queued items at every cursor-relative position compacts/refills atomically; deleting
  a non-queued item or deleting when no recall state exists succeeds without creating recall state.
- Not-found, duplicate-update, ownership violation, and refill failure responses leave both
  vocabulary and recall state unchanged.
- Telegram `/remove`, web soft deletion, and web hard deletion produce consistent eligibility and
  queue outcomes for the same vocabulary item.

### 5. Runestone chat and Teacher context

- Text and image/OCR chat turns receive the current queue phrases in persisted order, including after
  delivery, bump, postpone, remove, edit, soft deletion, and hard deletion.
- No recall state or an empty queue supplies no recall context and does not create state.
- Disabled recall retains its persisted queue as Teacher reinforcement context; account/ownership
  isolation prevents another user's words from appearing.
- Recall-context read failure is best effort: the chat turn still succeeds with empty recall context
  and does not roll back unrelated request work.
- Empty, multiline, very long, Unicode, and instruction-like vocabulary text is normalized, bounded,
  and treated as untrusted data before prompt injection.

### 6. Telegram polling, retries, and worker lifecycle

- Missing/empty/valid/malformed offset state has the documented behavior without changing recall
  state; fetched updates are processed in a deterministic policy regardless of response ordering.
- Duplicate update delivery after an offset-write failure is safe for every command: idempotent
  commands remain idempotent. Replayed non-idempotent commands may produce a second valid outcome;
  exactly-once command effects require a separate durable processed-update design and are not
  promised by the current file offset. Every replay must still preserve aggregate invariants.
- One malformed update, database-aborting update, or user-specific failure cannot poison later
  updates in the same batch; offset advancement must not silently discard a failed update contrary
  to the chosen retry policy.
- Polling network/API/JSON failures preserve the previous offset and recover on the next job.
- Worker restart with persisted database state and offset resumes commands and delivery without
  recreating, clearing, or duplicating recall state.

### 7. Cross-surface races

- Delivery is serialized independently against `/stop`, `/start`, `/bump_words`, `/postpone`,
  Telegram `/remove`, web soft deletion, and web hard deletion. Account activity is rechecked after
  the aggregate lock. A profile username change is authorization linkage keyed to the same user ID,
  not a recall aggregate mutation; lifecycle tests prove the old username loses access and the new
  username operates the existing state.
- Concurrent duplicate commands and concurrent Telegram/web mutations settle on one valid outcome:
  queue positions remain contiguous and unique, cursor remains valid, vocabulary eligibility agrees
  with membership, and no cross-user mutation occurs.

Every inventory item must map to at least one executable scenario before this plan is described as
consumer-complete. Equivalent internal branches may share a scenario when they have the same
observable input, output, and persisted outcome; implementation-only branches need no separate
scenario.

## Safety And Execution Contract

The harness must not run unless all of these conditions are satisfied:

1. The database URL uses PostgreSQL.
2. The operator passes the explicit mutation flag documented by the harness, such as `--apply`.
3. User `5` exists.
4. The operator confirms the displayed database host, database name, and target user.

The harness creates vocabulary fixtures with a unique run prefix such as `__recall_it_<run-id>_`. It may snapshot and temporarily replace user `5`'s recall state and queue, but it must never modify unrelated vocabulary. In a `finally` block it removes its fixture rows and restores the original recall state, queue order, cursor, enablement, chat ID, affected user fields, and offset-file content.

Outbound Telegram calls and LLM calls are replaced with deterministic recorders. Direct database reads are used only for setup, evidence, assertions, and restoration; actions under test go through the production service or endpoint boundary.

Before running the scenarios, record:

- user `5`: `active`, `telegram_username`, and current chat ID;
- `recall_user_states`: presence, `is_enabled`, `telegram_chat_id`, and `next_word_index`;
- ordered `recall_queue_items` joined to `vocabulary`;
- all fixture vocabulary fields;
- Telegram offset-file presence and content;
- configured `WORDS_PER_DAY`, cooldown, and recall delivery window.

## Invariants Checked After Every Mutating Scenario

Use these common assertions unless a scenario explicitly expects otherwise:

- At most one `recall_user_states` row exists for user `5`.
- Queue positions are exactly `0..n-1`, with no gaps or duplicates.
- Each vocabulary item appears at most once in the queue.
- Every queue item belongs to user `5` and references an existing vocabulary row.
- `next_word_index` is `0` for an empty queue; otherwise `0 <= next_word_index < queue_length`.
- Every queued vocabulary row has `in_learn = true`.
- A committed action is visible from a new database session.
- A failed action leaves the database equal to its scenario snapshot.
- No scenario changes non-fixture vocabulary or another user's recall state.

## Fixture Set

Create at least `2 * WORDS_PER_DAY + 3` learnable fixture words so replacement and exclusion behavior can be proved. Include:

- high-, default-, and low-priority words;
- words never learned;
- a word learned within the cooldown period;
- a word learned before the cooldown cutoff;
- one inactive (`in_learn = false`) word;
- complete and nullable example text variants.

Keep the fixture IDs and expected selection eligibility in the run report.

## Scenario Matrix

### A. Setup, schema, and selection

| ID | Action | Database assertions |
| --- | --- | --- |
| A01 | Verify migration/schema prerequisites. | Both recall tables and all named PK/FK/check/unique constraints exist; Alembic is at the expected head. |
| A02 | Load state for a user without a recall row. | Read returns no persisted row; no row is created by a read. |
| A03 | Enable recall for active user `5`. | One state row exists, `is_enabled = true`, supplied chat ID is stored, cursor is `0`; repeated enable updates rather than duplicates the row. |
| A04 | Deliver with an empty queue and enough eligible vocabulary. | Queue is created with up to `WORDS_PER_DAY` eligible unique items at contiguous positions; cursor advances only after the accepted send. |
| A05 | Select with fewer eligible words than the target. | Queue contains every eligible item once and remains shorter than the configured target without failure. |
| A06 | Select with no eligible words. | Queue stays empty, cursor remains `0`, no learning metadata changes, and no message is recorded. |
| A07 | Validate selection filters. | Inactive and cooldown-blocked words are absent; priority/candidate rules match repository semantics. |

### B. Normal scheduled delivery

| ID | Action | Database assertions |
| --- | --- | --- |
| B01 | Accept delivery of the item at cursor `0`. | Exactly that word's `learned_times` increments once, `last_learned` advances, and cursor advances in the same commit. |
| B02 | Deliver through the complete queue. | Messages follow queue order and cursor wraps from the last position to `0`. |
| B03 | Recorder returns `false`. | Cursor and learning fields do not change; transaction is rolled back. |
| B04 | Recorder raises an exception. | Cursor, queue, and learning fields remain unchanged and the service reports a recall operation failure. |
| B05 | State is disabled or chat ID is null. | No send occurs and no database mutation is committed. |
| B06 | User account is inactive. | User is absent from active-state enumeration and no delivery occurs. Recheck the race case in G03. |
| B07 | Current queued word becomes inactive before delivery. | Invalid item is removed, positions/cursor are repaired, queue is refilled if possible, and only a valid item may be sent. |
| B08 | All queued words become invalid. | Invalid entries are removed without looping indefinitely; replacement is attempted only up to the configured retry limit. |
| B09 | Delivery worker runs outside the configured window. | No state, queue, vocabulary, or message changes. |

### C. Telegram commands

Build Telegram update dictionaries with realistic command entities and record outbound messages. After every command, reload state from a new session.

| ID | Command | Database and behavior assertions |
| --- | --- | --- |
| C01 | `/start` for an active profile with matching username. | State is upserted/enabled, current chat ID is stored, and a success message is recorded. |
| C02 | Repeated `/start`. | No duplicate state or queue rows; chat linkage is refreshed and the agreed already-enabled response is preserved. |
| C03 | `/start` with case or `@` variation. | Username normalization resolves the same user and stores no duplicate state. |
| C04 | `/start` for missing, malformed, inactive, or duplicate profile linkage. | No enabled state is created; the appropriate authorization/conflict message is recorded. |
| C05 | `/stop`. | `is_enabled = false`; chat linkage and queue remain intact; account `users.active` is unchanged. |
| C06 | `/state`. | No database mutation; response matches persisted enablement, ordered queue, and empty-queue wording. |
| C07 | Unknown command, non-command text, update without message, username, or chat ID. | No database mutation and no unintended reply. |
| C08 | `/remove` or `/postpone` without a reply. | No database mutation; guidance message is recorded. |
| C09 | `/remove` or `/postpone` with an unparsable reply. | No database mutation; parsing-error message is recorded. |
| C10 | `/remove` for an unknown word. | No queue or vocabulary change; not-found response is recorded. |
| C11 | `/postpone` for a known word not in the queue. | No vocabulary priority or queue change; not-in-selection response is recorded. |

### D. Postpone, soft remove, bump, and refill

| ID | Action | Database assertions |
| --- | --- | --- |
| D01 | Postpone the item before the cursor. | Item is absent from the resulting queue, priority moves one step toward low urgency within bounds, positions compact, and cursor decreases so the same logical next item remains selected. |
| D02 | Postpone the item at the cursor or after it. | Item is absent, positions compact, and cursor still identifies the correct logical next item. |
| D03 | Postpone the last/only queue item. | Postponed ID is excluded from immediate refill, including the single-eligible-word case; empty queue implies cursor `0`. |
| D04 | Postpone when alternatives exist. | Queue refills toward `WORDS_PER_DAY` with unique eligible alternatives and never immediately re-adds the postponed ID. |
| D05 | `/remove` a queued word. | Vocabulary remains present but becomes `in_learn = false` with low priority; queue removes it, compacts, repairs cursor, and refills with an eligible alternative. |
| D06 | `/remove` a vocabulary word absent from the queue. | Vocabulary is deactivated; unrelated queue and cursor remain unchanged. |
| D07 | `/bump_words` with enough alternatives. | Complete queue is replaced, prior queue IDs are excluded when alternatives suffice, positions restart at `0`, and cursor resets to `0`. |
| D08 | `/bump_words` with insufficient alternatives. | Fallback selection fills as far as possible without duplicate queue IDs; resulting cursor is `0`. |
| D09 | `/bump_words` with no eligible words. | Queue becomes empty and cursor is `0`; command reports that no words are available. |

### E. Hard deletion through the API application boundary

| ID | Action | Database assertions |
| --- | --- | --- |
| E01 | Delete a queued fixture word owned by user `5`. | Vocabulary row and queue reference disappear atomically; positions/cursor are repaired; queue refills without the deleted ID. |
| E02 | Delete a fixture word not in the queue. | Vocabulary row disappears; queue and cursor remain unchanged. |
| E03 | Delete with no recall state. | Vocabulary deletion succeeds without creating recall state. |
| E04 | Delete a missing or another user's item. | Endpoint returns not found and any speculative queue mutation is rolled back. |
| E05 | Force failure during refill after queue removal and deletion. | Vocabulary, queue, positions, and cursor all roll back to the pre-action snapshot. |
| E06 | Delete words before, at, and after the cursor. | Cursor follows the documented logical-next-item rules in every position case. |

### F. Telegram offset and batch recovery

| ID | Action | Assertions |
| --- | --- | --- |
| F01 | No offset file, empty result, malformed content. | Missing defaults to `0`; malformed input is handled as documented without touching the database. |
| F02 | Process ordered update IDs successfully. | Offset advances through the highest contiguous handled update only. |
| F03 | First update causes a real PostgreSQL statement failure; a later valid command follows in the same fetched batch. | The failing update rolls back, no command response is sent, later fetched updates are not processed, and the offset remains at the failing update. |
| F04 | Poll again after removing the injected database failure. | The failed update is retried with a fresh session, later updates then process in order, and the contiguous offset advances through them. |
| F05 | Inspect the command transaction while its outgoing Telegram message is recorded. | Commit and provider closure complete before outbound HTTP begins. |
| F06 | Fail Telegram send after a successful command commit. | The failure is logged and the offset advances because application work has already committed. |
| F07 | Offset-file write fails after command handling. | Database outcome and replay behavior are reported explicitly; original fixture offset file is restored at cleanup. |
| F08 | Application and commit succeed, but closing the command session raises. | Cleanup failure is logged without suppressing the prepared response or retaining the offset for replay. |

### G. Concurrency and eligibility races

Use two independent `AsyncSession` instances and bounded timeouts so a failed locking assertion cannot hang the run.

| ID | Race | Assertions |
| --- | --- | --- |
| G01 | Two workers deliver the same user concurrently. | Row locking serializes them; they do not send the same cursor item twice under normal successful commits. |
| G02 | Delivery races with postpone, remove, bump, or hard delete. | Operations serialize; final queue constraints hold and every committed vocabulary mutation agrees with queue membership. |
| G03 | User is deactivated after active-state enumeration but before locked delivery. | Delivery revalidates account activity and records no message. |
| G04 | `/start` runs concurrently twice. | Upsert produces one state row with valid linkage and no unique violation exposed to the caller. |
| G05 | Queue refill runs concurrently with deletion. | Deleted ID cannot reappear; queue remains unique and contiguous. |

### H. Read consumers and isolation

| ID | Action | Assertions |
| --- | --- | --- |
| H01 | Load Teacher recall words. | Ordered phrases exactly match persisted queue order and the read uses the caller's request-scoped session. |
| H02 | Read active recall states for several fixtures/users where feasible. | Only `users.active = true`, `is_enabled = true` states are returned, with queues attached in deterministic order and without per-user queue queries. |
| H03 | Attempt operations with a vocabulary ID belonging to another user. | No cross-user read or mutation succeeds. |

### I. Cleanup and restoration

| ID | Action | Assertions |
| --- | --- | --- |
| I01 | Normal successful cleanup. | All prefixed fixture vocabulary and related queue rows are gone; original state, queue, cursor, user fields, and offset content match the initial snapshot. |
| I02 | Inject a mid-scenario failure. | The `finally` cleanup still restores the snapshot and reports cleanup separately from scenario failure. |

### J. Deployed profile and recall lifecycle

| IDs | Consumer behavior | Executable boundary |
| --- | --- | --- |
| J01-J04 | Changed chat ID, stop/start retention, profile username rename, and stop with no recall row. | `lifecycle` PostgreSQL case. |
| J05-J06 | State partitions, authorization failures, malformed updates, and no-op input. | Existing `commands` and `commands-edge` cases. |

### K. Delivery adapter and multi-user behavior

| IDs | Consumer behavior | Executable boundary |
| --- | --- | --- |
| K01-K03 | Exact safe MarkdownV2 payload, all rejected transport outcomes, and later-user continuation with a fresh session per user. | Focused production-adapter pytest tests with deterministic HTTP and provider recorders. |
| K04-K05 | Accepted delivery transaction, eligibility partitions, and invalid queue repair. | Existing PostgreSQL delivery cases. |
| K06-K07 | No provider outside delivery hours; one short enumeration session followed by a fresh session for every active user. | Focused Telegram delivery provider-lifecycle tests. |

### L. Vocabulary and Teacher consumers

| IDs | Consumer behavior | Executable boundary |
| --- | --- | --- |
| L01-L05 | Queued text edits, reactivation stability, future priority selection, delete partitions, and Teacher context after mutations. | `vocabulary-context` plus existing PostgreSQL selection/delete cases. |
| L06 | Text/image chat forwarding and best-effort context failure, including a real PostgreSQL rollback followed by a usable reloaded user. | Focused ChatService tests with deterministic agent/OCR recorders. |

### M. Polling and restart policy

| IDs | Consumer behavior | Executable boundary |
| --- | --- | --- |
| M01-M04 | Update-ID ordering, retryable failure stop/retry, contiguous persisted offset, duplicate idempotent replay after offset-write failure, and database state after restart. | `worker-lifecycle`, `offset-recovery`, and focused Telegram command tests. |
| M05 | Network, API, JSON, and empty polling outcomes preserve offset. | Focused `TelegramCommandProcessor` tests. |

The worker processes updates by ascending ID and persists only the highest contiguous prefix considered
handled. A database or SQLAlchemy failure stops the batch and retains the failing update for a later poll;
the retry and every later update receive fresh sessions. Expected domain failures and unknown non-database
application failures follow their handled response policy and advance. Telegram send failure after commit
also advances, so exactly-once outbound delivery remains outside this design. If writing the offset itself
fails, Telegram may replay already committed commands; idempotent commands must remain safe under replay.

### N. Supported concurrency boundaries

| IDs | Consumer behavior | Executable boundary |
| --- | --- | --- |
| N01-N03 | Delivery against start/stop, bump, postpone, Telegram remove, and endpoint-equivalent web soft/hard delete. | `delivery-races` with independent PostgreSQL sessions and bounded lock waits. |
| N04-N05 | Account deactivation, concurrent start, ownership isolation, and username authorization relink. | Existing `concurrency`, `isolation`, and `lifecycle` cases. |

## Evidence Format

For each scenario, print and optionally write a machine-readable record containing:

- scenario ID and title;
- pass, fail, skip, or cleanup-failed status;
- action invoked and recorded Telegram outcome;
- before/after state row;
- ordered queue rows with `position`, `vocabulary_id`, and phrase;
- relevant vocabulary fields: `in_learn`, `priority_learn`, `last_learned`, and `learned_times`;
- transaction/session identifiers when testing races;
- concise assertion failure and traceback.

The final summary must distinguish product failures from harness/setup failures and return a non-zero exit status if any required scenario fails or cleanup cannot prove restoration.

## Recommended Execution Order

1. Run harness import, compile, and non-mutating preflight checks.
2. Run schema/setup scenarios.
3. Run deterministic single-session state transitions and command cases.
4. Run hard-delete and rollback cases.
5. Run delivery and offset cases with network recorders.
6. Run two-session concurrency cases separately.
7. Run cleanup and compare the complete restored snapshot.
8. After fixes stabilize, execute the normal repository readiness checks independently of this one-off harness.

## Exit Criteria

The current baseline harness passes when every mapped executable scenario passes on PostgreSQL, cleanup proves that user `5` was restored, and no unexpected network request occurs. Consumer-facing coverage passes only when every interaction in the consumer-facing coverage contract is mapped and passes, including scheduler boundaries and supported cross-surface races. Migration-chain verification, SQL query counts, and session-identity instrumentation are reported separately and do not block that consumer-facing result.
