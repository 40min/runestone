# Per-user Recall Delivery Window and Timezone

## Plan Control

- Dart task: [`VjO9npvNgjXf` — user-profile: add user's timezone and take it into acc on sending words](https://app.dartai.com/t/VjO9npvNgjXf-user-profile-add-users-timezon)
- Plan ID: `VjO9npvNgjXf-user-recall-timezone-v2`
- Plan state: `CANDIDATE_REAUDIT_PENDING`
- Freeze candidate identity: pending independent review
- Repository planning baseline: `386f5583abe7b0bda82a4facede33b05c72316da`
- Alembic planning baseline: `8c3e4a1f2b7d (head)`
- SDD tier: `S2`
- Execution model: one backend/data owner, one frontend owner, one recall owner, one lead integrator, and one independent read-only reviewer
- Planning artifact: this document; implementation must not mutate a frozen revision

The planning checkout is the clean committed `feat/specialist-context-refactor` branch plus this untracked plan. The branch delta is unrelated to this task and does not overlap the declared implementation write set. Implementation must begin from a clean, then-current Runestone base after the preflight below; it must not inherit, revert, or use unrelated feature-branch changes as evidence.

## Clarification Log and Assumptions

1. The user confirmed that each user configures their own recall delivery window. The global `RECALL_START_HOUR` and `RECALL_END_HOUR` settings are retired.
2. New users and existing users receive the current global defaults: start `09:00`, end `22:00`.
3. `RECALL_INTERVAL_MINUTES` remains a worker-level setting. It controls how often the worker evaluates users; it is not a user preference and does not promise delivery at an exact wall-clock minute.
4. Timezone choices use IANA timezone identifiers such as `Europe/Helsinki`. The profile UI is a searchable, selection-only control rather than a free-text field.
5. The UI offers the browser-detected timezone as a suggestion but never silently overwrites an already saved value.
6. `UTC` is the default and the defensive runtime fallback. The one frozen acceptance rule is: trim the input; accept exactly `UTC`, or a slash-containing key for which `ZoneInfo(key)` succeeds; preserve the accepted trimmed key verbatim. Legacy values failing that exact rule are normalized to `UTC` by the migration.
7. Delivery hours have one-hour granularity. Start is inclusive and end is exclusive. Overnight windows are supported; for example, `22:00` to `07:00` includes local hours `22` through `23` and `00` through `06`.
8. Equal start and end values are rejected rather than interpreted as either an empty or 24-hour window. A future explicit “all day” option is outside this task.
9. A saved preference takes effect on the next recall-worker evaluation. No restart, rescheduling job, or per-user APScheduler job is required.
10. Delivery eligibility is evaluated from the user’s current persisted profile inside the existing per-user recall session, before queue mutation or Telegram I/O. The existing callback-spanning transaction and row-lock contract remains intact once an eligible delivery begins.
11. DST follows `zoneinfo` conversion from an aware UTC instant. The system evaluates each real scheduler tick against the resulting local hour; it does not synthesize a send for a skipped spring-forward hour or deduplicate the repeated fall-back hour.
12. The current code already persists and exposes `users.timezone`, and the profile already renders it as raw text. This plan completes and hardens that partial feature; it does not add a second timezone column.
13. No change is requested to recall enable/disable commands, queue selection, words per day, cooldown rules, Telegram message content, or exact scheduler cadence.

## SDD Tier Resolution

The canonical resolver input was:

```json
{
  "taskCount": 4,
  "executableOwners": [
    "profile-backend-owner",
    "profile-frontend-owner",
    "recall-delivery-owner"
  ],
  "capabilityHints": [
    "database-migration",
    "profile-api-contract",
    "browser-timezone-selection",
    "scheduled-delivery-policy"
  ],
  "riskFlags": {
    "architecture": true,
    "security": false,
    "performance": true,
    "browser": true,
    "data": true,
    "release": true,
    "externalEnvironment": false
  },
  "requirementsBytes": 15000,
  "externalSpecification": true
}
```

Resolved with:

```bash
agent-lifecycle tier resolve --request /tmp/runestone-timezone-tier-request.json
```

Result:

```json
{
  "schemaVersion": "agent-sdd-tier-resolution.v1",
  "tier": "S2",
  "reasons": [
    "multiple-executable-owners",
    "architecture-risk",
    "browser-risk",
    "performance-risk",
    "external-specification-required"
  ],
  "requestDigest": "2b310b60e2949799eaf5c7112d84c157d798e1297b75314a1fc6539ed24c7910"
}
```

S2 is required because this changes persisted user data, a public profile contract, browser UX, scheduling behavior for every enabled user, two Python container dependency surfaces, and three independently executable workstreams.

## Product Specification

### Problem

Recall delivery currently checks one deployment-local global window before loading any users. Every enabled user is therefore treated as if they live in the worker’s timezone and want the same delivery hours. The user profile already stores a timezone, but the API accepts arbitrary strings, the frontend uses free text, and scheduled delivery ignores it.

### Desired outcome

- Each user owns a timezone, recall start hour, and recall end hour in their profile.
- The profile offers mistake-resistant IANA timezone selection and simple start/end selectors.
- Defaults preserve today’s `09:00–22:00` behavior for UTC users while allowing every user to customize it.
- One worker interval continues to scan enabled users, but each candidate is checked against their current local time before a word is sent.
- DST and overnight windows behave deterministically.
- Invalid profile data cannot break a whole delivery sweep.
- Global start/end configuration is removed from code, environment templates, tests, and operational documentation.

### User-visible behavior

The Profile screen shows:

- a searchable **Timezone** selector containing `UTC` and browser-supported IANA zones;
- the browser-detected zone as a suggested option when it is valid;
- a **Recall delivery starts** selector with `00:00` through `23:00`;
- a **Recall delivery ends** selector with `00:00` through `23:00`;
- helper text explaining that the start is inclusive, the end is exclusive, and overnight windows are supported;
- client validation when start and end are equal, plus the existing form-level backend `ErrorAlert` for rejected API values.

Saving the profile persists all three preferences. A successful response refreshes the authoritative values in auth context. The UI does not claim an exact message minute because delivery still runs on the configured worker interval.

### Backend/API contract

`GET /api/me` adds two required integer fields while retaining required `timezone`:

```json
{
  "timezone": "Europe/Helsinki",
  "recall_start_hour": 9,
  "recall_end_hour": 22
}
```

`PUT /api/me` accepts partial updates for the same fields:

- `timezone`: a JSON string that, after trimming, is exactly `UTC` or contains `/` and succeeds with `ZoneInfo`;
- `recall_start_hour`: a strict JSON integer `0..23` (numeric strings and booleans are rejected);
- `recall_end_hour`: a strict JSON integer `0..23` (numeric strings and booleans are rejected);
- the effective start and end, after combining submitted and persisted values, must differ.

Explicit JSON `null` is rejected for all three fields; omission is the only way to leave a preference unchanged. Invalid primitive values return FastAPI validation status `422`. An equal effective window is a domain validation error returned through the endpoint’s existing profile-update error mapping with status `400`.

Accepted timezone keys are stored verbatim after trimming. Aliases are not canonicalized. Slashless abbreviations such as `EST` and `CET` are rejected even if the host `zoneinfo` database recognizes them; slash-containing keys such as `Etc/GMT+5` are accepted when `ZoneInfo` resolves them.

### Persistence contract

Add these non-null columns to `users`:

- `recall_start_hour INTEGER NOT NULL DEFAULT 9`;
- `recall_end_hour INTEGER NOT NULL DEFAULT 22`.

Add database checks for `0 <= hour <= 23` and `recall_start_hour <> recall_end_hour`. Keep matching ORM defaults so transient/new application users and database inserts agree.

The migration must:

1. add both columns with server defaults so existing rows backfill safely;
2. normalize legacy `users.timezone` values that fail the frozen rule above to `UTC`; the revision must implement its own rule with `zoneinfo` and must not import a mutable application helper;
3. install the hour-range and unequal-window constraints;
4. keep the defaults for future inserts;
5. provide a downgrade that removes only the new constraints and columns, never the pre-existing timezone column.

Python’s `zoneinfo` must use an application-controlled timezone database in both backend and recall images. Add the `tzdata` Python dependency, refresh `uv.lock`, and set `PYTHONTZPATH=""` in both runtime Dockerfiles so `zoneinfo` bypasses system timezone paths and uses the locked package.

### Recall-delivery contract

The worker retains one `IntervalTrigger(minutes=RECALL_INTERVAL_MINUTES)`. `TelegramRecallDelivery` no longer reads or checks global start/end settings. It enumerates active recall states as it does now and opens one isolated session per user.

Within `RecallService.deliver_next_word()`:

1. lock and validate the enabled recall state using the existing transaction lifecycle;
2. load the current user through `UserService`, preserving the service boundary and avoiding repository access from Telegram transport;
3. reject inactive/missing users as today;
4. convert an aware UTC `now` to the saved `ZoneInfo` timezone;
5. evaluate the local hour against the saved window;
6. on an ineligible window, roll back/release the session and return `None` without selecting, mutating, or sending a word;
7. on eligibility, continue the existing queue validation, Telegram callback, learning-event, cursor, and commit sequence unchanged.

The production method obtains an aware UTC time itself. A narrow injectable clock/`now` boundary is permitted for deterministic unit tests, but no time service framework or global clock abstraction may be introduced.

The window predicate is:

```text
start < end:  start <= local_hour < end
start > end:  local_hour >= start OR local_hour < end
start == end: invalid persisted state; do not deliver
```

If legacy/corrupt timezone data somehow survives migration, delivery logs only user ID plus a fixed `invalid_timezone_fallback` category, uses `UTC` for that evaluation, and continues processing other users. It never logs the corrupt value. Invalid hours fail closed for that user and do not abort the sweep.

### Timezone-option contract

The frontend uses `Intl.supportedValuesOf("timeZone")` when available, adds `UTC`, includes the saved value and valid browser-detected value, removes duplicates, and sorts deterministically. It does not use `freeSolo`.

When `Intl.supportedValuesOf` is unavailable, the selector still contains `UTC`, the saved valid value, and the browser-detected valid value. This fallback prevents arbitrary input without adding a timezone-list dependency. Browser capability loss must not make an existing valid saved value disappear.

### Non-goals

- Per-user delivery interval, exact send minute, weekdays, quiet-day calendars, notification count, or pause-until controls.
- One APScheduler job per user or scheduler recreation after a profile save.
- Geolocation, automatic timezone persistence, IP-based timezone inference, or location permission.
- A new timezone API endpoint or a second timezone source of truth.
- Moving recall state into the user table or moving profile fields into `recall_user_states`.
- Changing Telegram commands, queue contents, cursor rules, message formatting, or callback transaction ownership.
- Generalizing a reusable scheduling framework.
- Deployment, production database migration, or real Telegram sends as part of implementation validation.

## Requirements

- **R1 — Profile persistence:** Persist per-user `recall_start_hour` and `recall_end_hour` with `09:00–22:00` defaults and database constraints.
- **R2 — Timezone integrity:** Accept only supported IANA timezone choices, normalize legacy invalid data to `UTC`, and provide deterministic runtime fallback.
- **R3 — API contract:** Return and partially update timezone plus delivery-window fields through `/api/me` without breaking existing profile fields.
- **R4 — Profile UX:** Replace timezone free text with searchable selection and add accessible hour selectors with clear overnight semantics.
- **R5 — Per-user eligibility:** Evaluate every enabled user against their own timezone and window before Telegram I/O or queue mutation.
- **R6 — Transaction preservation:** Preserve the existing per-user session, row lock, callback-spanning transaction, commit, and rollback contracts.
- **R7 — Configuration cleanup:** Remove global start/end settings everywhere while retaining the global recall interval.
- **R8 — Temporal correctness:** Cover ordinary, boundary, overnight, UTC, invalid-data, spring-forward, and fall-back behavior deterministically.
- **R9 — Isolation:** One invalid or ineligible user must not prevent other eligible users from being processed.
- **R10 — Container/runtime support:** Ship a pinned timezone database to both Python runtime images and verify the frontend/browser fallback.
- **R11 — Durable documentation:** Update profile and recall documentation to describe the new source of truth, defaults, and operational cadence.
- **R12 — Release evidence:** Prove migration, API, frontend, recall, container dependency, readiness, and independent-review gates before release.

## Developer Overview

The persisted preference belongs to the user profile because it is configurable before or independently of Telegram recall activation. Recall remains the owner of delivery eligibility and uses `UserService` to read the current profile; Telegram transport remains a thin coordinator and never accesses a repository.

The scheduler does not become user-aware. Its only responsibility is to wake the worker at a bounded global cadence. Per-user local-time policy belongs inside the locked recall use case, which guarantees that no queue or learning mutation occurs when the user is outside their window.

The implementation deliberately reuses platform facilities: Python `zoneinfo`, browser `Intl`, MUI selection controls, the existing `/api/me` endpoint, and the existing recall session provider. No scheduling or timezone library is introduced beyond shipping `tzdata` for reproducible Python runtime data.

## Workstreams and Dependency DAG

```text
Frozen plan + clean baseline
  └── WS1 backend profile/data contract
        ├── WS2 frontend profile UX
        └── WS3 recall eligibility and config cleanup
              └── WS4 lead integration, migration/runtime evidence, docs, readiness
                    └── independent implementation audit
```

WS2 and WS3 may run in parallel only after WS1 publishes the final field names, validation semantics, and migration. WS4 owns shared integration seams and is never hidden inside another owner’s task.

### WS1 — Backend profile and data foundation

- Owner: `profile-backend-owner`
- Depends on: frozen plan, clean relevant write set, unchanged Alembic head
- Goal: R1-R3 and Python timezone-data foundation for R10

Steps:

1. Add the two constrained user columns and deterministic legacy-timezone normalization migration. Read distinct timezone keys, classify that bounded set in Python, and normalize invalid rows with set-based updates rather than loading every user row.
2. Add the unconditional `tzdata` runtime dependency, refresh `uv.lock`, and force both Python runtime images to use package data with `PYTHONTZPATH=""`.
3. Add a small timezone validation helper under `runestone.utils` using `zoneinfo`; keep package `__init__.py` empty.
4. Extend profile response/update schemas and `UserService` response/update validation.
5. Add API, service, schema, and migration-focused regressions, including strict primitive/null rejection, partial one-field updates, equal-window rejection, upgrade/downgrade scope, and normalization.
6. Hand the exact public field contract to WS2 and the current-user preference read contract to WS3.

### WS2 — Frontend profile UX

- Owner: `profile-frontend-owner`
- Depends on: WS1 contract handoff
- Goal: R3-R4 and browser portion of R10

Steps:

1. Add a selection-only timezone autocomplete backed by browser `Intl`, with `UTC`/saved/detected fallbacks.
2. Replace the existing timezone text input.
3. Add start/end hour selectors, helper text, local equality validation, and retain the existing form-level backend error display.
4. Extend auth/profile types and update payloads.
5. Add focused tests for searching/selecting, no free-text acceptance, fallback option construction, detected suggestion, saved-value retention, hour changes, overnight save, equal-hour rejection, and API payload/refresh behavior.

### WS3 — Recall policy and configuration cleanup

- Owner: `recall-delivery-owner`
- Depends on: WS1 contract handoff
- Goal: R5-R9

Steps:

1. Move delivery-window eligibility from `TelegramRecallDelivery` into the transport-independent recall use case.
2. Read the current user profile through `UserService` inside each per-user delivery session.
3. Implement UTC-aware `ZoneInfo` conversion and the ordinary/overnight predicate with defensive invalid-data handling.
4. Preserve queue, cursor, callback, commit, rollback, and per-user failure isolation behavior.
5. Remove global start/end settings from `Settings`, `.env` templates, unit fixtures, integration evidence, and delivery construction; retain interval scheduling.
6. Cover simultaneous users in different zones/windows at the same UTC instant in bounded unit/orchestration tests. Extend the guarded harness only for sequential preference changes to its one explicitly confirmed user.

### WS4 — Lead integration, documentation, and release evidence

- Owner: `timezone-plan-lead`
- Depends on: WS1-WS3 complete
- Goal: R10-R12 and shared seam verification

Steps:

1. Resolve contract integration only; do not absorb unowned feature work silently.
2. Reconcile README and recall persistence/integration documentation.
3. Verify the migration upgrade/downgrade/upgrade path on a disposable PostgreSQL database and record the DDL/update locking expectation.
4. Verify both built Python images have an empty `zoneinfo.TZPATH`, contain the locked `tzdata` version, and resolve representative IANA zones.
5. Run focused checks, full readiness, security, and container build gates.
6. Submit the plan, diff, ownership record, and evidence to an independent implementation auditor before finalisation.

## Exact Write-Set Manifest

No owner may write outside its set. A required additional path triggers plan reopen or an explicit lead-owned revision before the write.

### WS1 exclusive writes

- `alembic/versions/d4f6a8b0c2e1_add_user_recall_delivery_window.py` (new)
- `pyproject.toml`
- `uv.lock`
- `Dockerfile.backend`
- `Dockerfile.recall`
- `src/runestone/db/models.py`
- `src/runestone/utils/timezones.py` (new)
- `src/runestone/api/schemas.py`
- `src/runestone/services/user_service.py`
- `tests/api/test_user_endpoints.py`
- `tests/services/conftest.py`
- `tests/services/test_user_service.py`
- `integration_tests/migrations/verify_user_recall_delivery_window.py` (new)

### WS2 exclusive writes

- `frontend/src/components/auth/TimezoneAutocomplete.tsx` (new)
- `frontend/src/components/auth/TimezoneAutocomplete.test.tsx` (new)
- `frontend/src/components/auth/Profile.tsx`
- `frontend/src/components/auth/Profile.test.tsx`
- `frontend/src/hooks/useAuth.ts`
- `frontend/src/hooks/useAuth.test.tsx`
- `frontend/src/types/auth.ts`

### WS3 exclusive writes

- `src/runestone/recall/service.py`
- `src/runestone/telegram/delivery.py`
- `src/runestone/config.py`
- `tests/recall/test_service.py`
- `tests/telegram/test_delivery.py`
- `tests/test_config.py`
- `.env.example`
- `.env.test`
- `integration_tests/recall/run_recall_workflow.py`
- `integration_tests/recall/coverage_manifest.json`

### WS4 lead-owned integration writes

- `README.md`
- `docs/recall-state-persistence.md`
- `docs/recall-integration-test-plan.md`

### Planning-only file

- `docs/todo/user-profile-recall-timezone.md` — immutable after freeze; no implementation owner may edit it

## Read-only Inputs and Forbidden Writes

Read-only implementation inputs:

- `AGENTS.md`
- `recall_main.py`
- `src/runestone/recall/providers.py`
- `src/runestone/db/user_repository.py`
- `src/runestone/db/recall_repository.py`
- `src/runestone/recall/types.py`
- `src/runestone/api/user_endpoints.py`
- `frontend/src/components/auth/LanguageAutocomplete.tsx`
- `frontend/package.json`
- `frontend/package-lock.json`
- `Dockerfile.frontend`
- `docker-compose.yaml`
- `Makefile`
- existing Alembic revisions

Forbidden without plan reopen:

- changes to `recall_user_states` or recall queue schema;
- direct repository access from Telegram delivery or API transport;
- changes to scheduler job count or per-user scheduler jobs;
- a frontend timezone package or new API endpoint;
- changes to Telegram command/message behavior;
- changes to queue selection, learning metadata, cursor semantics, transaction providers, or session ownership;
- dependency, Dockerfile, deployment, or generated lockfile changes beyond the declared `tzdata`/`uv.lock`/`PYTHONTZPATH` scope;
- staging, reverting, or formatting unrelated branch work.

## Acceptance Criteria and Evidence Contract

| ID | Acceptance criterion | Requirements | Evidence |
| --- | --- | --- | --- |
| AC1 | Existing and new users have non-null `09`/`22` delivery defaults with database range and unequal checks. | R1 | E1, E2 |
| AC2 | Legacy empty/invalid timezones become `UTC`; valid IANA values survive migration. | R2 | E1, E2 |
| AC3 | `/api/me` returns and partially updates all three preferences, rejects invalid zones/hours/equal effective windows, and preserves unrelated fields. | R2, R3 | E2 |
| AC4 | Profile timezone is selection-only, searchable, includes saved/UTC/detected values, and works when `Intl.supportedValuesOf` is absent. | R4, R10 | E3 |
| AC5 | Profile start/end selectors submit integer hours, explain overnight semantics, allow overnight windows, and reject equality. | R4 | E3 |
| AC6 | At the same UTC instant, users in different zones are independently delivered or skipped according to their own windows. | R5, R8, R9 | E4, E5 |
| AC7 | Start is inclusive, end exclusive; ordinary and overnight boundaries are correct. | R5, R8 | E4 |
| AC8 | DST conversion uses aware UTC time and produces deterministic spring/fall eligibility without timezone exceptions. | R2, R8 | E4 |
| AC9 | Ineligible or corrupt-preference users cause no Telegram call, learning event, cursor advance, queue mutation, or sweep-wide failure. | R5, R6, R9 | E4, E5 |
| AC10 | Eligible delivery preserves the existing lock, callback, mutation, commit, rollback, and isolation sequence. | R6 | E4, E5 |
| AC11 | Global start/end settings have no production/config/documentation consumers; global interval scheduling remains unchanged. | R7 | E6 |
| AC12 | Both Python runtime images receive locked `tzdata`; frontend adds no timezone dependency. | R10 | E7, E9 |
| AC13 | Durable docs describe profile ownership, defaults, interval-versus-window semantics, overnight behavior, and UTC fallback. | R11 | E8 |
| AC14 | Focused suites, migration checks, readiness, security, container builds, scope inventory, and independent audit pass. | R12 | E1-E10 |

### E1 — Migration evidence

- Assert Alembic has one head before and after the new revision.
- Run upgrade → downgrade one revision → upgrade on a disposable database.
- Inspect `users` columns, defaults, constraints, valid timezone preservation, invalid timezone normalization, and downgrade scope.
- Do not use a production or shared non-test database.

Suggested disposable SQLite smoke command, followed by the PostgreSQL-backed migration test required for constraint truth:

```bash
rm -f /tmp/runestone_timezone_migration_check.db
DATABASE_URL=sqlite+aiosqlite:////tmp/runestone_timezone_migration_check.db UV_CACHE_DIR=.uv-cache uv run alembic upgrade head
```

### E2 — Backend profile regressions

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest \
  tests/api/test_user_endpoints.py \
  tests/services/test_user_service.py \
  -v
```

Include independent partial-update cases for start-only and end-only requests so equality is checked against persisted counterpart values.

### E3 — Frontend profile regressions

```bash
cd frontend
npm run test:run -- \
  src/components/auth/TimezoneAutocomplete.test.tsx \
  src/components/auth/Profile.test.tsx \
  src/hooks/useAuth.test.tsx
```

### E4 — Recall policy regressions

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest \
  tests/recall/test_service.py \
  tests/telegram/test_delivery.py \
  tests/test_recall_main.py \
  -v
```

Use fixed aware UTC instants. Required zones include `UTC`, `Europe/Helsinki`, and `America/New_York`; include ordinary, overnight, spring-forward, and fall-back fixtures.

### E5 — Guarded integration evidence

Extend the existing no-network recall harness and coverage manifest with:

- two enabled users evaluated at one UTC instant with opposite eligibility outcomes;
- preference change taking effect on the next evaluation;
- ineligible user state/queue fingerprint unchanged;
- one corrupt legacy preference failing closed/falling back without blocking the other user;
- post-run restoration of user profile preferences in addition to existing recall/vocabulary/offset restoration.

Preview and run only under the harness’s existing confirmation/restore contract. A real Telegram send is forbidden.

### E6 — Configuration and scheduler evidence

```bash
rg -n "recall_start_hour|recall_end_hour|RECALL_START_HOUR|RECALL_END_HOUR" \
  src recall_main.py tests integration_tests .env.example .env.test README.md docs
rg -n "recall_interval_minutes|RECALL_INTERVAL_MINUTES" \
  src recall_main.py tests .env.example .env.test README.md docs
```

The first command must return no live configuration/production references; migration/history references may be explicitly explained. The second must prove the interval remains wired to the one scheduled send job.

### E7 — Dependency and container evidence

```bash
UV_CACHE_DIR=.uv-cache uv lock --check
UV_CACHE_DIR=.uv-cache uv run python -c "from zoneinfo import ZoneInfo; [ZoneInfo(name) for name in ('UTC', 'Europe/Helsinki', 'America/New_York')]"
make security-check
make docker-build
```

`make docker-build` is the pre-release container gate because the backend and recall images independently copy the locked environment. If local Docker is unavailable, CI must run the equivalent three-image build before release; it cannot be reported as locally passed.

### E8 — Durable documentation evidence

```bash
rg -n "timezone|delivery window|09:00|22:00|RECALL_INTERVAL_MINUTES|UTC|overnight" \
  README.md docs/recall-state-persistence.md docs/recall-integration-test-plan.md
```

Reviewer confirms documentation distinguishes worker cadence from each user’s eligibility window.

### E9 — Standard readiness and diff hygiene

```bash
make check-readiness
git diff --check
git status --short
git diff --name-only
git ls-files --others --exclude-standard
```

Scope evidence must separate the task write set from pre-existing unrelated changes. A focused pass is not called a clean full gate when readiness or container checks have not run.

### E10 — Independent implementation audit

The reviewer receives the frozen plan, baseline/reopen record, exact diff, ownership log, E1-E9 outputs, and any unavailable-environment caveat. The reviewer checks requirement traceability, data migration, profile contract, DST/window behavior, transaction preservation, no-network evidence, container runtime support, forbidden writes, and release truthfulness before returning `READY`, `CHANGES_REQUIRED`, or `BLOCKED`.

## Preflight, Budgets, and Reopen Triggers

### Implementation preflight

```bash
git status --short
git branch --show-current
git rev-parse HEAD
UV_CACHE_DIR=.uv-cache uv run alembic heads
test ! -e alembic/versions/d4f6a8b0c2e1_add_user_recall_delivery_window.py
git diff --quiet -- <owner write-set paths>
git diff --cached --quiet -- <owner write-set paths>
```

Each owner must confirm exclusive ownership through the active orchestration mechanism; filesystem cleanliness alone does not prove another worker will not edit a path.

### Budgets

- WS1: one owner, one migration/API/dependency workstream, one focused correction round.
- WS2: one owner, one component/profile/type workstream, one focused correction round.
- WS3: one owner, one recall/config/integration-harness workstream, one focused correction round.
- WS4: lead-only seam integration and evidence, not a general implementation overflow owner.
- Plan review: one independent audit plus up to two correction rounds.
- Implementation review: one independent audit plus one focused correction round.
- Test retries: rerun only a failing focused gate after an in-scope fix; rerun readiness/security/container gates after focused suites pass.

### Small-context packet (`small-context-profile.v1`)

Every executor receives only:

- Plan Control;
- Clarification Log and Assumptions;
- Product Specification and relevant behavioral contract;
- Requirements assigned to its workstream;
- its workstream steps and exact write set;
- Read-only Inputs and Forbidden Writes;
- mapped acceptance criteria/evidence commands;
- `AGENTS.md` and the specific current-code anchors named in its packet.

Chat history is not implementation authority. Large files must be opened at relevant symbols/tests rather than read wholesale.

### Reopen triggers

Reopen and independently re-audit the plan if any of these occur:

- Alembic head changes from `8c3e4a1f2b7d` before implementation;
- `/api/me` field names or profile ownership changes;
- hour granularity, defaults, equal-window semantics, or DST behavior changes;
- per-user intervals, exact send times, weekday schedules, or a 24-hour mode enter scope;
- eligibility must move outside the recall use case or transaction lifecycle changes;
- browser support requires a timezone package or backend timezone-list endpoint;
- any implementation requires a write outside the manifest;
- runtime images cannot resolve IANA zones from the locked dependency;
- unrelated current work overlaps a write-set file;
- external network, production database, deployment, or real Telegram authority becomes necessary.

## Rollout and Rollback Safety

1. Merge and deploy code plus migration together; backend and recall containers both run Alembic on startup, so the migration must be idempotent under normal Alembic locking/ordering assumptions.
2. Deploying the migration first is backward-compatible because old code ignores the new columns and retains global settings. Deploying new recall code before the migration is not supported.
3. Before removing deployment environment variables, verify the new recall container is running the migrated code. Stale `RECALL_START_HOUR`/`RECALL_END_HOUR` values may remain temporarily because settings ignore extras, but they are no longer authoritative.
4. Observe logs for invalid preference fallback, per-user processing failures, and delivery volume by hour without logging message content or personal profile data beyond existing user IDs.
5. Code rollback is safe while the new columns remain. Do not downgrade the migration during an emergency rollback; old code can continue using its global window. Schema downgrade is a separate maintenance action after confirming no newer code reads the columns.
6. If delivery volume changes unexpectedly, stop/revert the recall container first. Profile writes and stored preferences can remain in place without causing sends.

## Plan Lock and Mutable Run Artifacts

Once this candidate reaches `READY_TO_FREEZE`, its plan ID, repository baseline, Alembic baseline, reviewed document digest, and revision become immutable authority. Implementation evidence, command output, diffs, ownership records, and audit results are mutable run artifacts stored outside this file.

If implementation needs a contract or ownership change, reopen the plan, create a new revision identity, and obtain independent plan review. Do not edit a frozen plan in place.

## Independent Plan Review Request

The independent reviewer must use the `audit-agent-plan` matrix and inspect this document against the repository planning baseline. Required output:

1. findings ordered by severity;
2. requirement → acceptance → workstream → evidence coverage matrix;
3. SDD tier and clarification/assumption assessment;
4. migration, DST, transaction, browser, dependency, release, and rollback risk assessment;
5. exact write ownership, overlap, DAG, budget, and small-context assessment;
6. validation command executability and sufficiency;
7. freeze verdict: `READY_TO_FREEZE`, `CHANGES_REQUIRED`, or `BLOCKED`;
8. exact edits for every non-ready finding.

## Review Record

Pending independent plan audit.
