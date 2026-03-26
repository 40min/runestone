# Agent Swarm: Async Post Implementation Plan

This document is the implementation plan for the design in
[`AGENT_SWARM_ASYNC_POST_DESIGN.md`](/Users/40min/www/runestone/docs/AGENT_SWARM_ASYNC_POST_DESIGN.md).

It intentionally favors a small, incremental rollout.

Guiding principle:

- reduce user-visible latency
- keep most specialist work in pre stage
- preserve a coordinator-driven post stage
- avoid queue/worker infrastructure for now

## Goals

- return the teacher response before post-stage work completes
- keep post-stage analysis available for teacher-dependent actions
- keep grammar directly available to the teacher
- move clear specialist cases into pre stage
- detect stale post-stage work on the next turn
- fail stale post-stage work loudly instead of retrying it

## Non-Goals

- do not add durable background queues
- do not add automatic replay or retry
- do not add message-level linkage fields unless clearly needed later
- do not move grammar into a dedicated specialist in this iteration
- do not attempt to redesign every specialist at once

## Current Baseline

Today the main synchronous flow is:

1. save user message
2. run coordinator
3. run pre specialists
4. run teacher
5. run post specialists
6. persist post side effects
7. save assistant message
8. return response

The latency problem is caused by steps 5 and 6 staying on the critical path.

## Target Baseline

After this implementation, the main synchronous flow should be:

1. save user message
2. inspect previous post coordinator state for this chat
3. run coordinator for pre stage
4. run pre specialists
5. run teacher
6. save assistant message
7. create post coordinator tracking row
8. return response immediately
9. run post coordinator and post specialists in background

## Milestone 1: Lock the Contract

Deliverables:

- design note accepted as current direction
- implementation plan accepted
- terminology standardized on `coordinator`

Tasks:

- use `coordinator` consistently in docs and code comments
- mark the older exploratory phase-matching document as superseded if helpful
- keep the new async-post design doc as the source of truth

Success criteria:

- there is one clearly referenced design document and one implementation plan

## Milestone 2: Split Manager Into Sync and Async Phases

Deliverables:

- `AgentsManager` no longer blocks on post stage before returning teacher output

Tasks:

- refactor [`manager.py`](/Users/40min/www/runestone/src/runestone/agents/manager.py) into explicit stages:
  - pre coordination
  - pre specialist execution
  - teacher response generation
  - post coordination and post specialist execution
- make the synchronous return boundary happen immediately after teacher response generation
- preserve existing source extraction behavior

Suggested shape:

- `prepare_pre_turn(...)`
- `generate_teacher_response(...)`
- `run_post_turn(...)`

Success criteria:

- the manager can generate teacher output without awaiting post specialists

## Milestone 3: Move HTTP Return Boundary Earlier

Deliverables:

- assistant message is persisted before post stage finishes
- `/message` returns as soon as teacher output is saved

Tasks:

- update [`chat_service.py`](/Users/40min/www/runestone/src/runestone/services/chat_service.py) so it:
  - saves the user message
  - runs the synchronous pre + teacher path
  - saves the assistant message
  - starts background post work
  - returns immediately
- keep TTS push behavior non-blocking relative to post stage

Success criteria:

- post stage is no longer on the request latency path

## Milestone 4: Add Post Coordinator Tracking

Deliverables:

- post-stage lifecycle is persisted in side effects using a dedicated coordinator row

Tasks:

- extend side-effect handling so a coordinator tracking row can be created and updated
- use conventions:
  - `specialist_name="coordinator"`
  - `phase="post_response"`
  - `status in {"pending","running","done","failed"}`
- add service methods for:
  - create pending coordinator row
  - mark running
  - mark done
  - mark failed
  - load latest coordinator row for a chat
- ensure teacher-facing side-effect loading ignores coordinator tracking rows

Success criteria:

- post-stage status for a chat can be inspected independently from specialist result rows

## Milestone 5: Separate Cleanup Paths

Deliverables:

- coordinator lifecycle rows and post specialist rows are cleaned separately

Tasks:

- split cleanup logic in [`agent_side_effect_service.py`](/Users/40min/www/runestone/src/runestone/services/agent_side_effect_service.py)
- support:
  - coordinator-row replacement/cleanup
  - post specialist result replacement/cleanup
- avoid current “replace everything for post phase” behavior for mixed row kinds

Success criteria:

- writing fresh specialist results does not accidentally erase active coordinator tracking state

## Milestone 6: Add Background Task Registry

Deliverables:

- one in-memory task handle per active chat post stage

Tasks:

- add a small in-memory registry keyed by `chat_id`
- on background post start:
  - store task handle
  - wrap execution in a timeout
- on completion:
  - remove task handle from registry
- on cancellation:
  - remove task handle from registry
  - mark coordinator row failed if not already finalized

Success criteria:

- the app can cancel stale post work for a chat without inspecting OS processes

## Milestone 7: Add Next-Turn Check

Deliverables:

- stale previous post-stage work is detected at the beginning of the next turn

Tasks:

- before normal turn processing for a non-first message, inspect the latest post coordinator row for that chat
- if state is `done`, continue
- if state is `pending`, `running`, or `failed`:
  - log loudly
  - cancel in-memory task if still alive
  - mark state `failed` if needed
  - continue with the new turn
- do not retry, replay, or repair

Success criteria:

- stale post stage cannot survive indefinitely across user turns

## Milestone 8: Align Specialist Routing With New Policy

Deliverables:

- pre stage becomes the main specialist stage in practice, not only in docs

Tasks:

- keep `WordKeeper` pre for explicit student save requests
- keep `WordKeeper` eligible for post when derived from teacher reply
- shape news routing so:
  - known-topic requests go to pre
  - vague “some news” requests do not trigger specialist work yet
- add or refine memory specialists/policies so:
  - read-oriented work happens in pre
  - explicit student-requested writes can happen in pre
  - teacher-triggered persistence remains eligible for post
- keep grammar tools on the teacher

Success criteria:

- routing behavior matches the intended per-tool cases in the design doc

## Milestone 9: Simplify Teacher Prompt

Deliverables:

- teacher prompt reflects the new ownership split

Tasks:

- remove or reduce prompt instructions that still imply all persistence must happen synchronously in the teacher path
- preserve truthfulness rules
- preserve grammar tool usage instructions
- make it explicit when teacher may rely on pre specialist artifacts
- avoid implying post-stage success in the visible reply

Success criteria:

- prompt instructions no longer conflict with async post behavior

## Testing Plan

### Unit Tests

- coordinator tracking row lifecycle
- separated cleanup behavior
- background task registry add/remove/cancel behavior
- next-turn stale-state check
- prompt/routing tests for:
  - pre WordKeeper explicit save
  - post WordKeeper teacher-highlighted words
  - pre news with explicit topic
  - no news specialist for vague “some news”
  - pre memory read at chat start

### Integration Tests

- response is returned and assistant message saved before post stage completes
- post specialist rows are eventually written when background task succeeds
- stale background post task is cancelled on next turn
- failed post stage does not block the next turn
- teacher-visible recent side effects do not include coordinator tracking rows

### Regression Tests

- news sources still extract correctly from teacher/tool messages
- explicit save-word requests still allow truthful same-turn acknowledgement
- chat history remains clean and does not contain internal post-stage state
- grammar lookup still works directly from teacher tool usage

## Suggested Implementation Order

Implement in this order:

1. split manager flow
2. move `ChatService` return boundary earlier
3. add coordinator tracking row methods
4. separate cleanup paths
5. add in-memory task registry
6. add next-turn stale check
7. align routing/prompt behavior
8. add tests and tighten logs

This order reduces risk because it first creates the new execution seam, then adds state tracking, then adds cancellation/inspection behavior.

## Logging Requirements

All new log lines should stay grep-friendly.

Recommended prefixes:

- `[agents:manager]` for sync/async orchestration flow
- `[agents:coordinator]` for coordinator planning
- `[agents:side-effects]` for coordinator row lifecycle and cleanup
- `[agents:post-task]` for background task creation, timeout, cancellation, and finish

Important events to log:

- post coordinator row created
- post task started
- post task timed out
- post task cancelled on next turn
- coordinator row marked done
- coordinator row marked failed

## Risks

### Risk: Late Background Write Interferes With Newer State

Mitigation:

- use the active coordinator row as the handle for the current post cycle
- keep coordinator cleanup separate from specialist cleanup

### Risk: Prompt Still Assumes Synchronous Persistence

Mitigation:

- update teacher prompt after the orchestration seam is in place
- add regression tests for truthfulness language

### Risk: Background Tasks Leak or Linger

Mitigation:

- track one task per chat
- enforce timeout
- cancel on next-turn stale detection
- remove finished or cancelled tasks from registry

### Risk: Too Much Change at Once

Mitigation:

- keep grammar untouched
- keep no-retry policy
- do not introduce queue infrastructure
- land in small milestones

## Done Criteria

This implementation is considered complete when:

- user-visible response latency no longer includes post-stage execution
- post coordinator state is visible in side effects
- stale post stage is failed and cancelled on next turn
- no automatic repair/retry exists
- grammar remains teacher-owned
- the implemented routing behavior matches the documented cases
