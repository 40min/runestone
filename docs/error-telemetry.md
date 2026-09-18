# Error Telemetry Policy

How Runestone exports error events to Better Stack (Sentry-compatible) without
leaking secrets or personal data. Implemented in
`src/runestone/core/error_tracking.py`. Only the standalone Rune Recall entry
point may additionally use the SDK's `isolation_scope()` to delimit a scheduled
job; Telegram modules never touch the SDK directly.

## Design

Two SDK callbacks enforce a default-deny policy:

- `before_send=_sanitize_event` — **rebuilds** every event from the allowlist
  below into a new dict. Nothing is redacted in place and no unknown section is
  copied. Anything not listed is dropped, so a new SDK field cannot become
  exported by upgrading the dependency.
- `before_breadcrumb=_sanitize_breadcrumb` — admits a breadcrumb only from a
  `runestone`/`runestone.*` logger record at `WARNING`/`ERROR`/`CRITICAL` that
  carries a valid `runestone_telemetry` mapping (see the breadcrumb contract).
  The event projection repeats breadcrumb validation before export, so later
  SDK processing cannot bypass the policy.

`capture_sanitized_exception()` is the sole application helper for explicitly
capturing a handled boundary failure. It accepts only the exception object and
relies on `before_send` to rebuild the resulting event from the same allowlist;
callers must not attach exception text, request data, or other untrusted fields.
Services never import the Sentry SDK directly.

## Fail-closed behavior

- An event that serializes to more than **128 KiB**, or that triggers any
  unexpected projection failure, is dropped (`before_send` returns `None`).
- A malformed mandatory structure (for example a broken exception chain) omits
  that structure, not the whole event.
- Neither callback ever logs: a log emission would recurse back into the SDK.
- The breadcrumb callback body is fully wrapped in `try/except` because
  sentry-sdk 2.68.1 fails **open** on an escaping `before_breadcrumb`
  exception and would retain the original unsanitized breadcrumb.
- Hostile input objects are never mutated.
- Explicit capture is best-effort: `capture_sanitized_exception()` captures only
  when the SDK is initialized and suppresses its own failures, so telemetry
  cannot change the application's outcome.

## Event allowlist

| Output path | Rule |
| --- | --- |
| `event_id` | 32-char hex |
| `timestamp` | UTC ISO-8601; omit if invalid |
| `platform` | exactly `python` |
| `level` | one of `debug`/`info`/`warning`/`error`/`critical`/`fatal` |
| `logger` | `runestone` or `runestone.*` only, ≤128 chars; otherwise omitted |
| `release`, `environment` | shape-checked strings from configured SDK options |
| `exception.values[]` | ≤3 entries, each only `type`, `module`, `mechanism.type`, `mechanism.handled`, and stacktrace frames — no `value`/`message` |
| `exception.values[].stacktrace.frames[]` | last 50 frames, each only `filename` (relative, no leading `/`, no `..` or empty segments), `module`, `function`, `lineno`, `in_app` — no `vars`, no absolute paths, no source context |
| `request.method` | `[A-Z]{3,16}` |
| `transaction` | route template only, and only when the SDK source is `route` or `component` |
| `contexts.runestone.status_code` | integer `100..599` (a three-digit string is parsed; other coercion rejected) |
| `contexts.runestone.request_id` | exactly 32 lowercase hex characters (see request correlation below) |
| `breadcrumbs.values[]` | ≤20 entries, each passing the breadcrumb contract |

Validator details:

- exception `type`/`module`: `[A-Za-z_][A-Za-z0-9_.]{0,127}`
- `mechanism.type`: `[a-z][a-z0-9_.-]{0,31}`; `mechanism.handled`: boolean
- frame `function`: `[A-Za-z0-9_.<>-]{1,200}`; `lineno`: integer `1..10_000_000`; `in_app`: boolean
- `release`: `[A-Za-z0-9._:/@-]{1,128}`; `environment`: `[A-Za-z0-9._-]{1,64}`
- route template: `^/[A-Za-z0-9_{}./:-]{0,199}$`, `/` is the sole valid root,
  and `?`/`#`/`%`/`//`/`..`/empty segments are rejected
- `request_id`: `^[0-9a-f]{32}$` exactly; any other value is omitted

The exported `contexts.runestone` dict is a **validated union** of
scope-injected fields (`request_id`) and event-level fields (`status_code`);
it is never a wholesale replacement of the dict, so both fields survive when
both are present.

Explicitly dropped: exception values/messages, `logentry`, `user`, `extra`,
arbitrary `tags`/`contexts`, stack `vars`, absolute paths, source context,
attachments, audio bytes, transcripts and other text payloads, WebSocket
payloads, authentication data, user IDs, and every unknown or future field.

## Breadcrumb contract

A breadcrumb is admitted only when **all** of the following hold:

1. The callback's `hint["log_record"]` is a `LogRecord` from a
   `runestone`/`runestone.*` logger.
2. The record level is `WARNING`, `ERROR`, or `CRITICAL`.
3. The record carries a `runestone_telemetry` mapping with a valid `operation`.

The returned breadcrumb is rebuilt solely from validated fields: the original
formatted message, `msg`, `args`, and `exc_info` are discarded. `message`
equals `operation`, type is `log`, level/category are validated, and the SDK
timestamp is preserved. Non-log and framework breadcrumbs are dropped.

Allowed `runestone_telemetry` fields:

| Field | Rule |
| --- | --- |
| `operation` (message) | `[a-z][a-z0-9_]{0,63}` — mandatory |
| `route_template` | same route-template rule as `transaction` |
| `provider` | one of `openai`, `openrouter`, `gemini`, `elevenlabs` — only ever from application configuration, never request data or exception text |
| `model` | config-sourced, `[A-Za-z0-9._:/-]`, ≤128 chars |
| `duration_bucket` | one of `lt_100ms`, `100ms_1s`, `1s_5s`, `5s_30s`, `gte_30s` |
| `retry_count` | integer `0..10` |
| `outcome` | `[a-z][a-z0-9_]{0,47}` |
| `status_code` | same status rule as the event field |

Fields that fail validation are dropped individually; an invalid `operation`
drops the whole breadcrumb.

## Database and startup boundaries

`record_database_boundary_failure(operation, exception, started_at)` in
`src/runestone/db/database.py` instruments two database boundaries, emitting a
marked breadcrumb only when they fail: `database_startup_check` from
`setup_database` (database readiness at application startup) and
`recall_transaction` from the Recall API's outer request-owned transaction
rollback paths. The marker contains a fixed operation,
`failed` outcome, and duration bucket. It never contains SQL, connection URLs,
table names, row identifiers, migration details, exception messages, or user
data. The same handled exception is captured in the same startup or request
lifecycle, so the event's exception type and stack frames carry the failure
identity; the marker does not duplicate it through a coarser classification.
A startup breadcrumb is not expected to survive into a later request.
Capturing and marker projection are best-effort; they run after rollback where
applicable and cannot alter transaction ownership, the HTTP response, or
startup failure behavior. This failure-only policy bounds volume; these paths
do not infer retries, so they do not emit a retry count. In addition to the
marker, `setup_database` logs `Database setup check failed` with
`exc_info=True`, so startup failures stay diagnosable in private local logs
when no DSN is configured.

## Rune Recall worker

`recall_main.py` initializes the existing error-tracking policy immediately
after worker logging setup. It reuses the configured DSN and environment but
derives a separate release as `runestone-recall@<revision>` only when the
configured value is exactly `runestone-api@` followed by a lowercase 40-hex
source commit. `Dockerfile.recall` receives `SOURCE_COMMIT` and sets that
backend-style configured release in the image environment. Missing, wrong-process, URL-like,
token-shaped, or malformed configuration deliberately becomes the fixed
`runestone-recall@unknown` value rather than copying configuration text. An
empty `SENTRY_DSN` still disables initialization entirely.

Each APScheduler polling and scheduled-recall invocation opens its own
`sentry_sdk.isolation_scope()`. This keeps concurrent and consecutive jobs from
sharing breadcrumbs or context without creating a worker correlation ID. An
escaped job failure is explicitly captured once in that job's scope; failures
that the normal polling or delivery flow handles remain bounded breadcrumbs so
one problematic user cannot turn into one event per retry.

| Boundary | Marker |
| --- | --- |
| polling offset read/write | `telegram_poll_offset_read` / `telegram_poll_offset_write`, `failed`, duration bucket |
| polling transport, API rejection, or parse failure | `telegram_poll_fetch`, `telegram_poll_api`, or `telegram_poll_parse`, `failed`, duration bucket; an HTTP transport failure includes only its response `status_code` |
| per-command transaction failure | `telegram_command_transaction`, `failed` or `retryable_failure`, duration bucket |
| command response delivery failure | `telegram_command_response_delivery`, `failed`, duration bucket |
| scheduled recall workflow failure | `telegram_recall_delivery`, `failed`, duration bucket |
| scheduled recall message delivery failure | `telegram_recall_message_delivery`, `failed`, duration bucket; an authoritative HTTP response includes only `status_code` |
| scheduled delivery queue replacement falls back to additional alternatives | `recall_queue_refill`, `fallback_alternative`, duration bucket |
| scheduled delivery has an invalid user timezone and uses UTC | `recall_delivery_timezone`, `fallback_utc`, duration bucket |
| escaped polling or scheduled-delivery job failure | `telegram_poll_job` or `telegram_recall_delivery_job`, `failed`, duration bucket, plus one sanitized exception event |

These markers contain no user/chat/update IDs, usernames, vocabulary, message
payloads, Telegram response bodies, URLs, bot tokens, exception text, or
timezone details. Worker code has no authoritative attempt ordinal at its
boundaries, so it omits `retry_count` rather than inventing one. The existing
20-breadcrumb event cap still applies; the scheduler also limits each job to
one active instance, and there are no success markers.

### Canary and rollback

Before enabling a production worker DSN, use a non-production worker with its
own DSN and release, trigger a controlled scheduled-job exception containing a
hostile sentinel, and verify the received event has only the fixed marker,
exception type/relative frames, and worker release. Confirm that the sentinel,
Telegram data, URLs, and token-shaped text are absent. Remove `SENTRY_DSN`
from the worker deployment and restart it to stop exports immediately. A code
rollback reverts the worker initialization, isolation wrappers, and worker
markers together; the shared sanitizer stays in place.

## Breadcrumb producers

The existing agent/OCR producers continue to carry their markers. The voice
pipeline adds markers at four owned failure/degradation boundaries. Markers
carry only fixed operation and outcome labels, provider/model values from
configuration, and a measured `duration_bucket`:

| Producer | Marker fields |
| --- | --- |
| `agents/manager.py::prepare_pre_turn` coordinator fallback | `operation=coordinator_plan`, `outcome=fallback_teacher_only`, configured coordinator provider/model |
| `agents/manager.py::generate_teacher_response` re-raised teacher failure | `operation=teacher_response`, `outcome=failed`, configured teacher provider/model |
| `core/ocr.py::_preprocess_image_for_ocr` recoverable fallback | `operation=ocr_preprocess`, `outcome=fallback_original` |
| `core/ocr.py::extract_text` `OCRError` exit | `operation=ocr_extract`, `outcome=failed`, configured OCR provider/model |
| `core/ocr.py::extract_text` first unexpected-exception record | `operation=ocr_extract`, `outcome=failed`, configured OCR provider/model |
| `services/voice_service.py::transcribe_audio` | `operation=voice_transcription`, `outcome=empty_result` or `failed`, configured transcription provider/model, measured duration bucket |
| `services/voice_service.py::enhance_text` | `operation=voice_enhancement`, `outcome=fallback_original`, configured OpenAI enhancement model, measured duration bucket |
| `services/tts_service.py::synthesize_speech_stream` | `operation=tts_synthesis`, `outcome=failed`, configured TTS provider/model, measured duration bucket |
| `services/tts_service.py::_stream_audio_task` | `operation=audio_delivery`, `outcome=failed`, configured TTS provider/model, measured duration bucket |
| `api/auth_endpoints.py::register` unexpected failure | `operation=auth_register`, `outcome=failed`, `route_template=/api/auth/register`, `status_code=500` |
| `api/auth_endpoints.py::login` unexpected failure | `operation=auth_login`, `outcome=failed`, `route_template=/api/auth/`, `status_code=500` |
| `auth/dependencies.py::get_current_user` unexpected token-resolution failure | `operation=auth_token_validation`, `outcome=failed`, `status_code=500` |
| `api/user_endpoints.py::update_user_profile` unexpected failure | `operation=profile_update`, `outcome=failed`, `route_template=/api/me`, `status_code=500` |

Voice/audio markers never contain audio bytes, transcripts, enhanced or source
text, WebSocket payloads, authentication data, user IDs, exception values, or
counts derived from user content. `duration_bucket` is measured from a monotonic
start time and contains only one of the bounded labels in the field table.
`retry_count` remains validator-only: no producer has an authoritative value,
and inventing one is worse than omitting it.

### Authentication decision and expected volume

Authentication markers describe unexpected server failures only. Registration
validation, duplicate accounts, invalid credentials, invalid or missing tokens,
inactive users, and authorization rejections are ordinary client outcomes: they
produce no marker and no explicit Better Stack event. The token-resolution
boundary has no fixed route template because it protects multiple routes; its
operation and fixed 500 status still distinguish it from a client rejection.

At normal volume, an unexpected re-raised authentication failure produces one
automatic Sentry event with one breadcrumb. The handled profile-update 500 is
captured once by the SDK's FastAPI integration with its preceding breadcrumb and
the original exception type/frames;
the endpoint does not explicitly capture it and therefore cannot duplicate the
event. This excludes credential spraying and invalid-token traffic from error quota. The producer
markers contain only fixed code-owned strings and integer 500: never email,
username, password, token/JWT, account ID, IP, user agent, headers, cookies,
request values, rejection detail, or exception text. This boundary is approved
only by the hostile-envelope and real-SDK tests that accompany it.

### Detached TTS failures

`TTSService` runs delivery in a detached task. Its done callback consumes
`task.result()`; if that raises, it passes the exception object to
`capture_sanitized_exception()`. This is the only explicit capture at that
boundary, and it occurs while the exception is still available. The captured
event and its `tts_synthesis` breadcrumb pass through the same default-deny
event and breadcrumb projections. Audio, transcript text, WebSocket data,
authentication data, user IDs, and exception values remain excluded. The
service imports the core helper, never the Sentry SDK.

### INFO decision

INFO breadcrumbs stay disabled. The breadcrumb admission contract accepts only
`WARNING`/`ERROR`/`CRITICAL` records; a marked INFO record is excluded even
when it carries a valid marker (covered by a real-SDK test). No current
diagnostic case justifies admitting every INFO record to the SDK callback.

## Request correlation

`RequestCorrelationMiddleware` (registered in `create_application()`) generates
one `uuid.uuid4().hex` value per HTTP request scope and binds it to Sentry's
per-request isolation scope as `contexts.runestone.request_id`. The middleware
never removes the context itself: the context must stay installed for the whole
request so exceptions that escape the middleware are still captured with the ID
by Sentry's outer ASGI integration. Cleanup relies on that integration
discarding its per-request isolation scope (sentry-sdk 2.68.1 creates and
clears one per ASGI request), which both prevents the ID leaking into the next
request and keeps it available for automatic exception capture; the middleware
must therefore run inside the SDK's ASGI lifecycle. It merges the ID into any
pre-existing `runestone` context instead of replacing it.

- The ID is generated **internally only**: inbound correlation values are never
  accepted, no response header is exposed, and the ID is never correlated with
  users or sessions. Its diagnostic value is correlating multiple error events
  raised inside one request scope (for example a handled 500 plus a late
  background-task failure).
- The same ID is bound to a request-scoped `ContextVar`
  (`runestone.core.logging_config`) and rendered as a `request_id=<hex>`
  suffix on **local** log lines by `RunestoneLogFormatter` while the request is
  in flight. This binding is unconditional for HTTP requests, so private logs
  correlate even when error tracking is disabled (no DSN, the documented local
  development default). This is private-log correlation only: the exported
  event still carries the ID solely through the validated
  `contexts.runestone.request_id` rule above, and breadcrumb/log messages
  remain discarded by the sanitizer. The `ContextVar` is reset with its token
  when the request scope exits, so later logs in the same task carry no ID.
- Detached background tasks created during a request intentionally inherit the
  ID: `asyncio` tasks copy the current context at creation, so a task spawned
  mid-request logs with that request's ID for its lifetime, including after
  the response is returned. The token reset restores only the requesting
  task's context, not the child's copy.
- WebSocket and lifespan scopes pass through without an ID.
- When the SDK is not initialized, the local-log binding above still applies;
  only the Sentry scope binding is skipped, so no ambient Sentry state is
  mutated.
- The ID reaches export only through the validated
  `contexts.runestone.request_id` rule above; request IDs via tags, log
  messages, headers, or request data are dropped.

## Volume and quota

The 128 KiB per-event cap is enforced in code and tested; a fully populated
event (bounded by 20 sanitized crumbs at maximum field sizes) serializes to
roughly 17 KiB.

Quota impact (from Better Stack's own pricing page,
https://betterstack.com/pricing): error tracking includes 100,000 exceptions
per month; additional exceptions are billed at $0.000050 per exception, with
90-day retention. This is a per-event cost, not a hard ceiling: sustained error
volume raises cost even though Better Stack's adaptive spike protection samples
bursts above an application's baseline to keep ingest volume near expected
levels
(https://betterstack.com/docs/errors/using-the-product/spike-protection/).
Spike protection reduces unexpected cost growth from error loops; it does not
cap billing for a consistently elevated error rate.

## SDK options

`setup_error_tracking` initializes the SDK with `send_default_pii=False`,
`include_local_variables=False`, `max_request_body_size="never"`,
`traces_sample_rate=0.0`, `auto_session_tracking=False`, `enable_logs=False`,
`max_breadcrumbs=20`, and an inert-except-breadcrumbs
`LoggingIntegration(level=WARNING, event_level=None, sentry_logs_level=None,
capture_sentry_logs=False)`. Envelopes therefore contain event items only —
no transaction, session, log, or replay items.

## Extending the allowlist

The allowlist is the single gate between production code and Better Stack, so
changes must be deliberate:

- **New `runestone_telemetry` key**: add it to `_project_telemetry_fields`, the
  breadcrumb table above, and the tests. An unknown key is dropped silently —
  nothing fails — so a producer emitting an unlisted field simply never sees
  it in Better Stack.
- **New provider**: update `_PROVIDERS`, the provider configuration-Literal
  regression test, and this table together. The allowlist currently covers the
  configured LLM providers and the `elevenlabs` voice/TTS provider; an
  unrecognized `provider` is dropped from breadcrumbs.
- **New `operation`/`outcome` values**: keep them lowercase snake_case; a value
  outside the pattern drops the whole breadcrumb, not just the field.
- **Breadcrumb producers**: a producer must log from a `runestone`/`runestone.*`
  logger at `WARNING`+ with a valid `runestone_telemetry` marker; anything else
  is dropped by the admission contract. Build markers from fixed labels,
  configuration, and bounded measurements only; never derive marker fields
  from audio, text, a WebSocket, authentication, a user, or an exception.

## Residual risk

By design, the exported event still reveals application shape: exception type
and module names, relative stack-frame paths and function names, route
templates, and configured provider/model names. No DSN, token, user data,
prompt content, or chat text is exported; exception values/messages and
breadcrumb messages are dropped precisely because they may embed user data or
secrets.
