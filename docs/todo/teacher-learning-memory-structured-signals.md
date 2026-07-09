# Teacher Learning Memory Structured Signals

Ticket: <https://app.dartai.com/t/DfcQ4Rhsn2ml-bugfix-keep-Teacher-prompt>

## Context

`WordKeeper` already receives a reliable structured channel from `TeacherOutput.vocabulary_candidates`.

`LearningMemoryKeeper` is different today:

- Teacher still exposes durability hints inside visible student-facing prose
- Python parses `[memory:area_to_improve:<id>]` from `teacher_response`
- untagged learning signals are still inferred from teacher wording

That bridge works, but it is brittle:

- students see internal tags
- tag syntax is not validated at the Teacher schema boundary
- post-phase learning-memory handling still depends too much on parsing visible prose

At the same time, memory cannot become a pure Teacher-owned direct-write channel.
We still need `LearningMemoryKeeper` as an interpreter and authorizer because:

- some valid learning signals are new issues and have no existing id
- Teacher may describe improvement/mastery but fail to identify the exact item id
- Python must continue to own allowlisting, ambiguity handling, and persistence

## Goals

- move Teacher -> learning-memory signaling into structured output
- keep support for untagged but durable learning signals
- validate memory tags against the exact legacy format
- preserve Python-side authorization and bounded writes
- remove the need to leak internal tags into the student-visible message

## Non-Goals

- letting Teacher emit executable memory mutations directly
- removing `LearningMemoryKeeper`
- broadening memory tags beyond `area_to_improve`
- redesigning `personal_info` memory in this pass

## Options Considered

### 1) Keep visible tags and only add validators

Pros:

- smallest code diff

Cons:

- students still see internal syntax
- structured-output migration remains incomplete
- `teacher_response` prose is still the primary machine channel

Verdict:

- not enough

### 2) Make Teacher emit full memory mutations directly

Pros:

- less inference work in `LearningMemoryKeeper`

Cons:

- pushes too much business logic and item targeting into Teacher
- higher risk of hallucinated ids, conflicting updates, or over-eager writes
- breaks the current Python-owned authorization boundary

Verdict:

- reject

### 3) Recommended: bounded structured signals plus `LearningMemoryKeeper` orchestration

Pros:

- matches the successful Teacher -> WordKeeper pattern
- keeps Teacher responsible for declaration, not execution
- keeps `LearningMemoryKeeper` available for untagged, ambiguous, or new-item cases
- allows strict validation for legacy-style tags without exposing them to the student

Verdict:

- recommended

## Recommended Contract

Add a new optional field to `TeacherOutput`:

```python
class LearningMemorySignal(BaseModel):
    signal_type: Literal[
        "new_issue",
        "improving",
        "mastered",
        "regressed",
        "content_correction",
    ]
    summary: str
    memory_id: int | None = None


class TeacherOutput(BaseModel):
    message: str
    emotion: TeacherEmotion = DEFAULT_TEACHER_EMOTION
    grammar_source_urls: list[str] | None = None
    vocabulary_candidates: list[WordSaveCandidate] = Field(default_factory=list)
    learning_memory_signals: list[LearningMemorySignal] = Field(default_factory=list)
```

Design intent:

- `message` stays the only student-facing text
- `learning_memory_signals` is invisible side-effect metadata
- the field is bounded and descriptive, not an executable mutation plan
- Teacher-owned signal types are intentionally non-destructive
- student-requested learning-memory edits are still routed by Coordinator

This is intentionally narrower than a full memory-write schema. Teacher declares
the learning signal; `LearningMemoryKeeper` still interprets and applies it.
Destructive or parameterized operations such as `delete`, `replace`, and
`reprioritize` stay out of the signal enum for now because `summary` plus an
optional tag is not enough structure to express them safely. Student-initiated
learning-memory edits are intentionally out of scope for this migration.

## Validator Rules

Suggested validation rules:

- trim `summary`
- reject empty `summary`
- reject non-positive `memory_id`
- reject `memory_id` for `signal_type="new_issue"`
- cap `learning_memory_signals` at 3 per turn
- deduplicate identical `(signal_type, summary, memory_id)` entries

## Manager And Routing Changes

`WordKeeper` currently gets a direct post-response branch when
`vocabulary_candidates` is non-empty. Learning memory should stay
coordinator-routable for explicit student edit requests, while teacher-emitted
structured signals remain deterministically enforced by manager.

Recommended behavior:

- coordinator post-turn routing may select `learning_memory_keeper` for explicit
  student requests to update stored learning progress
- if `learning_memory_signals` is non-empty, the manager appends
  `learning_memory_keeper` to the coordinator post plan if it is not already present

Why this boundary matters:

- Coordinator keeps ownership of language understanding for student edit requests
- manager keeps ownership of the deterministic "teacher emitted signals must run" guarantee

Coordinator behavior:

- keep `learning_memory_keeper` in coordinator post-turn availability
- add prompt instructions for explicit student edit requests to tracked learning topics
- keep manager-side post-plan normalization so teacher signals still run deterministically

Logging:

- when Teacher emits `learning_memory_signals`, log the count and signal types
  at the manager boundary
- when manager appends `learning_memory_keeper` from structured signals, log
  the normalization reason and whether any `memory_id` values were present
- when `LearningMemoryKeeper` applies or skips the signals, log the final
  outcome, operation counts, changed ids, and no-op/error reason
- never log raw student-facing `message` text solely to observe these signals;
  prefer counts, signal types, tag ids, and bounded summaries

## LearningMemoryKeeper Input Changes

Extend specialist context/payload so structured signals become the primary input.

Recommended payload shape:

```json
{
  "student_message": "...",
  "teacher_response": "...",
  "learning_memory_signals": [
    {
      "signal_type": "improving",
      "summary": "The student is improving with article choice.",
      "memory_id": 42
    }
  ],
  "target_memory_ids": [42],
  "existing_targets": [...]
}
```

Behavior:

- derive `target_memory_ids` from validated structured `memory_id` values
- keep `teacher_response` available as secondary context, not the primary machine channel
- keep the existing Python allowlist and ambiguity protections
- continue loading targeted ids through the current user/category allowlist before
  allowing mutations

Interpretation policy:

- tagged signals use the current fast path
- untagged `new_issue` signals may create/upsert
- untagged improvement/mastery/regression/content-correction signals may reconcile against
  `existing_targets`
- ambiguous references still resolve to `no_action`
- delete and reprioritize are not supported in this migration

## Teacher Prompt Changes

Update the Teacher prompt so the durable signal moves out of visible prose.

New prompt direction:

- keep writing natural student-facing feedback in `message`
- when a durable learning-memory event exists, also fill
  `learning_memory_signals`
- only include `memory_id` when the exact numeric id is present in available
  memory context
- never expose internal ids or memory syntax in `message`

Runtime guard:

- do not rely on student-facing `message` text for memory routing or id transport

Example:

```json
{
  "message": "Nice progress. Article choice is getting better, but let's keep practicing.",
  "learning_memory_signals": [
    {
      "signal_type": "improving",
      "summary": "The student is improving with Swedish article choice.",
      "memory_id": 42
    }
  ]
}
```

For a new issue:

```json
{
  "message": "Watch the verb-second rule here.",
  "learning_memory_signals": [
    {
      "signal_type": "new_issue",
      "summary": "Recurring issue: the student struggles with verb-second word order in main clauses."
    }
  ]
}
```

## Rollout Plan

### Phase 1: Schema And Plumbing

- add `LearningMemorySignal` and `TeacherOutput.learning_memory_signals`
- add validators and unit tests
- add a no-leak guard for legacy tags in student-facing Teacher messages
- thread the field through `TeacherGenerationResult`, `generate_teacher_response`,
  `process_turn`, `start_background_post_turn`, `run_post_turn`, manager direct
  routing, and specialist context

### Phase 2: Post-Phase Consumption

- make manager directly route `learning_memory_keeper` when structured signals exist
- remove `learning_memory_keeper` from coordinator post-turn availability,
  coordinator prompts, and coordinator routing tests
- add manager and keeper logs for emitted signal counts, signal types, tag ids,
  routing, and final apply/no-op outcomes
- make `LearningMemoryKeeper` consume structured signals as first-class input
- keep current target allowlisting and mutation bounds unchanged

### Phase 3: Prompt Migration

- update Teacher prompt to populate `learning_memory_signals`
- stop instructing Teacher to append visible `[memory:area_to_improve:<id>]` tags
- keep prompt language explicit that `delete` and `reprioritize` are not
  supported learning-memory signals in this pass

## Test Plan

Backend tests to add or update:

- `tests/agents/test_teacher.py`
  - `TeacherOutput` accepts valid `learning_memory_signals`
  - invalid `memory_id` is rejected
  - `new_issue` with `memory_id` is rejected
- `tests/agents/test_manager.py`
  - direct post-turn routing occurs for non-empty `learning_memory_signals`
  - coordinator post-turn routing includes `learning_memory_keeper` for explicit student edit requests
  - manager appends `learning_memory_keeper` when structured signals are non-empty
  - `learning_memory_signals` propagate through `generate_teacher_response`,
    `process_turn`, `start_background_post_turn`, and `run_post_turn`
- `tests/agents/test_coordinator.py`
  - coordinator prompt describes `learning_memory_keeper` for explicit student edit requests
- `tests/agents/specialists/test_learning_memory_keeper.py`
  - structured ids become `target_memory_ids`
  - untagged structured signals still allow bounded create/reconcile behavior
  - Teacher-emitted destructive or reprioritization signal types are not accepted
  - structured signal runs expose useful outcome artifacts for logging assertions

## Affected Files

- `src/runestone/agents/schemas.py`
- `src/runestone/agents/specialists/teacher.py`
- `src/runestone/agents/manager.py`
- `src/runestone/agents/specialists/base.py`
- `src/runestone/agents/specialists/learning_memory_keeper.py`
- `tests/agents/test_teacher.py`
- `tests/agents/test_manager.py`
- `tests/agents/specialists/test_learning_memory_keeper.py`
- `docs/agent-swarm-architecture.md`

## Recommended Decision

Implement option 3.

The key boundary should be:

- Teacher emits bounded structured learning-memory signals
- `LearningMemoryKeeper` remains the post-response orchestrator and executor
- Python validates positive `memory_id` values and owns all id authorization

That gets us the same reliability win we already use for `WordKeeper`, without
losing the reconciliation layer that learning-memory still needs.
