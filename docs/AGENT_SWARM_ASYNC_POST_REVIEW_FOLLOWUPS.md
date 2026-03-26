# Agent Swarm Async Post: Review Follow-Ups

This document captures the concrete follow-up work after reviewing:

- [`AGENT_SWARM_ASYNC_POST_DESIGN.md`](/Users/40min/www/runestone/docs/AGENT_SWARM_ASYNC_POST_DESIGN.md)
- [`AGENT_SWARM_ASYNC_POST_IMPLEMENTATION_PLAN.md`](/Users/40min/www/runestone/docs/AGENT_SWARM_ASYNC_POST_IMPLEMENTATION_PLAN.md)
- resolved implementation plan at `/Users/40min/.gemini/antigravity/brain/23b5f95e-64ae-4901-ba7b-8a347b82a1be/implementation_plan.md.resolved`
- current code and tests
- renewed general docs:
  - [`AGENT_SWARM_PLAN.md`](/Users/40min/www/runestone/docs/AGENT_SWARM_PLAN.md)
  - [`AGENT_SWARM_CONTRACT.md`](/Users/40min/www/runestone/docs/AGENT_SWARM_CONTRACT.md)

It is intended as a practical next-step checklist, not as a replacement source of truth.

## Status

All required follow-up items in this document are now fixed.

The canonical architecture source of truth is [`AGENT_SWARM_CONTRACT.md`](/Users/40min/www/runestone/docs/AGENT_SWARM_CONTRACT.md).

## Current Assessment

Implemented well:

- sync/async manager split exists
- assistant response is saved before post-stage completion
- post-stage coordinator tracking rows exist
- coordinator rows are excluded from teacher-facing side effects
- background post tasks are tracked in memory
- next-turn stale check exists
- image flow also uses async post handling

Fixed from the earlier review:

- post-stage routing now replans from the actual teacher reply
- stale background writes are guarded against newer coordinator cycles
- general agent docs were merged back into a single SoT and aligned with the accepted async-post architecture

## Required Fixes

### 1. Add Real Post-Stage Replanning [FIXED]

Requirement:

- the post stage must run the coordinator again after the teacher response is known

Why:

- this is the central design decision in the async-post SoT
- teacher-dependent actions cannot be determined reliably from the pre-turn alone

Current problem:

- [`AgentsManager.run_post_turn()`](/Users/40min/www/runestone/src/runestone/agents/manager.py#L187) executes `plan.post_response` from the earlier pre-turn plan
- there is no second `coordinator.plan(...)` call using the teacher reply

Expected behavior:

1. pre-turn coordinator decides only pre specialists
2. teacher responds
3. post-turn coordinator runs again using:
   - latest user message
   - recent history
   - actual teacher response
   - available post specialists
4. only then are post specialists executed

Recommended implementation shape:

- keep separate coordinator entry points for clarity, for example:
  - `plan_pre_turn(...)`
  - `plan_post_turn(...)`


### 2. Make Coordinator Prompt Stage-Specific [FIXED]

Recommendation:

- yes, the coordinator should be told explicitly which routing stage it is planning right now

Why this is better:

- it removes ambiguity from the prompt
- it lets the same coordinator model behave differently in pre and post without guessing
- it reduces invalid plans like post-only logic leaking into pre planning or vice versa
- it aligns naturally with the SoT, which treats pre and post as separate decisions

Recommended contract:

- when planning `pre_response`:
  - only produce `pre_response`
  - keep `post_response` empty
  - do not speculate about the future teacher reply
- when planning `post_response`:
  - only produce `post_response`
  - keep `pre_response` empty
  - use the actual teacher reply as a primary signal

Recommended prompt changes:

- add an explicit input field such as `current_stage`
- provide stage-specific rules:
  - `pre_response`: explicit user fast paths, retrieval, memory reads, known-topic news
  - `post_response`: teacher-derived persistence actions such as highlighted vocabulary
- forbid anticipatory post routing during pre-stage planning

This would be a better fit than the current prompt text in
[`coordinator.py`](/Users/40min/www/runestone/src/runestone/agents/coordinator.py#L17),
which currently asks one plan to decide both pre and post in advance.

### 3. Guard Against Late Writes From Stale Background Tasks [FIXED]

Requirement:

- the original stale-task handling design remains the primary behavior
- a stale background post task must not be able to overwrite specialist results from a newer post cycle

Current problem:

- [`replace_post_specialist_results()`](/Users/40min/www/runestone/src/runestone/services/agent_side_effect_service.py#L137) replaces rows by `chat_id`
- `_register_post_task()` replaces the task handle but does not cancel the old task first
- there is no validation that the writing task still owns the active coordinator row

Original intended protection:

- before processing the next user turn for the same `chat_id`, inspect coordinator state
- if previous coordinator work is not `done` or `failed`, log loudly
- try to cancel the prior task from the registry
- mark stale coordinator state `failed` if needed

Why that is not always sufficient:

- task cancellation is cooperative
- a previously cancelled task may still reach the persistence step if it is already far enough along

Recommended protection:

- keep the next-turn stale-task check as the main control point
- make `_register_post_task()` cancel any previous live task before replacing the handle
- optionally use the current coordinator row id as a write-time ownership token for the post cycle
- before replacing post specialist rows, verify that the current task's coordinator row is still the latest row for the chat
- if not current anymore, skip all writes and log loudly

Good enough minimal hardening rule:

- `run_post_turn()` may only persist results if `coordinator_row_id == latest_coordinator_row.id`

This should be treated as a safety net around the original design, not as a replacement for the next-turn check.

### 4. Separate Doc SoT From Future Roadmap [FIXED]

Requirement:

- general agent docs should reflect the currently accepted async-post design without introducing unapproved roadmap steps as if they were part of the same commitment

Current problems:

- [`AGENT_SWARM_PLAN.md`](/Users/40min/www/runestone/docs/AGENT_SWARM_PLAN.md#L92) adds MemoryReader/MemoryKeeper/NewsAgent/prompt-reduction milestones beyond the accepted async-post scope
- [`AGENT_SWARM_CONTRACT.md`](/Users/40min/www/runestone/docs/AGENT_SWARM_CONTRACT.md#L55) says teacher tools are transitional with a target of no tools
- [`AGENT_SWARM_CONTRACT.md`](/Users/40min/www/runestone/docs/AGENT_SWARM_CONTRACT.md#L300) mentions `GrammarAgent`, which does not exist and conflicts with the SoT
- [`AGENT_SWARM_CONTRACT.md`](/Users/40min/www/runestone/docs/AGENT_SWARM_CONTRACT.md#L288) describes post-stage coordinator replanning as if already implemented

Required corrections:

- keep grammar teacher-owned in the contract and remove any implication that a grammar specialist exists
- distinguish clearly between:
  - implemented now
  - accepted next work
  - possible future work
- describe post-stage coordinator replanning as required work until it is actually implemented

## Coverage Review

Targeted suite run:

```bash
uv run pytest tests/agents/test_manager.py tests/agents/test_coordinator.py tests/services/test_agent_side_effect_service.py tests/services/test_chat_service.py tests/api/test_chat_endpoints.py -q
```

Result:

- 70 tests passed

Relevant file coverage from that run:

- [`manager.py`](/Users/40min/www/runestone/src/runestone/agents/manager.py): 81%
- [`chat_service.py`](/Users/40min/www/runestone/src/runestone/services/chat_service.py): 86%
- [`agent_side_effect_service.py`](/Users/40min/www/runestone/src/runestone/services/agent_side_effect_service.py): 91%
- [`coordinator.py`](/Users/40min/www/runestone/src/runestone/agents/coordinator.py): 100%
- [`agent_side_effect_repository.py`](/Users/40min/www/runestone/src/runestone/db/agent_side_effect_repository.py): 44%
- [`memory_reader.py`](/Users/40min/www/runestone/src/runestone/agents/specialists/memory_reader.py): 0% in this targeted run

Interpretation:

- surface-level orchestration is reasonably covered
- the high-risk async correctness paths are not covered deeply enough
- repository coverage is especially thin for the new coordinator-row behavior

## Missing Tests

The highest-priority gaps listed in this section have now been covered by tests.

### Highest Priority [FIXED]

- post-stage coordinator replans from the actual teacher response
- pre-stage planning does not precompute post specialists based on anticipated teacher behavior
- stale task with old `coordinator_row_id` is prevented from replacing newer post specialist rows
- replacing a live post task handle cannot leave the old task writing results afterward

### Service / Repository [FIXED]

- repository test for `create_coordinator_row()`
- repository test for `update_coordinator_status()`
- repository test for `get_latest_coordinator_row()`
- repository test for `delete_coordinator_rows()`
- service/repository coverage now verifies that teacher-facing side effect queries still exclude coordinator rows after mixed writes

### Chat / Integration [FIXED]

- response returns before a deliberately slow post task finishes
- stale next-turn cancellation with a real live task, not only mocks
- timed-out post task cannot later mark the row done
- image-message flow returns before post-stage completion and preserves the same stale-task semantics

### Prompt / Routing [FIXED]

- coordinator prompt test for stage-specific planning rules once implemented
- regression test that vague news requests do not route a news specialist
- regression test that teacher-highlighted vocabulary only routes in post-stage planning
- regression test that grammar remains teacher-owned and is absent from coordinator routing rules

## Suggested Delivery Order

1. implement stage-specific coordinator planning
2. add real post-stage replanning from the teacher reply
3. add coordinator-row ownership guard before post-result persistence
4. tighten docs to match actual accepted scope
5. add missing async race and repository tests

## Acceptance Criteria For Follow-Up Work

Status: fixed.

- post specialists are chosen from the real teacher response, not from anticipation
- stale post tasks cannot overwrite newer post results
- docs no longer imply a grammar specialist or teacher-with-no-tools target unless re-approved
- coverage includes at least one integration test for real asynchronous overlap and stale-task prevention

## Design Cleanup

The architecture source of truth was consolidated into [`AGENT_SWARM_CONTRACT.md`](/Users/40min/www/runestone/docs/AGENT_SWARM_CONTRACT.md). The background task registry still lives in `AgentsManager`, but that extraction note remains an optional cleanup direction rather than an unresolved required fix.

### Extract Background Task Registry From `AgentsManager`

Observation:

- the background task registry currently lives inside
  [`manager.py`](/Users/40min/www/runestone/src/runestone/agents/manager.py#L233)
- `AgentsManager` already owns coordinator calls, teacher calls, specialist fan-out, source extraction, and async post orchestration

Concern:

- task-registry responsibilities are infrastructure concerns, not core orchestration policy
- keeping them inside `AgentsManager` makes the class broader and harder to reason about
- registry behavior becomes harder to test independently

Recommended direction:

- extract a small dedicated entity, for example:
  - `PostTaskRegistry`
  - `PostTurnTaskManager`
  - `ChatPostTaskRegistry`

Responsibilities of that component:

- store one active task per `chat_id`
- cancel and replace an existing task when required
- unregister completed tasks
- expose narrow methods such as:
  - `register(chat_id, task) -> None`
  - `cancel(chat_id) -> bool`
  - `pop(chat_id) -> asyncio.Task | None`
  - `get(chat_id) -> asyncio.Task | None`

Benefits:

- `AgentsManager` stays focused on planning and orchestration
- next-turn stale handling becomes easier to express clearly
- registry race behavior can be unit-tested without mocking the whole manager
