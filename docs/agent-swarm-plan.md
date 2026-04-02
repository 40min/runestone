# Agent Swarm Implementation Plan

## Purpose

Replace the current single teacher-agent model with a coordinator plus specialist agents so tool use becomes more reliable, prompts stay narrow, and each domain can evolve without overloading one system prompt.

## Completed Milestones (MS1–MS4)

The following were delivered in `feat/agent-swarm-ms1` through `feat/agent-swarm-ms4`:

- **MS1**: Introduced specialist interfaces, `SpecialistResult` schema, `agents/specialists/` package, `[agents:<component>]` log convention.
- **MS2**: Split `AgentService` → `AgentsManager` + `TeacherAgent` as first specialist.
- **MS3**: Introduced `CoordinatorAgent` for pre/post orchestration with structured `CoordinatorPlan`, concurrent specialist fan-out, and `agent_side_effects` persistence.
- **MS4**: Extracted `WordKeeper` specialist; pre-response fast path for explicit save requests; post-response path for teacher-highlighted vocabulary.

## Design Direction (Post-MS4)

After MS4 the team rethought the synchronous post-stage execution. The new direction is:

- pre-stage becomes the primary specialist stage
- grammar tools remain directly available to the teacher (no specialist)
- post stage is preserved but runs **asynchronously** in the background
- student is not blocked on post-stage latency
- no queues, no retries, no replay loops

Full design rationale: [`AGENT_SWARM_ASYNC_POST_DESIGN.md`](AGENT_SWARM_ASYNC_POST_DESIGN.md)

Implementation details are now consolidated into this document and [`agent-swarm-architecture.md`](agent-swarm-architecture.md).

## Active Milestones (Async Post Redesign)

### Milestone 1: Lock the Contract

- [x] Design doc accepted as current direction
- [x] Implementation plan accepted
- [x] Docs renewed (this file + `agent-swarm-architecture.md`)

### Milestone 2: Split Manager Into Sync and Async Phases

Refactor `manager.py` into explicit stage methods:

- `prepare_pre_turn()` – coordinator plan + pre specialists + side effect load
- `generate_teacher_response()` – teacher only
- `run_post_turn()` – post coordinator replanning + post specialists + persist

Return boundary moves to after `generate_teacher_response()`.

### Milestone 3: Move HTTP Return Boundary Earlier

Update `chat_service.py` to:

1. Save user message
2. Check previous post coordinator state (next-turn hook)
3. Run sync pre + teacher path
4. Save assistant message
5. Create post coordinator tracking row (`pending`)
6. **Return response immediately**
7. Fire background `run_post_turn()`

Applies to both `process_message()` and `process_image_message()`.

### Milestone 4: Add Post Coordinator Tracking

Reuse `agent_side_effects` table with `specialist_name="coordinator"`.
Add service methods: create pending row, mark running/done/failed, load latest.
`load_recent_for_teacher` must exclude coordinator rows.

### Milestone 5: Separate Cleanup Paths

Split cleanup so coordinator rows and specialist result rows are managed independently.
Remove `replace_post_response_side_effects()`; replace with:
- `cleanup_coordinator_rows()`
- `replace_post_specialist_results()`

### Milestone 6: Background Task Registry

In-memory dict keyed by `chat_id`. One `asyncio.Task` per active post stage.
Timeout: 15 seconds. Cancel on next-turn stale detection.

### Milestone 7: Next-Turn Check

Before processing any non-first user turn, inspect the latest coordinator row.
If stale (`pending`/`running`/`failed`): log loudly, cancel task, mark failed, continue.

### Milestone 8: Align Specialist Routing

Update coordinator prompt:
- WordKeeper eligible for `post_response` when teacher highlights vocabulary
- News routing: known topic → pre; vague request → skip
- Remove any grammar-specialist routing mentions

## Follow-Up Corrections (Fixed)

The async-post follow-up corrections have now been implemented:

- rerun the coordinator after the teacher response is known
- make coordinator prompting explicitly stage-specific
- guard post-result persistence with coordinator-row ownership checks
- add async overlap and stale-writer coverage

## Possible Future Work

The items below are exploratory roadmap ideas, not part of the accepted async-post commitment.

### Memory Maintenance Extraction

Deliverables:

- keep memory reading with `TeacherAgent`
- extract post-response memory maintenance into a dedicated plan and implementation track

Tasks:

- inject compact starter memory from the service layer on first turn
- keep `read_memory` available for on-demand teacher inspection
- plan post-stage `MemoryKeeper` review rules for create/update/status/priority/promote/no-action
- capture the design in the architecture and plan docs

Success criteria:

- teacher retains direct memory access when needed
- memory maintenance becomes independently testable
- `area_to_improve` can reflect progress and regression after post-stage review

### NewsAgent Extraction

Deliverables:

- reference and retrieval domains become specialists

Tasks:

- create `NewsAgent`
- ensure `NewsAgent` can read selected sources via `read_url` when needed
- add source/result schemas

Success criteria:

- teacher only routes and composes

### Teacher Prompt Reduction

Deliverables:

- slim teacher prompt
- improve reliability through narrower responsibilities

Tasks:

- strip memory and vocabulary tool details out of main teacher prompt
- keep only routing and composition instructions
- keep persona, tone, and truthfulness requirements

Success criteria:

- teacher prompt is substantially shorter and easier to maintain

## Architecture Summary

```
user message
    → Coordinator (pre plan)
    → Pre Specialists (parallel)
    → Teacher
    → [HTTP response returned]
    ↓ (background)
    → Coordinator (post plan)
    → Post Specialists (parallel)
    → Side effects persisted
```

## Logging Conventions

All agent log lines use `[agents:<component>]` prefix.

- `[agents:manager]` – orchestration flow
- `[agents:coordinator]` – coordinator planning
- `[agents:side-effects]` – side effect lifecycle
- `[agents:post-task]` – background task events

## Tool Access Policy (Current)

| Agent              | Tools                                         |
| ------------------ | --------------------------------------------- |
| `TeacherAgent`     | grammar tools + `read_url` + memory tools     |
| `CoordinatorAgent` | none (planning only)                          |
| `WordKeeper`       | `prioritize_words_for_learning`               |
| `MemoryKeeper`     | memory maintenance tools (future, post phase) |
| `NewsAgent`        | `search_news_with_dates`, `read_url` (future) |

## Non-Goals (Unchanged)

- No unrestricted free-form agent swarm
- No multiple agents generating final user-facing replies
- No automatic retry or replay loops
- No durable background queues
