# Error Telemetry Policy

How Runestone exports error events to Better Stack (Sentry-compatible) without
leaking secrets or personal data. Implemented in
`src/runestone/core/error_tracking.py`; no other module may touch the Sentry
SDK.

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
| `breadcrumbs.values[]` | ≤20 entries, each passing the breadcrumb contract |

Validator details:

- exception `type`/`module`: `[A-Za-z_][A-Za-z0-9_.]{0,127}`
- `mechanism.type`: `[a-z][a-z0-9_.-]{0,31}`; `mechanism.handled`: boolean
- frame `function`: `[A-Za-z0-9_.<>-]{1,200}`; `lineno`: integer `1..10_000_000`; `in_app`: boolean
- `release`: `[A-Za-z0-9._:/@-]{1,128}`; `environment`: `[A-Za-z0-9._-]{1,64}`
- route template: `^/[A-Za-z0-9_{}./:-]{0,199}$`, `/` is the sole valid root,
  and `?`/`#`/`%`/`//`/`..`/empty segments are rejected

Explicitly dropped: exception values/messages, `logentry`, `user`, `extra`,
arbitrary `tags`/`contexts`, stack `vars`, absolute paths, source context,
attachments, and every unknown or future field.

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
| `provider` | one of `openai`, `openrouter`, `gemini` — only ever from application configuration, never request data or exception text |
| `model` | config-sourced, `[A-Za-z0-9._:/-]`, ≤128 chars |
| `duration_bucket` | one of `lt_100ms`, `100ms_1s`, `1s_5s`, `5s_30s`, `gte_30s` |
| `retry_count` | integer `0..10` |
| `outcome` | `[a-z][a-z0-9_]{0,47}` |
| `status_code` | same status rule as the event field |

Fields that fail validation are dropped individually; an invalid `operation`
drops the whole breadcrumb.

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
- **New LLM provider**: adding a provider to the config Literals is guarded by
  `test_breadcrumb_provider_allowlist_covers_configured_llm_providers`, which
  fails until `_PROVIDERS` is updated (an unrecognized `provider` would be
  dropped from breadcrumbs). Voice/TTS providers are a separate domain and out
  of scope.
- **New `operation`/`outcome` values**: keep them lowercase snake_case; a value
  outside the pattern drops the whole breadcrumb, not just the field.
- **Breadcrumb producers**: a producer must log from a `runestone`/`runestone.*`
  logger at `WARNING`+ with a valid `runestone_telemetry` marker; anything else
  is dropped by the admission contract.

## Residual risk

By design, the exported event still reveals application shape: exception type
and module names, relative stack-frame paths and function names, route
templates, and configured provider/model names. No DSN, token, user data,
prompt content, or chat text is exported; exception values/messages and
breadcrumb messages are dropped precisely because they may embed user data or
secrets.
