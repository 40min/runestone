# Agent Swarm Memory Maintenance Plan

## Purpose

Define the follow-up extraction for memory maintenance without moving routine memory reading away from `TeacherAgent`.

## Accepted Design Changes

### 1. Keep Memory Reading on the Teacher Side

`MemoryReader` is no longer the target extraction.

Rationale:

- memory reading is not complex enough to justify a separate specialist today
- the teacher may need to inspect memory directly and intentionally during a turn
- keeping `start_student_info` and filtered `read_memory` on `TeacherAgent` preserves flexibility

### 2. Keep `start_student_info` Compact

The start-of-chat memory load should remain intentionally small:

- include active `personal_info`
- include only the top 5 `area_to_improve` items across `struggling` and `improving`
- rank those items by priority first, then recency
- rely on filtered `read_memory` if the teacher wants to inspect more items

This keeps the default prompt small while still surfacing the most urgent study topics.

### 3. Move Memory Maintenance to Post Phase

The complicated work is not memory reading. It is memory review and maintenance.

That work should run only in `post_response` because:

- it depends on the actual teacher reply, not a guessed future reply
- it may take several tool calls and should not delay the student response
- it needs a careful review loop for status and priority changes

## Problem Statement

Current memory writes are additive more often than corrective:

- the teacher sometimes creates new topics
- existing `area_to_improve` items often keep stale status and stale priority
- improvement or regression may be visible in the turn, but the memory is not updated to reflect it

This is most harmful for `area_to_improve`, where the system should continuously reflect:

- whether the student is still struggling
- whether the student is improving
- whether the topic has become urgent or less urgent
- whether the topic is mastered and ready to be promoted

## Proposed Scope

Create a post-stage memory maintenance specialist, likely still named `MemoryKeeper`, with this narrower role:

- review durable learning signals after the teacher reply is known
- inspect relevant memory items on demand
- update `area_to_improve` content, status, and priority when the turn provides evidence
- create new study topics when the teacher identifies a new recurring issue
- promote mastered topics to `knowledge_strength`

Out of scope for this extraction:

- replacing `TeacherAgent` as the normal reader of memory
- moving `start_student_info` away from the teacher
- running memory maintenance synchronously before the response

## Triggering Principle

The strongest signal for maintenance should come from what the teacher explicitly identified in the turn.

Examples:

- the teacher points out repeated mistakes on a topic
- the teacher notes visible improvement on a topic
- the teacher confirms mastery
- the teacher introduces a new durable area to improve

Avoid blind churn:

- do not rewrite priorities every turn without evidence
- do not infer mastery from weak signals
- do not delete memory unless the student explicitly asks or confirms an item is wrong

## Planned Maintenance Actions

For `area_to_improve`, the post-stage reviewer should be able to choose among:

- `no_action`
- `create_item`
- `update_content`
- `update_status`
- `update_priority`
- `update_status_and_priority`
- `promote_to_strength`

For `personal_info` and `knowledge_strength`, changes should stay conservative and mostly follow explicit facts or explicit corrections.

## Proposed Post-Phase Workflow

1. `TeacherAgent` responds to the student as usual.
2. The post coordinator decides whether memory maintenance is warranted for this turn.
3. `MemoryKeeper` loads only the relevant memory items it needs to inspect.
4. `MemoryKeeper` compares the turn evidence with the current memory state.
5. `MemoryKeeper` applies updates for status, priority, promotion, or creation.
6. The resulting side effects are persisted as post-stage outcomes.

## Area-To-Improve Review Rules

Initial review rules to implement:

- repeated or reinforced struggle should keep the item in `struggling` and may increase urgency by lowering the numeric priority
- visible progress should move the item toward `improving` and may lower urgency by raising the numeric priority
- confirmed mastery should move the item to `mastered` and then promote it to `knowledge_strength`
- new issues identified by the teacher should create a fresh `area_to_improve` item with an explicit initial priority

These rules should be applied only when the turn contains a meaningful signal, not by default.

## Implementation Phases

### Phase 1: Retrieval Tightening

- keep `start_student_info` compact
- document that larger memory review remains on-demand via filtered reads

### Phase 2: Contract and Routing

- define when post-stage routing should trigger memory maintenance
- define the structured output expected from `MemoryKeeper`
- keep the teacher prompt aligned with the new ownership boundaries

### Phase 3: Update Engine

- support create/update/status/priority/promote flows
- ensure updates are idempotent enough for a single post-stage run
- log why an item changed, especially for status and priority moves

### Phase 4: Test Coverage

- creation of new `area_to_improve` items
- status upgrade and downgrade flows
- priority increase and decrease flows
- mastered-to-strength promotion
- no-action cases when evidence is too weak

## Success Criteria

- the default teacher prompt sees only the most relevant study issues at chat start
- `TeacherAgent` can still inspect more memory when needed
- `area_to_improve` stops drifting into stale status and stale priority
- progress and regression mentioned by the teacher can change memory during post phase
- memory maintenance becomes testable independently from teacher response generation
