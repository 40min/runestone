# Agent Swarm Implementation Plan

## Purpose

Replace the current single teacher-agent model with a coordinator plus specialist agents so tool use becomes more reliable, prompts stay narrow, and each domain can evolve without overloading one system prompt.

This document is the implementation plan.

Architecture, contracts, orchestration flow, and logging conventions live in `AGENT_SWARM_CONTRACT.md`.

## Problem Statement

The current `AgentService` (to be renamed to `AgentsManager`) asks one agent to do all of the following in a single turn:

- teach Swedish naturally
- decide when to read or write memory
- decide when to save useful vocabulary
- decide when to search grammar references
- decide when to search news
- decide when to read URLs

This creates several issues:

- prompt overload: too many responsibilities compete for attention
- weak operational discipline: the agent chats well but may skip tools
- poor observability: difficult to tell whether a domain rule failed or was never considered
- poor scalability: every new tool makes the same agent less reliable

## Goals

- Keep the teacher experience natural and conversational.
- Move domain-specific tool reasoning into specialist agents.
- Make vocabulary and memory persistence more reliable.
- Keep each specialist prompt small, narrow, and testable.
- Preserve the ability for a domain agent to decide whether action is needed.
- Add structured outputs so orchestration is deterministic even when specialist reasoning is not.

## Non-Goals

- Do not build an unrestricted free-form agent swarm.
- Do not let multiple agents independently generate final user-facing replies.
- Do not give all agents full tool access.
- Do not rewrite the entire chat stack in one step.

## Architecture (Summary)

See `AGENT_SWARM_CONTRACT.md` for the full contract and flow.

Key design decisions for v1:

- `read_url` remains a direct tool (invoked by `CoordinatorAgent` and/or retrieval specialists), not by `TeacherAgent`.
- Coordinator is an LLM agent (not a hardcoded policy layer).
- Post-response specialist results are persisted as internal "agent side effects" records; do not rewrite the already-sent teacher reply.

## Implementation Plan

### Milestone 1: Introduce Specialist Interfaces

Deliverables:

- add a shared structured result schema for specialist outputs
- add a base specialist interface
- keep current `AgentService`/`AgentsManager` user-visible behavior unchanged

Tasks:

- rename `agent` -> `agents`
- rename `AgentService` -> `AgentsManager` to emphasize multi-agent ownership
- create `agents/specialists/` package
- define `SpecialistResult` schema
- define specialist invocation interface
- add logging shape for specialist runs
- add `[agents:<component>]` prefix convention for all coordinator/specialist logs

Success criteria:

- can instantiate a specialist and return a structured `no_action`

### Milestone 2: Split Manager and TeacherAgent

Deliverables:

- rename the manager model module to `manager.py`
- decouple the teacher implementation from `AgentsManager`
- introduce `TeacherAgent` as the first specialist

Tasks:

- rename `runestone/agents/service.py` -> `runestone/agents/manager.py`
- update imports to use `runestone.agents.manager`
- extract teacher prompt + execution into `TeacherAgent` specialist
- have `AgentsManager` call `TeacherAgent` directly (no coordinator yet)
- keep user-visible behavior unchanged

Success criteria:

- `AgentsManager` and `TeacherAgent` are separate components
- `TeacherAgent` can be invoked independently in tests

### Milestone 3: Introduce Coordinator for Pre/Post Orchestration

Deliverables:

- replace direct all-tools teacher path with coordinator + teacher
- enable pre- and post-response specialist execution

Tasks:

- create routing policy
- add specialist registry
- implement phased fan-out/fan-in orchestration
- add teacher input bundle creation
- preserve existing source extraction behavior for news

Success criteria:

- same user-facing chat endpoint, but internals run coordinator plus specialists
- coordinator can execute pre/post phases deterministically

### Milestone 4: Extract WordKeeper

Deliverables:

- move vocabulary responsibility out of the teacher prompt
- `WordKeeper` owns `prioritize_words_for_learning`

Tasks:

- create `WordKeeper` prompt and service
- wire `WordKeeper` into the `post-response` phase
- add a `pre-response` fast path for explicit "save this word" user commands (so the teacher can confirm truthfully in the same turn)
- remove word-saving policy from teacher agent prompt or reduce it to routing guidance
- add structured tests for:
  - explicit save requests
  - useful word discovered in normal conversation
  - no-action cases
  - tool failure propagation

Success criteria:

- word-saving behavior can be tested without invoking the teacher prompt

### Milestone 5: Extract MemoryReader and MemoryKeeper

Deliverables:

- isolate memory responsibilities from teacher prompt
- split pre-response retrieval from post-response persistence

Tasks:

- create `MemoryReader`
- create `MemoryKeeper`
- move memory read policy into `MemoryReader`
- move memory write policy into `MemoryKeeper`
- add tests for read relevance, create/update/delete/promote/no-action

Success criteria:

- teacher no longer owns memory tool rules directly
- memory retrieval and memory persistence are independently testable

### Milestone 6: Extract NewsAgent

Deliverables:

- news reference and retrieval becomes a specialist

Tasks:

- create `NewsAgent`
- ensure `NewsAgent` can read selected sources via `read_url` when needed
- add source/result schemas

Success criteria:

- teacher routes news retrieval through `NewsAgent`

### Milestone 7: Extract GrammarAgent

Deliverables:

- grammar reference and retrieval becomes a specialist

Tasks:

- create `GrammarAgent`
- add source/result schemas

Success criteria:

- teacher routes grammar retrieval through `GrammarAgent`

### Milestone 8: Reduce Monolithic Prompt

Deliverables:

- slim teacher prompt
- improve reliability through narrower responsibilities

Tasks:

- strip memory and vocabulary tool details out of main teacher prompt
- keep only routing and composition instructions
- keep persona, tone, and truthfulness requirements

Success criteria:

- teacher prompt is substantially shorter and easier to maintain

## Logging and Observability

See `AGENT_SWARM_CONTRACT.md` for the log contract and examples.

Implementation requirement:

- prefix every coordinator/specialist log line with `[agents:<component>]` so it is easy to grep.

## Testing Strategy

### Unit Tests

- specialist prompt contract tests
- routing tests
- result-schema tests
- failure handling tests

### Integration Tests

- coordinator invokes correct specialists for representative turns
- specialists do not over-trigger
- successful specialist actions affect final response language correctly
- persistence claims are never made without successful tool results

### Regression Tests

- useful-word capture during normal conversation
- explicit "save this word" behavior
- memory creation for durable student facts
- news lookup only when relevant

## Risks

### Risk: Over-Engineering Into an Unmanageable Swarm

Mitigation:

- use one coordinator and a small fixed set of specialists
- no arbitrary agent-to-agent chat
- no shared ownership across domains

### Risk: Latency Increase

Mitigation:

- only invoke specialists when routed
- parallelize independent specialists
- keep specialist context windows short

### Risk: Duplicate or Conflicting Behavior

Mitigation:

- strict domain ownership
- structured contracts
- one final response generator

### Risk: Routing Drift

Mitigation:

- explicit routing tests
- routing logs
- start with a small specialist set

## Migration Strategy

Implement incrementally without breaking the public chat interface.

Step 1:

- add specialist framework behind existing `AgentService` (renaming it to `AgentsManager` as part of this step)

Step 2:

- rename manager module to `manager.py` and extract `TeacherAgent` as the first specialist

Step 3:

- introduce `CoordinatorAgent` and phased pre/post execution

Step 4:

- add `WordKeeper` as a specialist

Step 5:

- add `MemoryReader` and `MemoryKeeper` as specialists

Step 6:

- add `NewsAgent` as a specialist

Step 7:

- add `GrammarAgent` as a specialist

Step 8:

- shrink teacher prompt and tool list

This reduces risk and makes it easy to compare old vs new behavior.

## Open Questions

Resolved for v1:

- `read_url`: remains a direct tool; `TeacherAgent` should not call it directly.
- Coordinator: LLM agent.
- Second passes: do not allow specialists to request them; provide fixed context windows instead.
- Post-response execution: run post-response specialists on the finalized teacher response and persist results as internal "agent side effects" records.

Still discussable:

- Should specialist outputs be produced by LLM agents only, or should some domains allow deterministic post-processing (with purely mechanical work wrapped as tools)?
- How much conversation history should each specialist receive by default (per specialist/tool), beyond the baseline suggestions in `AGENT_SWARM_CONTRACT.md`?

## Recommended First Cut

Build the smallest useful version first:

- `CoordinatorAgent`
- `TeacherAgent`
- `WordKeeper`
- `MemoryReader`
- `MemoryKeeper`

Leave `NewsAgent` and `GrammarAgent` in the current teacher path temporarily if needed.

Reason:

- the current biggest reliability gap is persistence, not retrieval
- word and memory behaviors are exactly where prompt overload is hurting most
- splitting memory into read and write paths keeps phase boundaries clean

## Acceptance Criteria

The redesign is successful when:

- the teacher no longer directly owns most write-tool policies
- the coordinator remains small and phase-aware
- useful words are saved reliably during normal conversation
- relevant memory is read before the teacher answers when needed
- durable memory updates happen reliably
- prompts are shorter and more maintainable
- logs clearly show which specialist acted and why
- the final answer remains conversational and coherent
