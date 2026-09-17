# Sanitized Better Stack database boundary telemetry

Task: add failure-only, sanitized telemetry at the two database boundaries —
application startup verification and the Recall API's outer request-owned
transaction — without weakening the reviewed default-deny breadcrumb contract.

1. (done) Add `record_database_boundary_failure(operation, exception,
   started_at)` in `src/runestone/db/database.py`. It emits one marked ERROR
   record (fixed operation, `failed` outcome, duration bucket) and captures
   the exception via `capture_sanitized_exception`. Both steps are best-effort:
   a diagnostics failure can never change the startup or transaction outcome.
2. (done) Keep the marker free of failure classification: the companion
   captured event already carries the exception type and stack frames, so a
   coarser type-based category adds no information and only invites
   misclassification.
3. (done) Wire `setup_database` to record `database_startup_check` failures
   and re-raise, keeping the local `exc_info` traceback so failures are
   diagnosable without a configured DSN.
4. (done) Wire the Recall API `_run_mutation` rollback paths to record
   `recall_transaction` failures after rollback, before raising the generic
   HTTPException.
5. (done) Tests: sanitized marker export against the real SDK, non-fatal
   diagnostics, boundary wiring for startup and recall endpoints.

Deliberately out of scope: success markers, retry counts, failure categories,
and any marker field derived from exception text, SQL, or user data.
