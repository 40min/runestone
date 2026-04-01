# Structured Intent Envelope — Architecture Note

## Problem

In a single-agent setup, the Teacher was responsible for both generating a response and
executing side effects (saving vocabulary, updating memory, fetching URLs, etc.) via tools.
Under context load, it started narrating tool calls instead of making them — reporting
`"I am saving"` without the tool ever firing. This is a tool-call hallucination caused by
attention dilution across too many responsibilities.

---

## Solution: Structured Output Envelope

The Teacher's output becomes a typed envelope with two fields:

```json
{
  "student_facing": "Great job! Let me save that word for you.",
  "intents": ["SAVE_VOCABULARY", "UPDATE_MEMORY"]
}
```

- `student_facing` — the message delivered to the student
- `intents` — a list of declared actions from a hardcoded enum, invisible to the student

The Teacher **declares** intent. It no longer **executes** anything.

---

## Intent Enum

```python
class TeacherIntent(str, Enum):
    SAVE_VOCABULARY  = "SAVE_VOCABULARY"
    UPDATE_MEMORY    = "UPDATE_MEMORY"
    FETCH_URL        = "FETCH_URL"
    SEARCH_GRAMMAR   = "SEARCH_GRAMMAR"
    WEB_SEARCH       = "WEB_SEARCH"
    NO_ACTION        = "NO_ACTION"
```

This enum is the contract between all agents. Adding a new capability = adding a new value
and a new subagent. The Coordinator and Teacher are untouched.

---

## Coordinator Becomes Deterministic

With explicit intents, the Coordinator no longer needs to reason — it routes:

```python
INTENT_ROUTING = {
    TeacherIntent.SAVE_VOCABULARY: word_keeper_agent,
    TeacherIntent.UPDATE_MEMORY:   memory_keeper_agent,
    TeacherIntent.FETCH_URL:       url_reader_agent,
    TeacherIntent.SEARCH_GRAMMAR:  grammar_search_agent,
    TeacherIntent.WEB_SEARCH:      web_search_agent,
}

for intent in teacher_output.intents:
    if agent := INTENT_ROUTING.get(intent):
        agent.run(context)
```

No LLM involved. No misrouting possible. The Coordinator can be a pure `switch` statement.

---

## Intents Are Signals, Not Data Packages

Intents should declare *what needs to happen*, not carry extracted data. The Teacher
structuring word lists or memory corrections inside `intents` is the same attention problem
in a different field.

Subagents receive the full conversation context anyway — WordKeeper can find the vocabulary
itself. That's its job. Keeping intents as pure signals means:

- The Teacher stays focused on generation and declaration only
- Intents remain cheap to emit regardless of enum size
- Subagents own their extraction logic, not the Teacher

The one exception: a minimal disambiguation hint when the subagent genuinely can't resolve
something from context — e.g. an explicit Teacher override. This should be rare and
case-specific, not a default payload shape.

---

## Multi-Intent Ordering

When the Teacher emits multiple intents, execution order should be explicit. A safe default:

1. Read-only operations first (`SEARCH_GRAMMAR`, `WEB_SEARCH`, `FETCH_URL`)
2. Write operations second (`SAVE_VOCABULARY`, `UPDATE_MEMORY`)

If a write depends on a read's result, that dependency should be modeled explicitly rather
than inferred from order.

---

## Why This Is Better

|                         | Before (single agent)                          | After (intent envelope)                                       |
| ----------------------- | ---------------------------------------------- | ------------------------------------------------------------- |
| Tool-call hallucination | Possible — model narrates instead of executing | Structurally impossible — Teacher only declares               |
| Coordinator complexity  | High — must infer intent from prose            | Zero — pure routing table                                     |
| Subagent isolation      | None — all logic in one context                | Full — each subagent has one job                              |
| Testability             | Hard — side effects mixed with generation      | Easy — Teacher, routing, and execution testable independently |
| Adding new capability   | Modify Teacher prompt and tool list            | Add enum value + new subagent                                 |

---

## Summary

The core insight is separating **declaration** from **execution**. The Teacher is good at
understanding context and generating responses. It is not reliable as an executor under
load. Giving it a structured output schema enforces the boundary at the architecture level,
not the prompt level — making the "I am saving" class of bug impossible rather than just
unlikely.
