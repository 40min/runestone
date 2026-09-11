# Richer Sanitized Better Stack Logging

## Plan control

- Dart task: [`kMMaU6ulmWQy` — Enable richer sanitized Better Stack logging](https://app.dartai.com/t/kMMaU6ulmWQy-Enable-richer-sanitized-Better)
- Repository baseline: `69cc42178d6eb8f445270f2318eeed37dc0f3a51` (`main`, clean before this plan)
- Risk tier: privacy-sensitive export-path expansion; requires independent privacy/security review and durable policy documentation. No other elevated process gates.
- State: `IN_PROGRESS` — the pre-freeze Dart re-read could not be performed by a repository agent (the Dart page requires login). The repository owner re-confirmed the task on 2026-09-11: status `Doing`, priority `Medium`, blocker `0YWS31901O3I` closed by `4b08c4a`, description and acceptance criteria unchanged from the 2026-09-08 snapshot. Implementation started on that confirmation; commit-bound privacy/security approval remains outstanding.
- Execution mode: standard, one cohesive backend implementation

This document is implementation authority only after review. It does not authorize deployment, Better Stack account changes, secret access, or sending production/user data.

The Dart page redirected to login during this planning run. Task scope and acceptance below come from the last verified Dart snapshot (2026-09-08). A live agent re-read was not possible (Dart requires login); the repository owner re-confirmed the task on 2026-09-11 (status `Doing`, priority `Medium`, blocker closed by `4b08c4a`, description and acceptance criteria unchanged), and implementation proceeded on that confirmation.

Last verified snapshot: task status `Doing`, priority `Medium`, sanitizer blocker `0YWS31901O3I`, and acceptance requiring useful sanitized breadcrumbs in captured events, representative secret/user-content exclusion, documented volume/quota impact, and privacy/security approval. The blocker was subsequently completed by `4b08c4a` and closed in Dart.

## Outcome

Add a small, explicitly marked trail of safe application warning/error breadcrumbs to Better Stack error events. Preserve the existing default-deny sanitizer, keep standalone log events and INFO breadcrumbs disabled, add internal request correlation, and prove the complete production path with the real Sentry SDK and synthetic sensitive sentinels.

## Current implementation

Already complete in commit `4b08c4a`:

- `src/runestone/core/error_tracking.py` rebuilds events and breadcrumbs from explicit allowlists and fails closed.
- Logging breadcrumbs are accepted only from `runestone` loggers at `WARNING`/`ERROR`/`CRITICAL` with a valid `runestone_telemetry` mapping.
- Original log messages, arguments, exception text, request bodies, query strings, headers, cookies, user data, and unknown fields are not exported.
- `LoggingIntegration.event_level`, Sentry logs, tracing, and automatic sessions are disabled; the SDK retains at most 20 breadcrumbs.
- `tests/core/test_error_tracking.py` covers hostile payloads, repeated logs, callback failure, envelope item types, and the 128 KiB event cap. At this baseline, `./.venv/bin/pytest tests/core/test_error_tracking.py -q` passes `17` tests.
- `docs/error-telemetry.md` is the durable policy owner.

Resolved by this implementation:

- Five production log records (four operation schemas) now emit `runestone_telemetry` markers in `agents/manager.py` and `core/ocr.py`.
- The sanitizer validates `contexts.runestone.request_id` (32 lowercase hex) and merges it with event-level `status_code` as a validated union.
- `RequestCorrelationMiddleware` in `error_tracking.py`, registered in `create_application()`, binds a server-generated ID to Sentry's per-request isolation scope (HTTP only; merge semantics; no early removal so escaping exceptions keep the ID).
- Tests pass a production producer through an application request to a captured real-SDK envelope, including a `SentryAsgiMiddleware` escaping-exception regression test and sentinel matrix.
- Quota/volume impact is documented in `docs/error-telemetry.md`.

Still outstanding:

- Quota/volume documentation is recorded, but the required privacy/security approval is not yet obtained (commit-bound, on the PR).
- The optional release-owner synthetic canary before deployment has not been performed.

The standalone recall worker in `recall_main.py` does not initialize error tracking. Instrumenting that process is not silently bundled into this task; see Non-goals and follow-up.

## Decisions

1. **Keep INFO breadcrumbs disabled.** No current diagnostic case justifies admitting every INFO record to the SDK callback. The first release uses existing warning/error failure boundaries only.
2. **Keep log events disabled.** Breadcrumbs remain attached to automatic exception events; warning/error logs do not become standalone Better Stack events, avoiding duplicate exception reporting.
3. **Use direct `extra={"runestone_telemetry": ...}` markers.** Five exact log-record edits implementing four operation schemas in two source files are clearer than adding a logging facade or new dependency. The sanitizer remains the only export authority.
4. **Generate request IDs internally.** Use a fresh lowercase UUID hex value per HTTP scope. Do not accept an inbound ID, expose a response header, or correlate users/sessions. The ID's diagnostic value is correlating multiple error events raised inside one request scope (for example a handled 500 plus a late background-task failure); a DEBUG-level local log of the ID is allowed and carries no export risk because the sanitizer owns export.
5. **Bind correlation to Sentry's existing ASGI isolation scope.** Do not create a nested isolation scope; Sentry SDK 2.68.1 already creates and clears one per ASGI request.
6. **Instrument only API-process paths in this release.** Use high-signal paths that either precede a re-raised exception or record a meaningful fallback. Do not mass-mark existing logs.

## Safe data contract extension

Extend the existing contract with one field:

| Output | Source | Validator | Failure behavior |
| --- | --- | --- | --- |
| `contexts.runestone.request_id` | Runestone-generated `uuid.uuid4().hex` | exactly 32 lowercase hex characters | omit invalid field |

Preserve `contexts.runestone.status_code` when both fields are present: the event projection is a validated union of scope-injected and event-level fields, never a wholesale replacement of the `runestone` context. Do not admit request IDs through arbitrary tags, log messages, inbound headers, or request data. Update `docs/error-telemetry.md` and hostile tests with the exact rule.

## Initial production producers

Add markers only to these existing records; keep their local human-readable messages unchanged.

| File and path | Marker | Safe fields | Why it is useful |
| --- | --- | --- | --- |
| `src/runestone/agents/manager.py::prepare_pre_turn` coordinator fallback | `operation=coordinator_plan`, `outcome=fallback_teacher_only`, configured coordinator provider/model | Explains why a later teacher-only turn failed without exporting the exception or user/chat data. |
| `src/runestone/agents/manager.py::generate_teacher_response` re-raised teacher failure | `operation=teacher_response`, `outcome=failed`, configured teacher provider/model | Becomes the last safe breadcrumb before automatic capture of the re-raised request exception. |
| `src/runestone/core/ocr.py::_preprocess_image_for_ocr` recoverable fallback | `operation=ocr_preprocess`, `outcome=fallback_original` | Preserves the earlier degradation if OCR later fails, without image attributes or exception text. |
| `src/runestone/core/ocr.py::extract_text`, the `except OCRError` record `ocr error raised; re-raising` | `operation=ocr_extract`, `outcome=failed`, configured OCR provider/model | Marks the domain-failure exit exactly once; earlier validation logs stay unmarked. |
| `src/runestone/core/ocr.py::extract_text`, only the first generic-exception record `ocr unexpected error type=%s` | `operation=ocr_extract`, `outcome=failed`, configured OCR provider/model | Marks the unexpected-failure exit exactly once; the following exception-message record stays unmarked. |

Do not mark logs containing user IDs, chat IDs, usernames, Telegram/update identifiers, URLs, paths, counts derived from user content, exception strings, or arbitrary provider responses. Do not invent `retry_count` or `duration_bucket` where the production code has no authoritative value.

## Implementation steps and ownership

Implementation order is strictly `preflight -> 1 -> 2 -> 3 -> 4 -> privacy/security review`. Implementation uses one owner to avoid overlapping edits in the telemetry contract and tests.

### Preflight and forbidden writes

- Re-read the live Dart task and record its current status, description, blocker relationship, and acceptance criteria. A changed task returns this plan to review.
- Assert `uv.lock` still resolves `sentry-sdk==2.68.1`. The request-isolation and fail-closed callback analysis is version-specific; any locked-version change requires re-inspection and plan review.
- Treat `pyproject.toml` and `uv.lock` as forbidden writes. This task adds no dependency and does not change the permitted Sentry version range.
- Confirm the implementation checkout follows the Runestone work-item branch/worktree workflow and preserve unrelated staged, unstaged, and untracked work.

### 1. Extend and bind request correlation

Owner: backend implementation worker.

Write set:

- `src/runestone/core/error_tracking.py`
- `src/runestone/api/main.py`
- `tests/core/test_error_tracking.py`
- `tests/api/test_main.py`

Work:

- Add the exact request-ID validator and define explicit merge semantics for `contexts.runestone` in `_project_event`: the projection must be a validated union of the scope-injected `request_id` and event-level `status_code`, never a wholesale replacement of the `runestone` dict. Test both fields present, and each alone.
- Add a minimal pure-ASGI middleware in `error_tracking.py` that handles HTTP scopes, generates one ID, and calls `sentry_sdk.get_isolation_scope().set_context("runestone", {"request_id": request_id})` inside the SDK-created request scope. WebSocket scopes pass through without an ID; revisit only if a WebSocket-path producer is ever instrumented.
- Make the middleware pass through without generating an ID or mutating ambient scope when `sentry_sdk.is_initialized()` is false.
- Pass non-request/lifespan scopes through unchanged.
- Register the middleware in `create_application()` without adding headers or accepting client correlation values.
- Prove concurrent HTTP requests receive distinct IDs and a completed request cannot leak its ID into the next request; prove disabled mode does not mutate ambient isolation state.

Exit gate: unit and ASGI tests prove valid propagation, invalid omission, HTTP coverage, and isolation with no sensitive data exported.

### 2. Add the named breadcrumb producers

Owner: same backend implementation worker, after step 1.

Write set:

- `src/runestone/agents/manager.py`
- `src/runestone/core/ocr.py`
- `tests/agents/test_manager.py`
- `tests/core/test_ocr.py`

Work:

- Add only the five exact log-record markers (four operation schemas) listed above using code/config-derived values. Provider/model values come from `settings` and are config-owned, never user-derived.
- Assert exact marker mappings on the relevant `LogRecord` objects; do not assert only formatted `caplog.text`.
- Keep current exception/fallback behavior and local messages unchanged.
- Add one negative test per surface showing exception text and representative sensitive sentinels are absent from the marker.

Exit gate: focused producer tests pass and a source search shows no unplanned production marker.

### 3. Prove the complete capture path

Owner: same backend implementation worker.

Write set:

- `tests/core/test_error_tracking.py`
- request/producer test file selected above

Work:

- Use the existing in-memory Sentry transport and production `setup_error_tracking` options.
- Drive the synthetic `/api/chat/message` failure path with dependency overrides that still invoke the real `AgentsManager.generate_teacher_response`; make the teacher double raise a sentinel exception so the endpoint produces its handled `500` and Sentry's Starlette integration captures it.
- Seed local log messages, exception text, request headers/query/body, and marker-adjacent values with named secret/user-content sentinels; assert none occur in serialized envelope bytes.
- Reuse the existing real-SDK tests from the sanitizer baseline for newest-20 behavior, SDK-option exclusion, and envelope item types; the new integration test must not re-prove them, and asserts the named producer breadcrumb, route template, and internal request ID over and above the baseline assertions.

Exit gate: integration test fails before producer/correlation changes and passes after them without network access.

### 4. Document policy, volume, and review evidence

Owner: implementation owner for repository docs; independent reviewer for approval.

Write set:

- `docs/error-telemetry.md`
- this plan only for `(done)` checklist marks while active

Work:

- Document request-ID provenance/isolation, the exact initial producer list, and the explicit INFO decision.
- Record explicitly that `duration_bucket` and `retry_count` remain validator-only: no production site currently has an authoritative value, and inventing one is worse than omitting it.
- Document quota/volume impact from provider-owned documentation (published Sentry/Better Stack limits or pricing pages). If no authoritative source supports a claim, record the renegotiated acceptance with the Dart task owner instead of leaving the criterion silently unmet.
- Record one sentence of volume evidence: the 128 KiB per-event cap is enforced in code and tested; note the approximate serialized size of a fully populated event (bounded by 20 sanitized crumbs). No measurement protocol, fixture identity, or percentage-growth exercise.
- Obtain independent privacy/security approval on the exact reviewed commit/PR, covering the diff, test sentinels, and durable policy. Record approval on the PR, not as a self-approval in this file. Standard code review covers implementation correctness; no separate audit workflow.

Exit gate: durable docs match tests and the exact implementation commit has explicit privacy/security approval.

## Acceptance and evidence matrix

| Requirement | Evidence |
| --- | --- |
| Useful sanitized breadcrumbs reach a captured error | Real-SDK application-path envelope test asserts the named producer breadcrumb and safe fields. |
| Secrets and user content do not reach Better Stack payloads | Serialized-envelope sentinel matrix covers request data, log text/args, exception text, auth/token data, chat/transcript/vocabulary, usernames, and Telegram identifiers. |
| Request correlation is safe and isolated | HTTP concurrency tests assert server generation, 32-hex shape, distinct values, no inbound trust, and no cross-request leakage. |
| Warning/error breadcrumbs remain explicitly opt-in | Source inventory plus producer tests; unmarked Runestone logs and all third-party logs remain absent. |
| INFO policy is evaluated | `LoggingIntegration.level` remains `WARNING`; a real-SDK test proves a marked INFO record is still excluded. |
| No duplicate or new telemetry channels | SDK option assertions and envelope item-type assertions keep event-level logging, Sentry logs, tracing, sessions, replay, and attachments disabled. |
| Volume is bounded and documented | Existing newest-20 and 128 KiB tests plus a one-sentence populated-event size note in `docs/error-telemetry.md`. |
| Quota impact is documented or renegotiated | Provider-owned documentation recorded in `docs/error-telemetry.md`, or an explicitly renegotiated acceptance criterion with the Dart task owner. |
| Privacy/security approval exists | Commit-bound privacy/security review approval on the implementation PR. |

## Validation commands

During implementation, run the narrowest affected sets:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python -m pytest tests/core/test_error_tracking.py -q
UV_CACHE_DIR=.uv-cache uv run --extra dev python -m pytest tests/api/test_main.py tests/agents/test_manager.py tests/core/test_ocr.py -q
rg -n 'runestone_telemetry' src/runestone
```

Before publication, run:

```bash
make security-check
make check-readiness
```

Associate every result with the exact combined HEAD/staged/unstaged/untracked review surface. Any behavior-changing review fix invalidates the affected focused tests and the privacy/security approval.

## Release gate and rollback

Repository tests do not authorize external telemetry transmission. The release owner may optionally send one synthetic event against a verified non-production Better Stack Errors application using fake sentinels only, confirming the expected route/request ID/breadcrumb fields are present and blocked sentinels are absent; record the event ID and reviewed commit without recording the DSN. Roll back by reverting the implementation commit/PR while retaining its ancestor sanitizer commit `4b08c4a`. Emergency containment is removal of `SENTRY_DSN` through deployment secrets by the release owner; repository agents must not mutate live secrets.

## Non-goals and follow-up

- Enabling INFO breadcrumbs, standalone Better Stack Logs, tracing, metrics, sessions, replay, profiling, attachments, or frontend telemetry.
- Broad structured-logging cleanup or marking every existing warning/error.
- Exporting raw durations, content-derived counts, user/session identifiers, hashed personal data, inbound request IDs, or response correlation headers.
- Instrumenting the standalone recall worker. If Better Stack coverage is required there, create a follow-up that first defines its own initialization/release identity (for example `runestone-recall@<commit>`), isolation lifecycle for scheduled jobs, and synthetic worker-path evidence; do not add dead Telegram markers before that boundary exists.
- Better Stack account, retention, data-region, billing, alert, or production-secret changes.

## Execution

One implementation owner performs all source, test, and doc writes; privacy/security review is read-only and commit-bound. Keep the evidence packet to the changed diff, focused command summaries, and `docs/error-telemetry.md`. No evidence-tier machinery, audit workflow, plan-digest protocol, or plan-retention lifecycle: this file can be removed once durable decisions live in `docs/error-telemetry.md` and the Dart task is complete.

## Final checklist

- [x] (done) Dart task re-confirmed for scope/status — by the repository owner on 2026-09-11, not by a live agent re-read (Dart requires login); see the State line above.
- [x] (done) Confirm `sentry-sdk==2.68.1` and preserve forbidden dependency files.
- [x] (done) Implement request-ID projection with explicit merge semantics and HTTP ASGI isolation binding.
- [x] (done) Add exactly the five named production markers implementing four operation schemas.
- [x] (done) Add real-SDK production-path and hostile sentinel evidence, reusing baseline envelope assertions.
- [x] (done) Record INFO decision, duration/retry waiver, quota note, and one-sentence volume evidence in `docs/error-telemetry.md`.
- [ ] Pass focused tests, `make security-check`, and `make check-readiness` on the final review surface.
- [ ] Obtain commit-bound privacy/security approval before publication.
- [ ] Optional single synthetic canary by the release owner before deployment.
