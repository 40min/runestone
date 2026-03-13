# Agent Swarm Contracts (Coordinator + Specialists)

This document describes the proposed agent roles, tool access, structured contracts, and orchestration flow.

For implementation milestones and delivery sequencing, see `AGENT_SWARM_PLAN.md`.

## Proposed Architecture

Use a thin `CoordinatorAgent` plus a separate `TeacherAgent` and specialist agents with clear ownership.

- `CoordinatorAgent`
  - is not user-facing
  - decides which specialists to invoke and in which phase
  - passes only the minimum relevant context to each specialist
  - collects structured outputs
  - prepares the teacher input bundle
  - may call direct utility tools when it is strictly mechanical (e.g., `read_url`)
  - deterministic/mechanical steps should be wrapped into tools (not performed as free-text transformations)

- `TeacherAgent`
  - owns the final user response
  - focuses on teaching, tone, explanation quality, and conversational flow
  - consumes specialist outputs instead of owning most tool policies
  - should not call persistence/retrieval tools directly in the multi-agent design

- `WordKeeper`
  - owns useful-word capture and `prioritize_words_for_learning`
  - usually runs post-response
  - can also run pre-response for explicit user commands that expect immediate confirmation (e.g., "Save this word")

- `MemoryReader`
  - pre-response only
  - reads relevant student memory and returns compact context for the teacher

- `MemoryKeeper`
  - post-response only
  - owns memory persistence decisions after the teaching turn

- `NewsAgent`
  - owns whether news lookup is needed
  - chooses query strategy, selects sources, and (optionally) reads a small number of URLs for summarization

- `GrammarAgent`
  - owns grammar lookup decisions and cheatsheet reading

### Tool Access Policy (First Cut)

- `TeacherAgent`: no tools (or strictly non-persistent, non-network helpers if absolutely required)
- `CoordinatorAgent`: orchestration-only + direct utility reads (`read_url`) when needed
- `MemoryReader`: `start_student_info`, `read_memory`
- `MemoryKeeper`: `upsert_memory_item`, `update_memory_status`, `update_memory_priority`, `promote_to_strength`, `delete_memory_item`
- `WordKeeper`: `prioritize_words_for_learning`
- `NewsAgent`: `search_news_with_dates`, `read_url`
- `GrammarAgent`: `search_grammar`, `read_grammar_page`

## Structured Outputs

Specialists should return structured results, not free-form prose as their primary output.

Each specialist result should include:

- `status`: `no_action` | `action_taken` | `error`
- `actions`: tool calls attempted and outcomes
- `info_for_teacher`: short, size-bounded summary for final response composition (max 3000 characters)
- `artifacts`: structured domain payload (machine-oriented; not for verbatim teacher consumption)

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
  "info_for_teacher": "Two useful vocabulary items were saved for future recall."
}
```

## Output Validation (Pydantic + LangChain)

Use Pydantic models as the single source of truth for coordinator and specialist outputs.

Implementation options (compatible with existing `langchain` usage in this repo):

- Prefer `ChatOpenAI(...).with_structured_output(MyPydanticModel)` for coordinator/specialist LLM calls so LangChain requests JSON matching the schema and parses it into the Pydantic object.
- Keep a fallback path: ask for JSON, then `MyPydanticModel.model_validate_json(text)`; on validation failure, do a single repair retry (or return `status="error"` and log).

For tool inputs/outputs, continue using tool argument schemas (already Pydantic-backed).

## Context Passing Defaults

Context windows should be selected per specialist based on what its tools require (and kept stable enough to test).

Important: preventing duplicate saves should be solved primarily via idempotent writes (stable keys / upserts) and an explicit "recent side effects" record, not by shrinking the text window alone.

Suggested defaults:

- `NewsAgent`: last 2 messages (`previous_assistant`, `current_user`)
- `GrammarAgent`: last 4 messages
- `MemoryReader`: last 6 messages (or last 2 pairs), because memory relevance often depends on the recent thread
- `WordKeeper`: last 2 messages (`previous_assistant`, `current_user`) plus `teacher_response` when post-response
- `MemoryKeeper`: last 2 messages (`previous_assistant`, `current_user`) plus `teacher_response`

Additionally, `CoordinatorAgent` may provide a small "system context bundle" to all specialists:

- stable learner profile (e.g., level, goals, mother tongue) if available
- the latest persisted "agent side effects" record (structured, not raw logs), including recent successful actions

### Side-Effects Record (For Dedupe)

To avoid saving the same thing repeatedly across turns, the coordinator should include (and keep updated) a small list like:

- `recent_side_effects`: last N (e.g., 10) specialist actions with `turn_id`, `specialist`, `status`, and key artifacts (e.g., `saved_words`, `memory_keys_changed`)

Specialist rule:

- if the candidate word/memory key appears in `recent_side_effects` within the last K turns (e.g., 3), return `no_action` unless there is genuinely new information (e.g., different meaning/example, higher priority, status change).

Memory idempotency rule:

- memory writes must use stable keys (e.g., `area_to_improve:word_order`, `personal_info:goal`) so repeats update instead of creating duplicates.

No specialist should request a second pass; instead, give enough context by default and keep the windows small and consistent.

## Coordinator Prompt Draft (Design Target)

Persona: you are the teacher's assistant and orchestration coordinator. You do not speak to the student.

Behavior requirements:

- be conservative: do not call specialists unless there is a clear trigger
- be truthful: teacher must not claim side effects unless a specialist succeeded in the same turn (pre-response fast path)
- keep costs low: avoid reading URLs unless necessary; cap number of URLs read; prefer short summaries
- keep outputs deterministic: always emit the routing plan and structured inputs
- for deterministic/mechanical work, call tools; do not "handwave" transformations in prose

Output (suggested shape):

- `pre_response`: list of specialists to invoke, with `reason`, `chat_history_size`, and expected artifacts
- (future) `teacher_hints`: optional hints/policies for what to send to the teacher
- `post_response`: list of specialists to invoke after the teacher response

### Teacher Input Hints (Future)

Coordinator-generated "what to send to the teacher" should be treated carefully to avoid hallucinating
conversation history or tool outputs.

Preferred design direction:

- Teacher input is built deterministically in code from the real request `message` + `history`.
- Coordinator may optionally return a small, validated hints/policy object (examples: desired history window,
  whether to include a memory summary, or whether to request a compact recap) that the manager may apply.
- Coordinator should never echo raw `history` back as "teacher input", and should never invent tool results.

### Size Limits (All Specialists)

To keep prompts stable and avoid flooding the TeacherAgent with unrelated details:

- Specialists must keep `info_for_teacher` to 3000 characters or fewer.
- Specialists should put any larger structured data into `artifacts` and rely on downstream code to interpret it.

## Agent Contracts

### CoordinatorAgent Contract

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
- optional side-effect confirmations from pre-response fast path only (e.g., WordKeeper ran pre-response successfully)

Output:

- final assistant response
- optional sources (news, grammar references)

Responsibilities:

- produce a coherent pedagogical response
- use specialist outputs naturally
- never claim persistence unless a specialist reports success for this turn

### WordKeeper Contract

Input:

- latest user message
- teacher draft or final response (when available)
- recent relevant snippets from conversation
- optional mother tongue

Tools:

- `prioritize_words_for_learning`

Decisions:

- should a word be saved
- which words to save
- translation/example completion rules

Typical phase:

- `post-response` (default)
- `pre-response` (fast path) when user explicitly requests saving and confirmation should appear in the same teacher reply

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

Output artifacts:

- changed memory items
- reasons for no action

### NewsAgent Contract

Input:

- latest user message
- optional recent context

Tools:

- `search_news_with_dates`
- `read_url`

Decisions:

- whether the user is actually asking for news
- query formulation
- timelimit and result count
- which (few) URLs to read for better summaries

Output artifacts:

- sources (urls + titles)
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

`CoordinatorAgent` inspects the turn and chooses zero or more pre-response specialists.

Examples:

- "My biggest problem is word order" -> `MemoryReader`, maybe `GrammarAgent`
- "What happened in Sweden this week?" -> `NewsAgent`
- "Save this word for me: avgorande" -> `WordKeeper` (pre-response fast path)

### Phase B: Pre-Response Specialist Execution

Pre-response specialists run and return structured results for the teacher.

Preferred execution model:

- run independent specialists in parallel where safe
- keep write domains out of this phase (exception: explicit user command fast paths)
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

`CoordinatorAgent` inspects the user turn plus teacher response and chooses zero or more post-response specialists.

Examples:

- teacher introduced or highlighted useful vocabulary -> `WordKeeper`
- teacher observed repeated confusion or a new durable learner fact -> `MemoryKeeper`
- user explicitly requests a post-response action (e.g., "Save this word for me") but fast path was not used -> `WordKeeper`

### Phase E: Post-Response Specialist Execution

Post-response specialists run and return structured results.

Potential safe parallel combinations:

- `WordKeeper` + `MemoryKeeper`

### Phase F: Side-Effects Recording

Post-response results are persisted as a structured, non-user-visible "agent side effects" record in the conversation history (system/internal).

Rules:

- do not change the already-sent teacher reply
- future turns may mention side effects only when they are confirmed by this record

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

Add a consistent tag for agent-swarm logs so they are easy to grep:

- prefix every log line with `[agents:<component>]` (examples: `coordinator`, `wordkeeper`, `memoryreader`)

Recommended log examples:

- `[agents:coordinator] Pre-phase selection: user_id=12 specialists=MemoryReader,NewsAgent`
- `[agents:coordinator] Post-phase selection: user_id=12 specialists=WordKeeper`
- `[agents:wordkeeper] Result: status=action_taken saved_words=2`
- `[agents:memoryreader] Result: status=action_taken items_read=3`
- `[agents:memorykeeper] Result: status=no_action reason=no durable memory in turn`
