# Agent Swarm Implementation Plan

## Purpose

Replace the current single teacher-agent model with a coordinator plus specialist agents so tool use becomes more reliable, prompts stay narrow, and each domain can evolve without overloading one system prompt.

This document is both a product/design note and an implementation plan.

## Problem Statement

The current `AgentService` asks one agent to do all of the following in a single turn:

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

## Proposed Architecture

### High-Level Shape

Use a thin `Coordinator` plus a separate `TeacherAgent` and specialist agents with clear ownership.

- `Coordinator`
  - is not user-facing
  - decides which specialists to invoke and in which phase
  - passes only the minimum relevant context to each specialist
  - collects structured outputs
  - prepares the teacher input bundle

- `TeacherAgent`
  - owns the final user response
  - focuses on teaching, tone, explanation quality, and conversational flow
  - consumes specialist outputs instead of owning most tool policies

- `WordKeeper`
  - owns useful-word capture and `prioritize_words_for_learning`
  - usually runs after the teacher response is drafted
  - decides whether a word should be saved or prioritized based on the user message and teacher output

- `MemoryReader`
  - pre-response only
  - reads relevant student memory and returns compact context for the teacher

- `MemoryKeeper`
  - post-response only
  - owns memory persistence decisions after the teaching turn
  - decides whether memory should be created, updated, promoted, reprioritized, or deleted

- `NewsAgent`
  - owns whether news lookup is needed
  - chooses query strategy and result shape
  - runs before the teacher response when external information is needed

- `GrammarAgent`
  - owns grammar lookup decisions and cheatsheet reading
  - usually runs before the teacher response when references are needed

- `UrlReaderAgent` or direct utility
  - owns `read_url` only if it needs domain-specific judgment
  - otherwise can remain a direct tool used by `Coordinator`

## Design Principles

### 1. Domain Ownership

Each specialist owns:

- its prompt
- its tools
- its decision policy
- its output schema
- its tests

No two specialists should share write ownership of the same persistence domain.

### 2. Structured Outputs

Specialists should return structured results, not free-form prose as their primary output.

Each specialist result should include:

- `status`: `no_action` | `action_taken` | `error`
- `actions`: tool calls attempted and outcomes
- `artifacts`: structured domain payload
- `notes_for_teacher`: short summary for final response composition

Example:

```json
{
  "status": "action_taken",
  "actions": [
    {
      "tool": "prioritize_words_for_learning",
      "status": "success",
      "summary": "created=1, restored=0, prioritized=1, already_prioritized=0"
    }
  ],
  "artifacts": {
    "saved_words": ["avgorande", "forutsattning"]
  },
  "notes_for_teacher": "Two useful vocabulary items were saved for future recall."
}
```

### 3. Narrow Context

Each specialist should receive only:

- latest user turn
- short conversation window relevant to its domain
- small shared context summary if needed

Do not pass the full conversation history to every specialist.

### 4. Coordinator Is Thin

The coordinator should not re-implement specialist logic.

It should only:

- route
- manage phases
- collect results
- resolve minor conflicts
- prepare teacher context

The teacher should not absorb orchestration duties back into its prompt.

### 5. Different Domains Use Different Flows

Not all specialists belong to the same orchestration phase.

- `pre-response specialists`
  - gather information needed before the teacher can answer
  - examples: `MemoryReader`, `NewsAgent`, `GrammarAgent`, maybe `UrlReaderAgent`

- `post-response specialists`
  - persist or interpret outcomes that depend on the teacher's reasoning or answer
  - examples: `WordKeeper`, `MemoryKeeper`

This is intentional. Some domains need the teacher's draft or final answer as an input signal.

## Why This Instead of a Generic Plan/Execute/Respond Pipeline

A generic execution stage would centralize too much domain behavior again. News, memory, and vocabulary are not passive tools; they each involve judgment:

- whether to act
- which tool arguments to use
- whether the result is meaningful
- whether the result should affect the final response

That judgment belongs inside domain specialists, not inside a global executor.

## Agent Contracts

### Coordinator Contract

Input:

- latest user message
- recent chat history
- current user metadata

Output:

- routing decisions
- teacher input bundle
- audit trail of specialists invoked

Responsibilities:

- decide which specialists to invoke and in which phase
- avoid duplicate specialist calls
- keep orchestration narrow and predictable

### TeacherAgent Contract

Input:

- latest user message
- recent chat history
- compact outputs from pre-response specialists
- optional post-response notes only if needed for user-visible acknowledgements

Output:

- final assistant response
- optional sources

Responsibilities:

- produce a coherent pedagogical response
- use specialist outputs naturally
- never claim persistence unless a specialist reports success

### WordKeeper Contract

Input:

- latest user message
- teacher draft or final response
- recent relevant snippets from conversation
- optional mother tongue

Tools:

- `prioritize_words_for_learning`

Decisions:

- should a word be saved
- which words to save
- translation/example completion rules

Typical phase:

- `post-response`

Reason:

- useful vocabulary may only become obvious after the teacher has interpreted the student's message and prepared an explanation or correction

Output artifacts:

- saved words
- skipped words
- tool action summary

### MemoryReader Contract

Input:

- latest user message
- recent relevant chat turns
- optional routing hints from coordinator

Tools:

- `start_student_info`
- `read_memory`

Decisions:

- whether memory should be read for this turn
- what subset of memory is relevant
- how to compress memory into a small context bundle for the teacher

Typical phase:

- `pre-response`

Output artifacts:

- memory context summary
- memory items consulted
- reasons for no action

### MemoryKeeper Contract

Input:

- latest user message
- teacher draft or final response
- recent relevant chat turns
- optional memory summary

Tools:

- `upsert_memory_item`
- `update_memory_status`
- `update_memory_priority`
- `promote_to_strength`
- `delete_memory_item`

Decisions:

- whether a fact or learning signal is durable enough to store
- whether a change is create/update/status-change/delete

Typical phase:

- `post-response`

Reason:

- some signals are only visible after the teacher has interpreted the turn, such as repeated struggle, demonstrated mastery, or a clarified goal

Output artifacts:

- changed memory items
- reasons for no action

### NewsAgent Contract

Input:

- latest user message
- optional recent context

Tools:

- `search_news_with_dates`

Decisions:

- whether the user is actually asking for news
- query formulation
- timelimit and result count

Output artifacts:

- sources
- short domain summary

### GrammarAgent Contract

Input:

- latest user message
- optional recent learner mistakes or topic context

Tools:

- `search_grammar`
- `read_grammar_page`

Decisions:

- whether a grammar reference is useful
- which cheatsheet(s) to read

Output artifacts:

- selected grammar references
- distilled explanation points

## Orchestration Flow

Use phase-aware orchestration. Different specialists run at different times.

### Phase A: Pre-Response Routing

`Coordinator` inspects the turn and chooses zero or more pre-response specialists.

Examples:

- "My biggest problem is word order" -> `MemoryReader`, maybe `GrammarAgent`
- "What happened in Sweden this week?" -> `NewsAgent`
- "Is this sentence correct?" -> maybe `GrammarAgent`, maybe no specialists

### Phase B: Pre-Response Specialist Execution

Pre-response specialists run and return structured results for the teacher.

Preferred execution model:

- run independent specialists in parallel where safe
- keep write domains out of this phase
- preserve logs and outputs per specialist

Potential safe parallel combinations:

- `MemoryReader` + `NewsAgent`
- `MemoryReader` + `GrammarAgent`
- `NewsAgent` + `GrammarAgent`

### Phase C: Teacher Response

`TeacherAgent` answers the user using:

- latest user message
- recent conversation context
- pre-response specialist outputs

### Phase D: Post-Response Routing

`Coordinator` inspects the user turn plus teacher response and chooses zero or more post-response specialists.

Examples:

- teacher introduced or highlighted useful vocabulary -> `WordKeeper`
- teacher observed repeated confusion or a new durable learner fact -> `MemoryKeeper`

### Phase E: Post-Response Specialist Execution

Post-response specialists run and return structured results.

Potential safe parallel combinations:

- `WordKeeper` + `MemoryKeeper`

### Phase F: Finalization

The system finalizes:

- the teacher answer
- optional mention of successful side effects when appropriate
- optional news sources
- optional grammar references

The coordinator should not expose internal agent chatter.

## Implementation Plan

### Milestone 1: Introduce Specialist Interfaces

Deliverables:

- add a shared structured result schema for specialist outputs
- add a base specialist interface
- keep current `AgentService` behavior unchanged

Tasks:

- create `agent/specialists/` package
- define `SpecialistResult` schema
- define specialist invocation interface
- add logging shape for specialist runs

Success criteria:

- can instantiate a specialist and return a structured `no_action`

### Milestone 2: Extract WordKeeper

Deliverables:

- move vocabulary-saving responsibility out of the teacher prompt
- `WordKeeper` owns `prioritize_words_for_learning`

Tasks:

- create `WordKeeper` prompt and service
- wire `WordKeeper` into the `post-response` phase
- remove word-saving policy from teacher agent prompt or reduce it to routing guidance
- add structured tests for:
  - explicit save requests
  - useful word discovered in normal conversation
  - no-action cases
  - tool failure propagation

Success criteria:

- word-saving behavior can be tested without invoking the teacher prompt

### Milestone 3: Extract MemoryReader and MemoryKeeper

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

### Milestone 4: Extract NewsAgent and GrammarAgent

Deliverables:

- reference and retrieval domains become specialists

Tasks:

- create `NewsAgent`
- create `GrammarAgent`
- decide whether `read_url` remains direct or becomes its own specialist
- add source/result schemas

Success criteria:

- teacher only routes and composes

### Milestone 5: Introduce Coordinator and TeacherAgent Split

Deliverables:

- replace direct all-tools teacher agent with phased coordinator plus separate teacher

Tasks:

- create routing policy
- add specialist registry
- implement phased fan-out/fan-in orchestration
- add teacher input bundle creation
- preserve existing source extraction behavior for news

Success criteria:

- same user-facing chat endpoint, but internals run coordinator plus specialists

### Milestone 6: Reduce Monolithic Prompt

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

Each specialist invocation should log:

- specialist name
- user id
- routing reason
- input summary
- tools called
- action result
- latency
- failure details

Recommended log examples:

- `Coordinator pre-phase selection: user_id=12 specialists=MemoryReader,NewsAgent`
- `Coordinator post-phase selection: user_id=12 specialists=WordKeeper`
- `WordKeeper result: status=action_taken saved_words=2`
- `MemoryReader result: status=action_taken items_read=3`
- `MemoryKeeper result: status=no_action reason=no durable memory in turn`

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

- add specialist framework behind existing `AgentService`

Step 2:

- add `WordKeeper` as a post-response specialist, keep everything else in current teacher path

Step 3:

- route `MemoryReader` and `MemoryKeeper`

Step 4:

- route `NewsAgent` and `GrammarAgent`

Step 5:

- shrink teacher prompt and tool list

This reduces risk and makes it easy to compare old vs new behavior.

## Open Questions

- Should `read_url` remain a direct tool or become a dedicated specialist?
- Should specialist outputs be produced by LLM agents only, or should some domains allow deterministic post-processing?
- How much conversation history should each specialist receive by default?
- Should the coordinator be an LLM agent or a simpler policy layer?
- Should post-response specialists run on the teacher draft or the finalized teacher response?
- Should memory and vocabulary specialists be allowed to request a second pass if context is insufficient?

## Recommended First Cut

Build the smallest useful version first:

- `Coordinator`
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
