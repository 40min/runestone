# Model Cost Tracking

Runestone logs operational estimates for paid model calls. This is lightweight
observability, not invoice reconciliation: costs can be exact, estimated, or
unknown, and reported amounts are known subtotals when any interaction is
unknown.

## Architecture And Schemas

The tracking path is deliberately one-way and content-free:

```text
PriceSnapshot / ModelPrice
          +
normalized provider usage
          |
          v
   CostCalculation
          |
          v
   InteractionRecord
          |
          v
_CostCollector through ContextVar
          |
          +---- CostTrackingHandle for owned detached work
          |
          v
stable interaction and summary log schemas
```

`PriceSnapshot` is the validated, immutable in-memory form of the local price
registry. Its `ModelPrice` entries identify a provider/model route, the source
and freshness of its prices, and normalized USD rates keyed by billing unit,
such as `input_token`, `output_token`, or `character`.

Provider adapters and LangChain callbacks convert returned usage into those
normalized units. `CostCalculation` then represents the known subtotal,
quality, and source for one paid attempt. A provider-reported request cost is
`exact`; normalized usage multiplied by a complete local rate is `estimated`;
missing usage, a missing route, or any required missing rate is `unknown`.

Each calculation becomes an `InteractionRecord`. The record contains only
operational identifiers, provider/model routing, terminal status, normalized
usage, known cost, quality, and source. It never contains request or response
content.

The private `_CostCollector` aggregates interaction records and owns the
preliminary, corrected, or final summary lifecycle. A `ContextVar` binds the
collector to the current asynchronous context, so ordinary awaited calls can
record interactions without passing tracking parameters through service and
provider APIs. Only application/use-case boundaries open tracking scopes.

Detached work needs an explicit ownership transfer because it can outlive its
creator. `track_model_costs_with_background()` yields a controller whose
`transfer()` method returns a `CostTrackingHandle`. The task owner transfers
the handle before scheduling, activates it for the whole paid task or stream,
and finishes it once. Providers do not receive handles.

Independent detached jobs must not accidentally inherit the creator's active
collector. `suspend_model_cost_tracking()` synchronously clears only the
model-cost `ContextVar` while `asyncio.create_task()` captures its context, then
restores the creator's binding. Every other context variable remains inherited.
The new task can therefore open its own `track_model_costs()` scope and emit an
independent summary without losing unrelated request context.

Finally, records are rendered into stable log schemas. Internal names may use
`operation` and `phase` as diagnostic fields, but these values are not threaded
through application APIs. Tracking, pricing, and logging are fail-open: a
tracking failure must not fail the user action.

## Price Registry

Runtime requests read only `state/model_prices.json`. They never contact a
pricing service and continue normally when the file is missing, stale, or
invalid; affected interactions are reported with unknown cost.

Refresh the registry with:

```bash
make update-model-prices
```

The command resolves configured model routes, fetches Models.dev once, uses
Portkey only for unresolved supported providers, validates the complete
snapshot, and atomically replaces the local file. The first successful refresh
creates the parent directory and a complete snapshot; an empty placeholder is
not required. Manual entries are preserved. When a configured route cannot be
refreshed, its previous entry is retained and marked stale. ElevenLabs prices
remain manual or unknown unless a validated source supplies the exact billing
unit. OpenAI streaming TTS exposes no response usage through the current SDK,
so Runestone records its input character count and reports unknown cost unless
the local snapshot contains a manual `character` rate for that model. Operator
output reports Models.dev and Portkey resolutions separately.

Application startup also schedules one best-effort refresh task. Startup does
not wait for it, refresh failures are logged without failing readiness, and the
last valid snapshot remains usable. Use a deployment scheduler such as cron or
a platform scheduled job to run the command once per day as the reliable
refresh mechanism. No refresh runs in a request path. Operators can validate
the live sources without replacing runtime state:

```bash
uv run python scripts/update-model-prices.py --check
```

Use `--output <path>` to write a validated inspection snapshot somewhere other
than `state/model_prices.json`.

## Log Contract

Each paid interaction emits a `DEBUG` record named
`model_cost_interaction`. It contains identifiers, provider/model route, phase,
terminal status, usage quantities, known USD cost, quality, price source, and
the normalized `applied_rates_usd` used for local estimation. Exact
provider-reported costs have an empty applied-rate map because no local rate was
used.
It never contains prompts, responses, transcripts, images, audio bytes, API
keys, or full provider payloads.

Application boundaries use `track_model_costs()` for ordinary awaited work and
`track_model_costs_with_background()` when one use case owns both awaited work
and detached paid work. Ordinary service and provider calls use the ambient
collector; they do not accept collector, operation, or foreground/background
parameters. Provider callbacks and direct voice clients call
`record_model_interaction()`. A paid provider call without active tracking
remains fail-open, emits a content-free warning, and is not silently counted
under a fabricated standalone scope.

Only an application/use-case boundary opens a scope. Ordinary awaited work
inherits that scope automatically. Independent background jobs open separate
`track_model_costs()` scopes and produce separate summaries, using
`suspend_model_cost_tracking()` around task creation when they are scheduled
from inside another tracked operation.

Awaited non-chat operations emit one `INFO` summary:

```text
model_cost stage=final operation=<type> operation_id=<id>
status=<completed|completed_with_errors|failed|timed_out|cancelled>
known_total_usd=<fixed-8-decimal amount>
cost_breakdown_usd={"<component>":"<fixed-8-decimal amount>"}
cost_quality=<exact|estimated|unknown>
exact_calls=<n> estimated_calls=<n> unknown_calls=<n>
```

The component breakdown is deterministic and aggregated across all interactions
represented by that summary. Preliminary summaries include foreground records;
corrected and final summaries include the complete applicable record set. USD
values are rendered with eight decimal places for log readability while all
internal arithmetic remains `Decimal` based.

When detached work belongs to the same use case, its owner obtains a
`CostTrackingHandle` from `track_model_costs_with_background()`, transfers the
handle before scheduling, activates it for the entire paid task or stream, and
finishes it exactly once. Successful chat turns emit a preliminary summary
after the assistant message is persisted, followed by a corrected summary
after owned post-turn work and optional TTS terminate. The existing log keys,
including `operation`, `operation_id`, and `phase`, remain stable diagnostics;
they are not parameters threaded through application APIs. A foreground
failure emits one final failure summary instead.

Quality is conservative:

- `exact`: the provider returned request cost;
- `estimated`: provider usage was multiplied by a local registry rate;
- `unknown`: usage or a required rate is missing, including cancelled work
  whose final provider usage was unavailable.

If any interaction is unknown, the whole operation is unknown even though
`known_total_usd` still reports the sum of known calls.

Provider failures and cancellations may still be billable. Adapters therefore
record the attempted interaction when possible. Returned usage or provider cost
is retained; otherwise the attempt is an unknown-cost interaction. Business
partial-success and fallback decisions remain owned by the relevant service and
do not manually finalize the common cost collector.

A TTS stream keeps its transferred `CostTrackingHandle` active for the whole
provider stream, not just stream creation. Completion and cancellation both
finish the handle exactly once. If cancellation prevents final provider usage
from being observed, the interaction is recorded with unknown cost rather than
being omitted or reported as zero.

## Limits And Recovery

Prices are list-price estimates. Discounts, credits, taxes, cached billing
rules not exposed by the provider, and invoice reconciliation are outside this
feature. Cost scopes are held in memory, so a process restart may lose an
unfinished corrected chat summary.

Tracking and logging failures are fail-open and must not fail the user action.
If cost tracking causes operational trouble:

1. preserve or remove `state/model_prices.json`; a missing file degrades costs
   to unknown without blocking requests;
2. roll back the application change if callback or lifecycle instrumentation is
   implicated;
3. restore the last known valid snapshot, then run the updater with `--check`;
4. inspect `model_cost` warnings and summaries without logging user content.

There is no usage ledger, database schema, dashboard, quota, or user billing in
this implementation.
