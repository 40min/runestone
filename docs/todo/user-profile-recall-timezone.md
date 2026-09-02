# Per-user Recall Schedule and Timezone

## Plan Control

- Dart task: [`VjO9npvNgjXf` — user-profile: add user's timezone and take it into acc on sending words](https://app.dartai.com/t/VjO9npvNgjXf-user-profile-add-users-timezon)
- Plan ID: `VjO9npvNgjXf-user-recall-timezone-v3`
- State: `READY_TO_FREEZE`
- Freeze candidate identity: `VjO9npvNgjXf-user-recall-timezone-v3@5d369c496788f120f144b9bf6077a0d789cca0ceea5e8e95b5199ed5dec821b9`
- Independently reviewed candidate SHA-256: `5d369c496788f120f144b9bf6077a0d789cca0ceea5e8e95b5199ed5dec821b9`
- Repository baseline: `66a22e40650f304e8b70fa903297dba4689b6f9c` (`main`; clean committed baseline plus this plan-only modification)
- Alembic baseline: `8c3e4a1f2b7d (head)`
- SDD tier: `S2`
- Execution: one backend/data owner, one frontend owner, one lead integrator, and one independent read-only reviewer

This file is planning authority only. Implementation must start from a clean, then-current base after preflight and must not mutate a frozen revision.

## Implementation at a Glance

1. Keep timezone as an account preference on Profile and replace free text with a selection-only IANA timezone control.
2. Store start/end hours with `recall_user_states`; expose hours, enablement, and effective timezone through the Recall API.
3. Put start time, end time, and Start/Stop delivery controls on the existing Recall page—not on Profile.
4. Evaluate each enabled user against their saved timezone and window inside the locked delivery use case, then remove global start/end configuration.
5. Prove migration, API, UI, temporal, transaction, container, and rollback behavior before release.

## Clarification Log and Assumptions

1. The user corrected the UX location: recall start/end and Start/Stop belong on the existing Recall page.
2. Profile continues to own timezone because it is account-wide and already used outside Recall. Recall displays the effective timezone read-only and directs the user to Profile to change it.
3. The Recall page adds exactly three editable actions in this scope: start hour, end hour, and Start/Stop. Queue controls remain unchanged.
4. Existing `recall_user_states.is_enabled` remains the only delivery-enablement source; no second boolean is added.
5. Web and Telegram Start/Stop update the same state. Web Stop preserves chat ID, queue, cursor, and hours. Web Start requires an existing configured state with a stored chat ID.
6. An unconfigured user sees disabled default `09:00`–`22:00` controls plus current Telegram onboarding. Sending `/start` creates the state with those defaults and enables delivery.
7. Existing configured users receive `09:00`–`22:00` during migration. New states receive the same database defaults.
8. `RECALL_INTERVAL_MINUTES` remains global. It controls evaluation cadence and does not promise an exact delivery minute.
9. Timezone values are IANA identifiers. Profile uses a searchable, selection-only control; browser detection is a suggestion and never silently overwrites a saved value.
10. Frozen timezone rule: trim input; accept exactly `UTC`, or a slash-containing key for which `ZoneInfo(key)` succeeds; preserve the trimmed key. Migration normalizes legacy failures to `UTC`.
11. Hours have one-hour granularity. Start is inclusive, end exclusive, and overnight windows are supported. Equal start/end is rejected; all-day mode is outside scope.
12. Saved settings apply on the next worker evaluation. No restart or per-user scheduler job is required.
13. Eligibility uses fresh persisted state inside the existing per-user session before queue mutation or Telegram I/O. The callback-spanning lock/transaction remains intact for eligible delivery.
14. DST follows conversion from an aware UTC instant. The worker neither synthesizes skipped spring-forward sends nor deduplicates repeated fall-back hours.
15. Current code already stores `users.timezone`, exposes Recall at `?view=recall`, persists `is_enabled`, and shows delivery status read-only. This plan connects and hardens those parts.

## SDD Tier Resolution

This remains `S2`: persisted data, authenticated contracts, browser UX, all-user delivery policy, container timezone data, and deployment sequencing carry meaningful data/browser/architecture/release risk across multiple owners. The UX relocation does not lower those risks.

Canonical resolver input:

```json
{
  "taskCount": 3,
  "executableOwners": ["recall-backend-owner", "recall-frontend-owner", "timezone-plan-lead"],
  "capabilityHints": [
    "database-migration",
    "authenticated-recall-settings-api",
    "browser-timezone-selection",
    "scheduled-delivery-policy",
    "container-startup-sequencing"
  ],
  "riskFlags": {
    "architecture": true,
    "performance": true,
    "browser": true,
    "data": true,
    "release": true,
    "security": false,
    "externalEnvironment": true
  },
  "requirementsBytes": 18000,
  "externalSpecification": true
}
```

Resolved with `agent-lifecycle tier resolve --request /tmp/runestone-recall-schedule-tier-v3.json`:

```json
{
  "schemaVersion": "agent-sdd-tier-resolution.v1",
  "tier": "S2",
  "reasons": [
    "multiple-executable-owners",
    "architecture-risk",
    "browser-risk",
    "externalEnvironment-risk",
    "performance-risk",
    "external-specification-required"
  ],
  "requestDigest": "b4b37684fe84ee819f7e533b62d19ce16a60b3e38f48dc8ee94dec71d3cedf66"
}
```

## Product Specification

### Problem and outcome

Delivery currently checks one deployment-local window before loading users. Users are treated as if they share the worker's timezone and preferred hours. Profile timezone accepts arbitrary text, scheduled delivery ignores it, and the Recall page cannot change hours or enablement.

After this work:

- Profile owns a valid IANA timezone through a mistake-resistant selector.
- Recall owns its start/end hours and enablement in `recall_user_states`.
- Recall page owns the corresponding controls.
- One global worker interval remains, but eligibility is per user.
- Defaults preserve current `09:00`–`22:00` behavior for UTC users.
- Invalid data for one user cannot break a sweep.

### User-visible behavior

Profile shows a searchable **Timezone** selector containing `UTC` and browser-supported IANA zones. It includes a valid saved value and browser-detected suggestion without silently saving the latter.

The Recall page adds a compact **Delivery schedule** section near existing delivery status:

- **Starts** and **Ends** selectors, each `00:00` through `23:00`;
- helper text explaining cadence, inclusive start, exclusive end, and overnight windows;
- read-only effective timezone plus direction to Profile;
- **Start delivery** when configured and stopped, or **Stop delivery** when running;
- pending-state protection against a second same-page settings mutation;
- success/error feedback using existing Snackbars.

For API/UI purposes, `configured` means a recall row exists **and** has a non-null Telegram chat ID. A chat-less row left by `/stop`-before-`/start` is unconfigured. For absent or chat-less unconfigured users, schedule, Start/Stop, and queue actions are disabled and current Telegram onboarding remains. Queue actions remain enabled only for configured-but-disabled users. Direct bump/postpone/remove calls against a chat-less row retain the current row-based backend behavior; this accepted API/UI difference avoids redefining queue ownership, while the UI prevents those actions until Telegram linkage exists.

The form keeps server state separate from draft hours. **Save times** patches the two valid draft hours. Start/Stop atomically patches the currently displayed valid draft hours plus the desired enablement, so it never discards unsaved edits. Equal draft hours disable Save and Start/Stop, show an inline error, and move focus to the invalid schedule group on submission attempt. A failed request keeps the draft and prior authoritative enablement; reload discards drafts and reloads persisted values. Every success replaces Recall state and resets the draft from the full server response.

### Recall API

`GET /api/recall` keeps existing fields and adds required settings fields:

```json
{
  "configured": true,
  "delivery_enabled": true,
  "recall_start_hour": 9,
  "recall_end_hour": 22,
  "timezone": "Europe/Helsinki",
  "words": []
}
```

For no recall row, return `configured=false`, `delivery_enabled=false`, default hours `9`/`22`, validated effective profile timezone, and `words=[]`. For a chat-less row, return `configured=false`, its stored hours, `delivery_enabled=false`, timezone, and its existing queue. A read never creates state.

Add `PATCH /api/recall/settings`. It accepts a partial object with at least one of:

- `recall_start_hour`: strict JSON integer `0..23`;
- `recall_end_hour`: strict JSON integer `0..23`;
- `delivery_enabled`: strict JSON boolean.

Omission preserves a field. Explicit null, booleans as hours, numeric strings, unknown fields, and an empty object return `422`. After merging with persisted values, equal hours return `400`. `timezone` is read-only here and remains writable through `PUT /api/me`.

The endpoint requires an existing state with non-null Telegram chat ID; otherwise it returns existing onboarding guidance with `409` and no mutation. It derives user ID from authentication, calls a locked `RecallService` operation, commits exactly once at the endpoint boundary, rolls back on failure, and returns the full `RecallResponse`.

Add `InvalidRecallScheduleError` under `runestone.core.exceptions`. RecallService raises it only when the merged effective hours are equal or persisted hours are invalid. The endpoint maps an invalid submitted/effective schedule to `400` with a safe fixed detail; it must be handled before the generic `RecallOperationError` branch so it cannot become `500`. Corrupt persisted hours encountered during delivery fail closed and remain an operational error category rather than a client response.

Start/Stop semantics:

- Stop preserves chat ID, queue, cursor, and hours.
- Start resumes the configured state without Telegram relinking.
- Repeated Start/Stop is idempotent.
- Telegram `/start` and `/stop` continue to update the same `is_enabled` field.
- New `/start` uses database hour defaults; repeated `/start` preserves saved hours.

`PUT /api/me` retains timezone only. It rejects explicit null/non-string input with `422`; strings failing the frozen rule use the endpoint's existing domain-validation `400` path.

### Persistence and timezone runtime

Add to `recall_user_states`:

- `recall_start_hour INTEGER NOT NULL DEFAULT 9`;
- `recall_end_hour INTEGER NOT NULL DEFAULT 22`.

Add named range and unequal checks, and matching ORM defaults. Do not add hours to `users` or another enablement column.

Timezone normalization is an irreversible data correction with zero accepted data loss (`RPO=0`) for original profile values. The release owner must first count distinct/total valid and invalid rows and create a recoverable, access-controlled database backup or encrypted `user_id`→original-timezone export. Record its location, checksum, retention, and restore owner outside this plan. Production migration is blocked without that evidence.

Before production, rehearse the revision on a size-representative PostgreSQL copy. The migration sets a 5-second lock timeout and 60-second statement timeout (or stricter deployment-standard values), aborts without partial commit on timeout, and records elapsed time. The release owner schedules a maintenance window from that result rather than assuming metadata-only DDL.

The migration must:

1. backfill existing recall states through server defaults;
2. normalize legacy `users.timezone` values failing the frozen rule to `UTC`, using revision-local validation rather than an application helper;
3. install range and unequal constraints;
4. keep defaults for future `/start` inserts;
5. emit/record the number of normalized rows without logging raw timezone values;
6. downgrade only the new constraints/columns, never timezone, enablement, or queues. Schema downgrade does not restore normalized timezone strings; recovery uses the pre-deploy artifact.

Add `tzdata` as an unconditional runtime dependency, refresh `uv.lock`, and set `PYTHONTZPATH=""` in backend and recall runtime images so `zoneinfo` uses locked package data.

### Delivery contract

Keep one `IntervalTrigger(minutes=RECALL_INTERVAL_MINUTES)`. Remove global-window checks from `TelegramRecallDelivery`. Replace queue-bearing `get_active_recall_states()` with `get_delivery_candidate_user_ids()`, which performs one PostgreSQL query returning only ordered user IDs for enabled, active users currently inside their local ordinary or overnight window. The query joins `pg_timezone_names`, so a manually corrupted timezone excludes only that user instead of failing enumeration for every user. It may evaluate saved hours and timezone but must not load them, queues, vocabulary rows, or usernames into application memory. Remove the old public enumeration method if no production caller remains. The transport opens one isolated session per candidate.

Within `RecallService.deliver_next_word()`:

1. lock current recall state;
2. reject missing, disabled, or chat-less state without mutation;
3. load the current user through `UserService` and recheck account activation, timezone, and the locked delivery window to close enumeration races;
4. reject an ineligible candidate before queue or vocabulary access;
5. preserve existing queue validation, callback, learning, cursor, commit, and rollback order.

```text
start < end: start <= local_hour < end
start > end: local_hour >= start OR local_hour < end
start == end: invalid persisted state; fail closed
```

If corrupt timezone survives migration, log only user ID plus fixed category `invalid_timezone_fallback`, evaluate that user in UTC, and continue. Never log the corrupt value. Invalid hours fail closed for that user.

### Frontend timezone options

Profile uses `Intl.supportedValuesOf("timeZone")` when available, adds `UTC`, includes saved and valid browser-detected values, deduplicates, sorts, and does not use `freeSolo`. Without that API, it still offers `UTC`, saved valid value, and valid detected value. No timezone dependency or endpoint is added.

### Non-goals

- Timezone editing on Recall or recall controls on Profile.
- Minute granularity, exact send minute, per-user interval, weekdays, quiet-day calendars, pause-until, or all-day mode.
- Web creation of a recall row before Telegram supplies chat ID.
- Per-user scheduler jobs or scheduler recreation.
- Moving timezone into recall state or duplicating enablement in users.
- Queue, words-per-day, cooldown, Telegram content, or callback transaction changes.
- A general scheduling framework, production migration, deployment, or real Telegram sends during validation.

## Requirements

- **R1 Persistence:** Hours live with configured recall state, default `09`/`22`, with database constraints.
- **R2 Timezone:** Profile owns valid IANA timezone; migration and runtime handle legacy corruption safely.
- **R3 API:** Recall GET returns settings/timezone/queue; authenticated PATCH updates hours and enablement.
- **R4 Recall UX:** Existing Recall page provides accessible hour and Start/Stop controls with onboarding/pending/feedback behavior.
- **R5 Profile UX:** Profile timezone becomes searchable and selection-only; no recall controls are added there.
- **R6 Eligibility:** Candidate enumeration evaluates each user's saved timezone and window before any per-user queue work.
- **R7 Transactions:** Settings update locks recall state and commits once at endpoint; delivery preserves its callback-spanning transaction.
- **R8 Lifecycle:** Web and Telegram share enablement; Stop preserves state; Start requires existing linkage.
- **R9 Cleanup:** Remove global start/end settings, retain global interval.
- **R10 Temporal/isolation:** Cover boundaries, overnight, DST, corruption, and independent multi-user outcomes.
- **R11 Release:** Prove runtime timezone data, migration/recovery, focused suites, real-browser behavior, readiness, security, containers, docs, and independent review.
- **R12 Enumeration performance:** Every interval enumerates lightweight candidate IDs only; queue/vocabulary work occurs only inside eligible locked delivery.

## Developer Overview

Timezone stays in the user domain because it is an account preference already consumed outside Recall. Hours and enablement belong to the recall aggregate and its page. RecallService coordinates delivery policy through UserService; each service continues to access only its own repository.

The Recall endpoint is the outer transaction boundary for web settings. It does not access repositories or locks directly. RecallService locks and updates through RecallRepository; the endpoint commits/rolls back once.

The scheduler remains user-agnostic and only wakes at the global cadence. The locked per-user use case owns local-time eligibility, so out-of-window users have no queue, cursor, learning, or Telegram side effect.

## Workstreams and DAG

```text
Frozen plan + clean baseline
  -> WS1 backend/data/API
       -> WS2 Recall and Profile frontend
            -> WS3 lead integration/docs/evidence
                 -> independent implementation audit
                      -> external release-owner migration/deployment gate
```

`recall-release-owner` is an external, non-repository owner with authority for the protected timezone backup/export, restore rehearsal, maintenance window, production migration, and orchestrator sequencing evidence. This owner has no implementation write set and cannot delegate production mutation to WS1 or WS3 without plan reopen and explicit authority.

### WS1 — Backend, data, API, and delivery policy

- Owner: `recall-backend-owner`
- Covers: R1-R3, R6-R10, R12, runtime portion of R11

1. Add recall hours/constraints, recoverable timezone normalization, unconditional `tzdata`, and both Dockerfile settings.
2. Add `runestone.utils.timezones`; keep package `__init__.py` empty.
3. Harden Profile timezone validation without adding recall fields to Profile.
4. Extend recall DTO/schema/serialization with hours and effective timezone, including non-mutating unconfigured defaults.
5. Add locked settings update and `PATCH /api/recall/settings`, preserving linkage and endpoint-owned transactions.
6. Replace queue-bearing active-state enumeration with a single timezone-catalog-backed candidate-ID query; retain locked enablement/chat checks and recheck current activation/timezone/window in `deliver_next_word()` before queue access.
7. Remove global start/end settings, retain the interval/Telegram lifecycle, remove Alembic startup from Recall, and make Docker Compose Recall wait for healthy backend migration completion.
8. Add migration, API, query-count, repository, service, Telegram, config, and temporal regressions.

### WS2 — Recall and Profile frontend

- Owner: `recall-frontend-owner`
- Depends on: WS1 schema handoff
- Covers: R3-R5 and browser portion of R11

1. Extend Recall types/useRecall with settings mutations, in-flight protection, and authoritative response replacement.
2. Add a focused delivery-schedule component with hours, timezone context, Save times, and Start/Stop.
3. Integrate it into RecallView; disable settings for onboarding and keep queue controls while stopped.
4. Replace Profile timezone free text with a selection-only autocomplete using browser `Intl` and bounded fallbacks.
5. Test configured/stopped/unconfigured/pending/success/failure/overnight/equality and timezone fallback paths.

### WS3 — Lead integration and evidence

- Owner: `timezone-plan-lead`
- Depends on: WS1 and WS2
- Covers: R11

1. Resolve contract integration only; reopen for undeclared feature work.
2. Update README and recall persistence/integration docs.
3. Verify PostgreSQL upgrade/downgrade/upgrade, normalization recovery evidence, and expected DDL/update locking.
4. Verify both Python images use locked timezone data.
5. Run focused, readiness, security, container, and scope gates.
6. Route frozen plan, diff, ownership, and evidence to independent implementation audit.

### External release gate — production authority

- Owner: `recall-release-owner` (external, non-repository)
- Depends on: independent implementation audit `READY`
- Inputs: frozen plan, migration revision/checksum, disposable/staging evidence, production row counts, protected backup/export destination, approved maintenance window, and production orchestrator access.
- Required outputs: valid/invalid row counts; backup/export location and checksum; restore-rehearsal result and elapsed time; migration window approval; production migration result; backend-before-Recall sequencing logs; rollback decision record.
- Authority boundary: this owner alone authorizes production backup, migration, restore, and deployment ordering. Implementation agents may prepare commands/evidence but may not perform those mutations.

## Exact Write Sets

Additional paths require plan reopen or explicit lead-owned revision.

### WS1 exclusive

- `alembic/versions/<new_revision>_add_recall_delivery_schedule.py` (new; record generated ID at run start)
- `pyproject.toml`, `uv.lock`, `Dockerfile.backend`, `Dockerfile.recall`
- `docker-compose.yaml`
- `src/runestone/db/models.py`, `src/runestone/db/recall_repository.py`
- `src/runestone/utils/timezones.py` (new)
- `src/runestone/core/exceptions.py`
- `src/runestone/api/schemas.py`, `src/runestone/api/recall_schemas.py`, `src/runestone/api/recall_endpoints.py`
- `src/runestone/services/user_service.py`
- `src/runestone/recall/types.py`, `src/runestone/recall/service.py`
- `src/runestone/telegram/delivery.py`, `src/runestone/config.py`
- `tests/api/test_user_endpoints.py`, `tests/api/test_recall_endpoints.py`
- `tests/db/test_recall_repository.py`
- `tests/services/conftest.py`, `tests/services/test_user_service.py`
- `tests/recall/test_service.py`, `tests/telegram/test_delivery.py`, `tests/telegram/test_commands.py`, `tests/test_config.py`
- `tests/test_recall_main.py`
- `.env.example`, `.env.test`
- `integration_tests/containers/recall_schedule.compose.yaml` (new, isolated test-only stack)
- `integration_tests/containers/verify_recall_schedule_startup.py` (new)
- `integration_tests/browser/prepare_recall_schedule_fixture.py` (new)
- `integration_tests/recall/run_recall_workflow.py`, `integration_tests/recall/coverage_manifest.json`

### WS2 exclusive

- `frontend/src/components/auth/TimezoneAutocomplete.tsx` (new)
- `frontend/src/components/auth/TimezoneAutocomplete.test.tsx` (new)
- `frontend/src/components/auth/Profile.tsx`, `frontend/src/components/auth/Profile.test.tsx`
- `frontend/src/components/recall/RecallDeliverySchedule.tsx` (new)
- `frontend/src/components/recall/RecallDeliverySchedule.test.tsx` (new)
- `frontend/src/components/recall/RecallSummaryPanel.tsx`
- `frontend/src/components/RecallView.tsx`, `frontend/src/components/RecallView.test.tsx`
- `frontend/src/hooks/useRecall.ts`, `frontend/src/hooks/useRecall.test.ts`
- `frontend/src/types/recall.ts`
- `integration_tests/browser/verify_recall_schedule_configured.js` (new)
- `integration_tests/browser/verify_recall_schedule_unconfigured.js` (new)

### WS3 lead-owned

- `README.md`
- `docs/recall-state-persistence.md`
- `docs/recall-integration-test-plan.md`

### Planning-only

- `docs/todo/user-profile-recall-timezone.md` — immutable after freeze

## Read-only Inputs and Forbidden Writes

Read-only anchors: `AGENTS.md`, `recall_main.py`, recall providers, user repository, user endpoints, auth hooks/types, `LanguageAutocomplete`, frontend API utility/package files, Makefile, and existing Alembic revisions.

Forbidden without reopen:

- hour fields in `users` or a second enablement source;
- timezone editing on Recall or recall settings on Profile;
- repository/row-lock access from API or Telegram transport;
- web creation of chat-less recall state;
- new scheduler jobs, timezone dependency/endpoint, or Telegram behavior changes;
- queue/learning/cursor/provider/session ownership changes;
- dependencies/containers/lockfiles beyond `tzdata`, `PYTHONTZPATH`, backend-as-migration-executor startup sequencing, and Recall's backend-health dependency;
- unrelated staging, reverting, or formatting.

## Current Code Anchors

| Contract | Current symbol/path | Planned change |
| --- | --- | --- |
| Recall response | `recall_endpoints._response_from_state`, `RecallResponse` | Serialize configured-by-chat-link, hours, and effective timezone. |
| Settings transaction | `recall_endpoints._run_mutation` | Reuse endpoint-owned commit/rollback and explicitly map `InvalidRecallScheduleError` to `400`. |
| Enable/disable | `RecallService.enable_for_username`, `disable_for_user`; `RecallRepository.upsert_for_user` | Preserve saved hours/chat linkage and share state with web settings. |
| Candidate scan | `RecallService.get_active_recall_states`, `RecallRepository.get_active_recall_states` | Replace with ordered lightweight user-ID enumeration; remove queue-bearing public API. |
| Delivery lock | `RecallService.deliver_next_word` | Recheck mutable delivery state and account activation before queue access while retaining callback-spanning transaction. |
| Global gate | `TelegramRecallDelivery.send_next_recall_word`, `Settings.recall_start_hour/end_hour` | Delete global gate/settings; retain interval. |
| Recall UI | `RecallView`, `RecallSummaryPanel`, `useRecall`, `RecallState` | Add schedule component and authoritative PATCH mutations. |
| Profile timezone | `Profile`, `UserProfileUpdate`, `UserService.update_user_profile` | Selection-only UI plus frozen backend validation. |
| Startup migration | backend/Recall Dockerfile `CMD`, Compose `depends_on` | Backend alone migrates; Recall starts only after backend health. |

## Acceptance and Evidence

| ID | Acceptance | Requirements | Evidence |
| --- | --- | --- | --- |
| AC1 | Recall states have non-null `09`/`22` defaults and named range/unequal checks; users has no hour columns. | R1 | E1, E2 |
| AC2 | Invalid legacy timezone becomes UTC; valid IANA survives; Profile rejects new invalid values; pre-migration originals are recoverable at RPO 0. | R2, R11 | E1, E3 |
| AC3 | Recall GET returns configured/enabled/hours/timezone/queue without creating state. | R3 | E2 |
| AC4 | Settings PATCH strictly validates partial input, equality after merge, ownership, locking, one commit, and authoritative response. | R3, R7 | E2, E4 |
| AC5 | Web Stop/Start is idempotent, atomically saves valid displayed hours, preserves linkage/queue/cursor, and returns 409 when unconfigured/chat-less. | R4, R8 | E2, E4, E5 |
| AC6 | Recall UI owns hours and Start/Stop, handles dirty/equal/onboarding/pending/error/reload states, keeps queue actions for configured-but-disabled users, and disables them for absent/chat-less users. | R4 | E5, E6 |
| AC7 | Profile owns selection-only timezone; Recall displays it read-only; labels, keyboard use, focus, and status announcements work in a real browser. | R2, R4, R5 | E5, E6 |
| AC8 | Users in different zones/windows get independent outcomes at one UTC instant. | R6, R10 | E4 |
| AC9 | Inclusive/exclusive, overnight, spring-forward, and fall-back behavior is deterministic. | R6, R10 | E4 |
| AC10 | Ineligible/corrupt users cause no queue/vocabulary query or side effect and do not block another user. | R6, R7, R10 | E4 |
| AC11 | Eligible delivery preserves lock/callback/mutation/commit/rollback order. | R7 | E4 |
| AC12 | Global start/end has no live consumer; one global interval remains. | R9 | E7 |
| AC13 | Both Python images use locked tzdata; frontend adds no timezone dependency. | R11 | E8 |
| AC14a | Repository Dockerfiles and isolated Compose evidence prove backend is the sole migration executor and Recall waits for backend health. | R11 | E8, E11 |
| AC14b | External release owner records protected recovery and equivalent production-orchestrator migration sequencing. This is deployment acceptance, not implementation completion. | R11 | External release gate |
| AC15 | Candidate enumeration is one lightweight query and does not load queues/vocabulary/usernames/hours. | R12 | E2, E4 |
| AC16 | Docs and release record accurately cover UI ownership, lifecycle, migration/recovery, rollback, and unavailable gates. | R11 | E9-E11 |

### E1 Migration

Verify the migration once against the target PostgreSQL database: confirm the Alembic head, columns, defaults, named constraints, and zero invalid schedule/timezone rows. Do not retain or run a disposable upgrade/downgrade verifier as part of routine checks. Before production, record valid/invalid counts, backup/export checksum, restore owner, retention, and a timed restore rehearsal. SQLite is not constraint truth.

```bash
.venv/bin/alembic heads
```

### E2 Recall API/repository

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/api/test_recall_endpoints.py tests/db/test_recall_repository.py -v
```

Cover absent and chat-less unconfigured reads, strict null/primitive/unknown/empty payloads, one-field merge validation, toggle idempotence, preservation, ownership, explicit equal-window `InvalidRecallScheduleError` → `400`, commit/rollback, generic errors, and repository query counts. Candidate enumeration must execute one query and no queue query. Direct bump/postpone/remove against a chat-less existing row retains current row-based backend behavior; API tests freeze that behavior while frontend tests prove the UI disables those actions.

### E3 Profile timezone

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/api/test_user_endpoints.py tests/services/test_user_service.py -v
```

### E4 Recall service/delivery

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/recall/test_service.py tests/telegram/test_delivery.py tests/telegram/test_commands.py tests/test_recall_main.py -v
```

Use fixed aware UTC instants and `UTC`, `Europe/Helsinki`, `America/New_York`; cover ordinary/overnight boundaries, DST, web/Telegram lifecycle, and transaction order. Repository assertions must prove out-of-window users are not enumerated, while service assertions retain per-user isolation.

### E5 Frontend

```bash
cd frontend
npm run test:run -- src/components/auth/TimezoneAutocomplete.test.tsx src/components/auth/Profile.test.tsx src/components/recall/RecallDeliverySchedule.test.tsx src/components/RecallView.test.tsx src/hooks/useRecall.test.ts
```

Component tests must cover dirty hours plus Start/Stop atomic payload, equal-hour focus/error, failed-save draft retention, persisted reload, keyboard-operable labels, and `role=status`/`role=alert` feedback.

### E6 Authenticated real-browser gate

Prepare a disposable browser fixture through the owned guarded helper. It must reject non-loopback database hosts and database names not ending in `_test`, create configured and chat-less accounts through production service boundaries, snapshot every touched row, write one-time credentials to a mode-0600 file under the evidence directory without printing them, and provide a manifest-driven cleanup that restores/removes all fixtures. Authenticate each persistent headed session manually from that file; credentials must never enter shell history, logs, screenshots, or repository files.

```bash
export BROWSER_TEST_DATABASE_URL=postgresql+asyncpg://runestone:runestone@127.0.0.1:5432/runestone_recall_browser_test
export BROWSER_EVIDENCE_DIR=/tmp/runestone-recall-schedule-browser/manual-run
UV_CACHE_DIR=.uv-cache uv run --extra dev python integration_tests/browser/prepare_recall_schedule_fixture.py --database-url "$BROWSER_TEST_DATABASE_URL" --output-dir "$BROWSER_EVIDENCE_DIR"
DATABASE_URL="$BROWSER_TEST_DATABASE_URL" make run-dev
playwright-cli -s=recall-schedule-configured open --browser=chrome --headed http://localhost:5173/
playwright-cli -s=recall-schedule-configured goto http://localhost:5173/?view=recall
playwright-cli -s=recall-schedule-configured run-code "$(cat integration_tests/browser/verify_recall_schedule_configured.js)"
playwright-cli -s=recall-schedule-unconfigured open --browser=chrome --headed http://localhost:5173/
playwright-cli -s=recall-schedule-unconfigured goto http://localhost:5173/?view=recall
playwright-cli -s=recall-schedule-unconfigured run-code "$(cat integration_tests/browser/verify_recall_schedule_unconfigured.js)"
UV_CACHE_DIR=.uv-cache uv run --extra dev python integration_tests/browser/prepare_recall_schedule_fixture.py --cleanup-manifest "$BROWSER_EVIDENCE_DIR/fixture-manifest.json"
```

Using keyboard input only, record snapshots/screenshots and network responses proving:

1. Profile timezone can be searched/selected and remains after reload.
2. Recall Starts/Ends have programmatic labels and can be changed without a pointer.
3. Equal hours expose an associated error and focus the schedule group; no PATCH occurs.
4. Dirty valid hours plus Start/Stop produce one PATCH containing both hours and enablement.
5. Controls block duplicate input while pending; failure retains draft and prior status with an alert; success is announced and survives reload.
6. An absent/chat-less account has disabled schedule, toggle, and queue actions plus onboarding; a configured-but-stopped account retains enabled queue actions.

Run `make run-dev` in one terminal and the browser commands in another; cleanup runs after both servers stop. The browser scripts use role/label locators, keyboard input, request/response assertions, reloads, and screenshots; they restore the configured account's original schedule/enablement in `finally`. They write redacted JSON plus PNG evidence beneath the evidence directory; WS3 records paths and SHA-256 checksums. This gate is separate from `make check-readiness`. Lack of a safe authenticated browser environment blocks release evidence, not implementation code completion, and is never a pass.

### Supplemental guarded workflow preview

Extend the no-network harness/manifest for defaults, web/Telegram Stop/Start preservation, changed settings on next evaluation, unchanged ineligible fingerprint, invalid-data isolation, and restoration of hours/enablement/chat/queue/cursor/user/offset. Cover two-user opposite eligibility in bounded orchestration tests unless the harness gains explicit multi-user confirmation/recovery.

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python integration_tests/recall/run_recall_workflow.py --show-coverage
```

Live mutation still requires existing `--apply` plus matching user/host/database confirmations. Real Telegram sends are forbidden.

`--show-coverage` proves only manifest coverage. It is supplemental and is not acceptance evidence for runtime behavior. Do not run `--apply` merely to close this plan.

### E7 Configuration/scheduler

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/test_config.py tests/test_recall_main.py -v
rg -n "RECALL_START_HOUR|RECALL_END_HOUR" src recall_main.py tests integration_tests .env.example .env.test README.md docs
rg -n "recall_interval_minutes|RECALL_INTERVAL_MINUTES" src recall_main.py tests .env.example .env.test README.md docs
```

Tests must assert `Settings` exposes no start/end fields and recall startup constructs exactly one interval delivery job. `rg` is supplemental inventory: first may match migration/history prose but no live consumer; second locates the retained interval.

### E8 Dependencies/containers

```bash
UV_CACHE_DIR=.uv-cache uv lock --check
UV_CACHE_DIR=.uv-cache uv run python -c "from zoneinfo import ZoneInfo; [ZoneInfo(name) for name in ('UTC', 'Europe/Helsinki', 'America/New_York')]"
make security-check
UV_CACHE_DIR=.uv-cache uv run --extra dev python integration_tests/containers/verify_recall_schedule_startup.py
git diff --exit-code 66a22e40650f304e8b70fa903297dba4689b6f9c -- frontend/package.json frontend/package-lock.json
```

The owned verifier uses only `integration_tests/containers/recall_schedule.compose.yaml`, a unique Compose project name, an ephemeral named database volume, test-safe environment values, and no host state/database bind mounts. It must refuse non-local database hosts. It builds backend/Recall; uses `docker image inspect` to assert backend `Config.Cmd` contains `alembic upgrade head` and Recall `Config.Cmd` does not; asserts both containers have `PYTHONTZPATH=""`, import `tzdata`, have `zoneinfo.TZPATH == ()`, and resolve representative zones; starts the isolated stack with a bounded 120-second health wait; asserts backend migration-success log precedes Recall startup; records `docker compose ps` and redacted logs; and always runs `down --volumes --remove-orphans` in `finally`. Evidence goes under `/tmp/runestone-recall-schedule-containers/<run-id>/` with SHA-256 checksums.

Docker evidence is required for implementation acceptance. Production-orchestrator sequencing is a later external release gate; its absence does not prevent an implementation audit from returning `READY`, but it blocks deployment.

### E9 Documentation

```bash
rg -n "timezone|delivery schedule|Start delivery|Stop delivery|09:00|22:00|RECALL_INTERVAL_MINUTES|overnight" README.md docs/recall-state-persistence.md docs/recall-integration-test-plan.md
```

### E10 Readiness/scope

```bash
make check-readiness
git diff --check
git status --short
git diff --name-only
git ls-files --others --exclude-standard
```

Separate task scope from pre-existing work. Do not call focused results a clean full gate when readiness, security, PostgreSQL, or containers did not run.

### E11 Independent implementation audit

Reviewer receives frozen plan, baseline/reopen record, diff, ownership log, E1-E10, and unavailable-environment caveats. It checks traceability, persistence ownership, settings lifecycle, migration, DST, transaction preservation, no-network evidence, containers, forbidden writes, rollback, and truthful phase status. It may return implementation `READY` when AC1-AC14a and AC15-AC16 pass even if external AC14b is pending; the release record must then say `IMPLEMENTATION_READY_RELEASE_BLOCKED`. Production mutation remains outside agent authority and deployment remains blocked until `recall-release-owner` supplies AC14b.

## Preflight, Budgets, and Reopen Triggers

```bash
git status --short
git branch --show-current
git rev-parse HEAD
.venv/bin/alembic heads
git diff --check
```

Record generated Alembic filename after head confirmation. Each owner confirms exclusive ownership through active orchestration; filesystem cleanliness alone is insufficient.

Budgets:

- WS1: active context ≤24k tokens, rendered packet ≤8k, one implementation pass plus one correction round.
- WS2: active context ≤18k tokens, rendered packet ≤7k, one pass after schema handoff plus one correction round.
- WS3: active context ≤14k tokens, rendered packet ≤6k, integration/evidence only—not overflow implementation.
- Independent plan/implementation review: active context ≤20k tokens and rendered evidence index ≤8k; at most two plan correction rounds and one implementation correction round.
- Command evidence: keep each captured output ≤4k tokens; store full logs outside the active packet and reference path/checksum.
- Rerun only failing focused gates after in-scope fixes; rerun broad gates after focused suites pass.

`small-context-profile.v1`: give each executor Plan Control, decisions, relevant contract, assigned requirements/workstream/write set, forbidden writes, mapped evidence, the Current Code Anchors table, and `AGENTS.md`. The compact packet must remain within the owner limit above. Chat history is not authority.

Reopen and independently re-audit if Alembic head, UI ownership, persistence location, enablement source, API field/PATCH/onboarding semantics, hour/default/equality/DST rules, web-linkage requirement, scheduler model, transaction ownership, dependency strategy, write set, or external authority changes.

## Rollout and Rollback

1. Before production, count valid/invalid timezone rows and create/rehearse the RPO-0 recovery artifact. No raw timezone value enters ordinary logs.
2. New recall columns are backward-compatible: old code ignores them and keeps global hours.
3. In repository Compose, backend remains the sole migration executor; Recall's image starts `python recall_main.py` without Alembic and Compose waits for healthy backend. Production must use an equivalent one-shot/sole executor and gate Recall startup on successful migration. Missing ordering evidence blocks release.
4. Keep deployed global start/end variables until the new worker is healthy; new code ignores them, then operations may remove them. Interval remains.
5. Observe fixed-category invalid-data/settings failures, candidate counts, and delivery volume without logging profile values, message content, or new personal data.
6. Emergency code rollback leaves new columns. Old code resumes global hours. Do not downgrade schema or restore timezone values during emergency rollback.
7. For unexpected volume, stop/revert Recall first. Stored settings and backend UI cannot send without the worker.
8. Later schema downgrade is separate maintenance. It does not restore normalized timezone values; use the protected recovery artifact only when the release owner explicitly authorizes data restoration.

## Plan Lock and Review Request

After `READY_TO_FREEZE`, record plan ID, repository/Alembic baselines, reviewed document SHA-256, and revision as immutable authority. Outputs, diffs, ownership records, tests, and audits stay mutable outside this file. Contract or ownership change creates a new revision and independent review.

The independent reviewer must apply `audit-agent-plan` against the repository baseline and return findings first, traceability, scope/tier/ownership/DAG/budget/context assessment, validation executability, and one verdict: `READY_TO_FREEZE`, `CHANGES_REQUIRED`, or `BLOCKED`. Every non-ready finding names the exact edit.

## Review Record

- Audit round 1: `CHANGES_REQUIRED`. Findings covered migration sequencing, queue-bearing all-day enumeration, irreversible timezone recovery, non-executing guarded evidence, dirty-hour toggle semantics, real-browser/accessibility proof, executable container/config assertions, and incomplete freeze metadata/budgets.
- Correction round 1: designated backend-only migration execution and Compose health ordering; added lightweight candidate enumeration; added RPO-0 recovery and migration timeouts; demoted guarded preview; froze atomic dirty-hour Start/Stop; added real-browser/container/config gates; recorded tier resolution, anchors, paths, exception mapping, and numeric packet budgets.
- Audit round 2: `CHANGES_REQUIRED`. Remaining findings were chat-less queue semantics, incomplete WS3/release ownership, conflated implementation/deployment acceptance, and insufficiently reproducible browser/container gates.
- Correction round 2: froze chat-less UI/API behavior; added `timezone-plan-lead` to tier resolution; defined external `recall-release-owner`; split implementation and production release gates; added guarded browser fixture/scripts and isolated container startup verifier with exact evidence/cleanup contracts.
- Audit round 3: `READY_TO_FREEZE`; no open High or Medium findings. Requirements R1-R12 map to acceptance, owned workstreams, executable evidence, and final audit gates.
