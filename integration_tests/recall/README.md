# Recall integration workflow

This directory contains a one-off, database-aware recall verification utility.
It is intentionally outside `tests/`, is not collected by pytest, and is never
run by normal readiness checks.

The utility uses the configured PostgreSQL database and user ID `5` by default.
It temporarily replaces that user's recall queue, account activation, and
Telegram link; creates uniquely prefixed fixture vocabulary; runs selected
workflows through the real services; reads the database directly after each
workflow; and restores the original state in a `finally` block.

It does **not** contact Telegram or an LLM. Outbound messages, deliveries,
polling batches, and update offsets are recorded in memory. The sole filesystem
offset exercise uses a temporary directory; the configured offset file is only
fingerprinted before and after the run.

The complete A01-N05 coverage declaration is machine-readable in
`coverage_manifest.json`. It maps all 83 plan scenarios. A01 remains explicitly
excluded because migration behavior is outside the deployed-consumer contract;
all consumer scenarios map to a harness group or a named focused pytest surface.
Grouped does not mean a dedicated test function per plan row; it identifies the
executable case that contains that scenario's assertions.

## Prerequisites

- PostgreSQL is running and `DATABASE_URL` points to the intended local database.
- Alembic migrations are at the current head.
- User ID `5` exists.
- No backend, recall worker, or other process is concurrently mutating user `5`.
- You have reviewed the current user-5 recall state and accept temporary changes.

The script refuses non-PostgreSQL databases. It takes a session-level PostgreSQL
advisory lock on a dedicated pinned connection for the whole run and verifies
that unlocking on that same connection returns true. The lock cannot prevent
ordinary application traffic that does not cooperate with it.

Candidate selection is intentionally isolated by a test-only
`FixtureCandidateVocabularyService`. It delegates production lookup, mutation,
cooldown, priority, and transaction behavior, but adds every non-fixture
vocabulary ID to selection exclusions. A full fingerprint of all non-fixture
user-5 vocabulary and all other users' recall rows proves isolation at cleanup.
Command processing uses a fixture-aware transaction provider that opens a fresh
PostgreSQL session per relevant update. Scheduled delivery uses a separate
session-only provider for enumeration and each user operation so its production
callback-spanning transaction contract remains intact.

## Invocation

Preview the CLI without permitting mutation:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python integration_tests/recall/run_recall_workflow.py --help
```

Print the complete A01-N05 mapping without database access:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python integration_tests/recall/run_recall_workflow.py --show-coverage
```

Run every scenario against local user `5`:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python integration_tests/recall/run_recall_workflow.py \
  --apply --user-id 5 --confirm-user-id 5 \
  --confirm-host localhost --confirm-database runestone
```

Replace `localhost` and `runestone` with the host and database name shown by
your configured `DATABASE_URL`. For a Unix-socket URL, confirm host `local`.

Run selected scenarios:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python integration_tests/recall/run_recall_workflow.py \
  --apply --user-id 5 --confirm-user-id 5 \
  --confirm-host localhost --confirm-database runestone \
  --case normal-delivery --case commands \
  --report-file /tmp/recall-report.json
```

Available executable groups:

- `selection-pools`: missing-state reads, short/empty candidate pools, cooldown,
  inactivity, and deterministic priority filtering.
- `normal-delivery`: accepted delivery, learning metadata, cursor advance, and
  scheduled enumeration/user session isolation. A synthetic duplicate target
  DTO safely proves a real failed PostgreSQL user session cannot poison the
  later fresh session, and the send callback observes the open row-lock transaction.
- `delivery-edge`: disabled/null-chat delivery and one/all-invalid queued rows.
- `hard-delete`: endpoint-equivalent cross-service deletion, FK cleanup, cursor,
  queue compaction, and refill.
- `hard-delete-edge`: not-queued, no-state, missing, foreign-user, rollback, and
  before/at/after-cursor deletion.
- `commands`: `/start`, `/state`, `/postpone`, `/bump_words`, `/remove`, `/stop`,
  plus polling-offset persistence. It also documents the current behavior that
  `/help` and `/status` are unsupported no-ops.
- `commands-edge`: username normalization, authorization variants, malformed or
  missing updates, unparsable replies, and unknown/absent words.
- `postpone-bump`: cursor positions, no-alternative self-refill, alternative
  refill, absent soft remove, and full/short/empty bump pools.
- `eligibility`: active/enabled, disabled, and inactive delivery eligibility.
- `offset-recovery`: temporary offset parsing, a real first-update PostgreSQL
  failure retaining its offset and stopping the batch, fresh-session retry of
  that update and the later suffix, provider closure before outbound send, and
  synthetic offset-write failure.
- `concurrency`: two deliveries, deactivation race, concurrent start, and
  concurrent deletion/refill using independent sessions and bounded timeouts.
- `isolation`: ordered Teacher reads and cross-user ownership protection.
- `rollback`: rejected delivery, missing queue membership, and a synthetic
  transport exception plus caller-owned rollback, with exact DB comparison.
- `lifecycle`: changed chat-ID refresh, stop/start state retention, profile
  username relink, and stop when no recall row exists.
- `vocabulary-context`: queued phrase/translation/example edits reflected in
  delivery and Teacher reads, context after postpone/remove, and reactivation
  without current-queue churn.
- `worker-lifecycle`: update-ID ordering, contiguous-prefix acknowledgment,
  duplicate idempotent command replay, and persisted-offset restart behavior.
- `delivery-races`: delivery serialized with start/stop, bump, postpone,
  Telegram remove, and endpoint-equivalent web soft/hard delete in independent
  sessions.

Focused pytest coverage complements the PostgreSQL harness for clock and HTTP
adapter partitions: `tests/telegram/test_delivery.py`,
`tests/telegram/test_commands.py`, and
`tests/services/test_chat_service.py`, plus Teacher prompt-safety coverage in
`tests/agents/test_teacher.py`. No real Telegram or LLM request is made.

Each case prints PASS/FAIL followed by direct database evidence. Every run also
retains a mode-`0600` JSON report under `/tmp` by default. It contains database
identity, configuration, the coverage manifest, per-case tracebacks and
before/after evidence, lock outcome, initial fingerprints, and final restoration
proof. A non-zero exit status means a case, setup, lock, or cleanup failed.

Four regression assertions cover the final review findings: repeated `/start`
must preserve its already-enabled response, a postponed word must not be selected
as its own immediate refill, and delivery must recheck account activation after
acquiring the recall-state lock. A real PostgreSQL statement failure in one
Telegram update must retain that update's offset, stop the current batch, and
then succeed in a fresh session before later fetched updates are processed.
These scenarios are expected to pass; any regression produces a normal failed
case while the runner still restores the database.

## Safety and interrupted runs

Only vocabulary whose phrase starts with the run-specific
`__recall_it_<random>_` prefix is created or deleted. Existing vocabulary is not
selected, deleted, or rewritten. The original queue may reference existing
vocabulary, so the utility snapshots and restores its row IDs, ordered vocabulary
IDs, positions, and timestamps exactly. User activation, Telegram username,
current chat ID, user timestamp, recall linkage, enablement, cursor, and recall
timestamps are also restored exactly.

Before the first mutation, a mode-`0600` recovery snapshot is written to:

```text
/tmp/runestone-recall-integration-user-5.json
```

It is removed only after restoration has been verified. If the process is killed
in a way that prevents `finally` cleanup, the next run refuses to start while
this file exists. Preserve that file and restore the recorded user and recall
state before removing it. A normal assertion failure or Ctrl-C still enters the
restoration path.

The recovery file includes database host/name/server identity, the complete
target user/recall snapshot, the fixture prefix, configured offset-file snapshot,
and both isolation fingerprints. A retained scenario report is separate and is
not removed after success.

As with ordinary insert/delete testing, PostgreSQL sequence counters can advance
even though the logical user, recall-state, queue-row identities/timestamps, and
vocabulary contents are restored.
