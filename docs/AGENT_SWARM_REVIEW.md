# Agent Swarm — MS3 Review

**Branch:** `feat/agent-swarm-ms3`
**Milestone reviewed:** MS3 — Introduce Coordinator for Pre/Post Orchestration
**Date:** 2026-03-13

---

## Executive Summary

MS3 delivers a clean, working coordinator + specialist orchestration layer on top of the MS1/MS2 foundation. The overall architecture is sound: the coordinator produces structured plans, the manager executes fan-out/fan-in,  and the teacher consumes pre-response specialist context naturally. The implementation is production-quality in its core paths.

The main issues are:

1. **TeacherAgent still owns ALL tools** — the key contract promise (tool responsibility moved to specialists) is not yet enforced.
2. **Coordinator has no unit tests** — the most novel MS3 component is untested.
3. **Registry is always empty at runtime** — no specialist is ever registered, making routing a no-op today.
4. **Several minor design and consistency gaps** worth addressing before MS4.

---

## Architecture Assessment

### What is correct and well-designed

| Area                                                                  | Verdict                   |
| --------------------------------------------------------------------- | ------------------------- |
| Phase model (A→B→C→D→E→F)                                             | ✅ Implemented faithfully  |
| `SpecialistResult` / `RoutingItem` / `CoordinatorPlan` Pydantic chain | ✅ Matches contract schema |
| LLM coordinator with `with_structured_output`                         | ✅ Correct approach        |
| Fan-out via `asyncio.gather` preserving routing order                 | ✅                         |
| Chat-history window per specialist (`chat_history_size`)              | ✅                         |
| Coordinator fallback on error → empty plan                            | ✅ Safe degradation        |
| `[agents:<component>]` log prefix convention                          | ✅ Consistent              |
| `_extract_sources` kept in manager, not teacher                       | ✅ Good separation         |
| `pre_results` injected as `SystemMessage` with sanitised format       | ✅                         |
| `info_for_teacher` / `artifacts` field split                          | ✅ Matches contract        |

### Gaps versus the MS3 contract

#### 1. TeacherAgent still holds all 12 tools (Minor)

The contract states:

> `TeacherAgent`: no tools (or strictly non-persistent, non-network helpers if absolutely required)

`teacher.py` still imports and registers all 12 tools:

```python
tools = [
    start_student_info, read_memory,
    upsert_memory_item, update_memory_status, update_memory_priority,
    promote_to_strength, delete_memory_item,
    prioritize_words_for_learning,
    search_news_with_dates,
    search_grammar, read_grammar_page,
    read_url,
]
```

This is expected to remain temporarily until MS4–MS7 extract each specialist, but it creates a contradiction: the coordinator plans routing to specialists that don't exist, while the teacher silently does the same work anyway via tools. This undermines the observability goal immediately.

**Recommendation:** Add an explicit `# TODO MS4-MS7: tools will be removed as specialists are extracted` comment to each tool import group, making the intentional phasing visible. Consider removing at minimum `prioritize_words_for_learning` (MS4 target) to validate the specialist pipeline end-to-end.

**Decision:** leave as is for now, wait for the next milestone.

#### 2. Specialist registry is permanently empty (Minor)

`AgentsManager.__init__` creates a `SpecialistRegistry()` but never calls `.register()` for any specialist. The coordinator's routing decisions therefore always trigger the "Missing specialist — skipping" log path. The entire pre/post specialist machinery is wired but has zero live specialists.

**Recommendation:** Even a stub `NoOpSpecialist` for `word_keeper` registered at startup would validate the fan-out path in production. Alternatively, document clearly in `manager.py` that the registry starts empty and will be populated in MS4.

**Decision:** leave as is for now, wait for the next milestone.

#### 3. Coordinator not exposed to `available_specialists` (Minor)

Manager correctly passes `available_specialists` filtered to non-teacher names from the registry. But since the registry is empty, `available_specialists=[]` is always passed to the coordinator. The coordinator prompt says:

> Only route to specialists listed in the `available_specialists` input field.

So the coordinator correctly returns empty plans — but this means the code path exercised in production today is: coordinator called → returns empty plan → no specialists run → teacher runs alone. **MS3 is structurally intact but not yet doing meaningful new work.**

**Decision:** leave as is for now, wait for the next milestone.

---

## Implementation Analysis

### `coordinator.py` (fixed)

**Strengths:**
- Clean, single-responsibility class
- `temperature=0` for deterministic routing — correct
- `with_structured_output(CoordinatorPlan)` — idiomatic LangChain, matches contract
- Good log line with latency

**Issues:**

**A. Model builder is duplicated from `teacher.py` (fixed) **

Both files contain identical provider selection + `ChatOpenAI` instantiation logic. This will diverge as they're updated independently.

```python
# Same block exists in both coordinator.py and teacher.py
if settings.chat_provider == "openrouter":
    api_key = settings.openrouter_api_key
    api_base = "https://openrouter.ai/api/v1"
elif settings.chat_provider == "openai":
    api_key = settings.openai_api_key
    api_base = None
else:
    raise ValueError(f"Unsupported chat provider: {settings.chat_provider}")
```

**Recommendation:** Extract a `build_chat_model(settings, temperature)` factory into a shared `agents/llm.py` module.

**B. Coordinator and teacher use the same model (fixed)**

The coordinator should ideally use a cheaper/faster model than the teacher (it only needs to plan routing, not teach). The current implementation uses `settings.chat_model` for both.

**Recommendation:** Add `settings.coordinator_model` (with fallback to `chat_model`) so the coordinator can be pointed at a faster model independently.

**C. No retry / repair path for structured output failures (fixed)**

The contract specifies:

> Keep a fallback path: ask for JSON, then `MyPydanticModel.model_validate_json(text)`; on validation failure, do a single repair retry (or return `status="error"` and log).

If the LLM returns malformed JSON, `with_structured_output` raises an exception, which the manager catches and converts to an empty fallback plan. This is safe but silent — the log entry is `Coordinator failed, falling back to teacher only` with no indication of whether it was a schema validation failure or a network error.

**Recommendation:** Catch and log `OutputParserException` separately from network errors for better observability.

### `manager.py` (fixed)

**Strengths:**
- Phase A→B→C→D→E→F is clean and readable
- Fan-out with `asyncio.gather` is correct
- Specialist error isolation (returns `{"status": "error", "info_for_teacher": ""}`) prevents teacher context poisoning
- `_extract_sources` security (URL validation, scheme check, port allow-list) is solid

**Issues:**

**A. Log prefix mismatch — coordinator logs emitted from manager** (fixed)

```python
# manager.py lines 108-111 and 132-135
logger.info("[agents:coordinator] Pre-phase selection: ...")
logger.info("[agents:coordinator] Post-phase selection: ...")
```

These lines use the `[agents:coordinator]` prefix but are emitted by the **manager** logger. The coordinator's own `plan()` does not log the selection summary. This breaks the grep-by-component convention.

**Recommendation:** Move the routing selection log lines into `coordinator.py`'s `plan()` method (they have access to the plan result there), and use `[agents:manager]` for anything emitted in `manager.py`.

**B. `_run_specialists` type annotation is untyped** (fixed)

```python
async def _run_specialists(self, routing_items, ...) -> list[dict]:
```

`routing_items` should be annotated `list[RoutingItem]`.

**C. Missing log for post-response specialist results** (fixed)

Post-response specialist results are gathered but unlike pre-response, they are never stored or logged as "side-effects records" (Phase F from the contract). The spec says:

> Post-response results are persisted as a structured, non-user-visible "agent side effects" record in the conversation history.

This Phase F persistence is not implemented. The results are gathered and then discarded. This means deduplication across turns (the `recent_side_effects` contract) is not possible yet.

**Recommendation:** At minimum, log the post-response results as a structured summary entry, and add a comment that Phase F persistence is deferred (note which MS it belongs to).

### `specialists/teacher.py` (fixed)

**Strengths:**
- Clean decoupling from `BaseSpecialist` (correct for MS3 — teacher is not a routable specialist)
- `_format_pre_results` correctly truncates per `INFO_FOR_TEACHER_MAX_CHARS`
- `PRE_RESPONSE_SPECIALISTS` system message placed before history — good ordering
- History truncation at `MAX_HISTORY_MESSAGES=20` consistent with before

**Issues:**

**A. `_format_pre_results` only surfaces `info_for_teacher`, drops `artifacts` (fixed)**

The formatted context sent to the teacher is:

```python
lines.append(
    f"- {name} ({status}): "
    f"{TeacherAgent._truncate_text(info_for_teacher, max_len=INFO_FOR_TEACHER_MAX_CHARS) or 'no info'}"
)
```

Resolution:
- Keep raw `artifacts` out of `_format_pre_results`; they remain machine-oriented.
- Teacher-visible tool/action context is now expected to come from specialist-authored `info_for_teacher` and manager-injected `[RECENT_SIDE_EFFECTS]`.
- Unit tests now lock in that pre-response formatting does not leak raw artifacts.

The contract says:

> `info_for_teacher`: primary, size-bounded information for the TeacherAgent. Prefer `info_for_teacher` over raw artifacts.

This item is now resolved without widening the teacher prompt contract.

**B. `_format_pre_results` is declared `@staticmethod` but references `TeacherAgent.PRE_RESPONSE_INFO_MAX_CHARS` (fixed)**

```python
@staticmethod
def _format_pre_results(pre_results: list[dict]) -> str:
    ...
```

A `@staticmethod` referencing the class by name is a code smell — it's a hidden coupling to the class. If the method is moved, renamed, or subclassed, this silently breaks.

Resolution: `_format_pre_results` now truncates via the shared `INFO_FOR_TEACHER_MAX_CHARS` constant directly, removing the class-name coupling.

**C. `build_agent` is called in `__init__` but is also a public method (fixed)**

The agent used to be built in `__init__` via `self.agent = self.build_agent()`. Because `build_agent` was public, tests or external code could call it again and implicitly replace the agent. Either:
- Make it `_build_agent` (private), or
- Document that it should only be called once and is exposed only for testability.

Resolution: the builder is now private as `_build_agent()`, and teacher tests were updated to target the private construction helper directly.

### `specialists/base.py` (fixed)

**Strengths:**
- Clean Pydantic models with field descriptions
- `INFO_FOR_TEACHER_MAX_CHARS = 3000` constant matches the contract exactly
- Abstract `run(context: SpecialistContext)` now enforces a typed contract

**Issues:**

**A. `context: dict` is too loose for a contract (fixed)**

The specialist interface passes everything as an untyped `dict`. If specialist authors forget to unpack `user`, `message`, or `teacher_response`, they get a `KeyError` at runtime rather than a type error at instantiation.

Resolution: Added `SpecialistContext` as a typed Pydantic input model and updated `BaseSpecialist.run` to `run(context: SpecialistContext)`. Manager orchestration now passes this typed context object to specialists.

```python
class SpecialistContext(BaseModel):
    message: str
    history: list[ChatMessage]
    user: User
    teacher_response: str | None = None
    pre_results: list[dict] = Field(default_factory=list)
    routing_reason: str = ""
    chat_history_size: int = 0
```

**B. `SpecialistResult.info_for_teacher` uses `max_length` but Pydantic v2 does not enforce it (fixed)**

```python
info_for_teacher: str = Field("", ..., max_length=INFO_FOR_TEACHER_MAX_CHARS)
```

In Pydantic v2, `max_length` on `Field` for `str` is a JSON Schema annotation but is **not enforced at validation time** by default unless you use `Annotated[str, StringConstraints(max_length=...)]`. The `_truncate` in `_format_pre_results` compensates, but a downstream specialist could return an oversized string that passes `SpecialistResult.model_validate(...)` without error.

Resolution: Migrated to `Annotated[str, StringConstraints(max_length=...)]` so validation enforces the `INFO_FOR_TEACHER_MAX_CHARS` bound at runtime.

```python
from pydantic import StringConstraints
from typing import Annotated

info_for_teacher: Annotated[str, StringConstraints(max_length=INFO_FOR_TEACHER_MAX_CHARS)] = ""
```

### `specialists/registry.py`

**Well-implemented.** `OrderedDict` preserves registration order (good for deterministic routing order). The API is minimal and correct.

**Minor:** No `unregister` method, which could complicate testing (registering multiple times silently overwrites). Consider a guard:

```python
def register(self, specialist: BaseSpecialist, *, overwrite: bool = False) -> None:
    if not overwrite and specialist.name in self._specialists:
        raise ValueError(f"Specialist '{specialist.name}' already registered")
    self._specialists[specialist.name] = specialist
```

---

## Test Coverage Assessment

### What is covered

| Test file                     | Coverage                                                                                                                                               |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `test_base.py`                | `SpecialistResult` validation, `BaseSpecialist` abstractness, concrete instantiation                                                                   |
| `test_registry.py`            | register + get + list                                                                                                                                  |
| `test_coordinator_schemas.py` | `CoordinatorPlan` schema validation                                                                                                                    |
| `test_service.py`             | `AgentsManager` orchestration: delegation, cleanup, source extraction, URL safety, history truncation, pre_results passing, specialist history slicing |
| `test_teacher.py`             | `TeacherAgent` build, history, mother tongue, source formatting, provider config                                                                       |

### Critical gaps

#### 1. `CoordinatorAgent` has zero tests (fixed)

`coordinator.py` is the primary new MS3 component and has no test file. The coordinator prompt, routing logic, and LLM call are completely untested.

**Required tests:**

```python
# Suggested: tests/agents/test_coordinator.py

async def test_coordinator_plan_returns_empty_for_simple_turn():
    # Mock LLM to return empty plan JSON → verify CoordinatorPlan parsed
    ...

async def test_coordinator_plan_routes_to_memory_reader():
    # Mock LLM return with MemoryReader in pre_response
    ...

def test_coordinator_rejects_teacher_in_plan():
    # If LLM tries to include "teacher" in pre/post, verify it's filtered
    ...

async def test_coordinator_raises_on_invalid_api_key():
    ...

def test_build_model_raises_on_unsupported_provider():
    settings = MagicMock()
    settings.chat_provider = "anthropic"
    with pytest.raises(ValueError):
        CoordinatorAgent(settings)
```

#### 2. `_run_specialists` fan-out not tested end-to-end

`test_service.py` tests the _result_ of specialist runs via `_CaptureHistorySpecialist`, but does not test:
- Concurrent execution (two specialists run in parallel)
- One specialist fails, the other succeeds (partial failure isolation)
- Post-response specialists receive `teacher_response` in context

#### 3. Coordinator fallback path not tested

When `coordinator.plan()` raises an exception, the manager falls back to an empty `CoordinatorPlan`. This fallback is not covered by any test.

```python
async def test_coordinator_failure_falls_back_to_empty_plan(...):
    manager.coordinator.plan = AsyncMock(side_effect=RuntimeError("LLM timeout"))
    response, _ = await manager.generate_response(...)
    assert response == "Hi there!"  # teacher still runs
```

#### 4. `_format_pre_results` not tested

`TeacherAgent._format_pre_results` is a pure static method with non-trivial logic (status extraction, truncation, fallback text). It should have its own unit tests.

#### 5. Routing item validation not tested

`RoutingItem.chat_history_size` has `ge=0, le=20`. There is no test that validates the bounds or that an out-of-range value raises `ValidationError`.

---

## Proposals for MS3 Cleanup (Before MS4)

Priority order:

### P1 — Must fix before MS4

| #   | Item                                                               | File                  | Effort |
| --- | ------------------------------------------------------------------ | --------------------- | ------ |
| 1   | Add `test_coordinator.py` with LLM mock tests                      | `tests/agents/`       | M      |
| 2   | Fix log prefix mismatch (`[agents:coordinator]` from `manager.py`) | `manager.py`          | XS     |
| 3   | Add coordinator fallback test                                      | `test_service.py`     | XS     |
| 4   | Add `SpecialistContext` typed input model to `base.py`             | `specialists/base.py` | S      |
| 5   | Annotate `routing_items` param in `_run_specialists`               | `manager.py`          | XS     |

### P2 — Should fix in MS4

| #   | Item                                                                         | File                           | Effort |
| --- | ---------------------------------------------------------------------------- | ------------------------------ | ------ |
| 6   | Extract `build_chat_model()` factory (deduplicate coordinator + teacher)     | `agents/llm.py`                | S      |
| 7   | Fix `SpecialistResult.info_for_teacher` Pydantic v2 `max_length` enforcement | `specialists/base.py`          | XS     |
| 8   | Register at least one live specialist (even a stub) to validate fan-out      | `manager.py`                   | S      |
| 9   | Add `_format_pre_results` unit tests                                         | `test_teacher.py`              | XS     |
| 10  | Add parallel specialist failure isolation test                               | `test_service.py`              | S      |
| 11  | Add `settings.coordinator_model` config option                               | `config.py` / `coordinator.py` | S      |

### P3 — Nice to have

| #   | Item                                                                                       | Effort |
| --- | ------------------------------------------------------------------------------------------ | ------ |
| 12  | Add `overwrite` guard to `SpecialistRegistry.register`                                     | XS     |
| 13  | Make `build_agent` private (`_build_agent`) in `TeacherAgent`                              | XS     |
| 14  | Document Phase F (side-effects persistence) as deferred in `manager.py`                    | XS     |
| 15  | Add `coach_context_size` suggestion in coordinator prompt (currently defaults not exposed) | S      |

---

## MS4 Readiness

The MS3 scaffolding is ready to accept MS4 (`WordKeeper`):

- ✅ `SpecialistRegistry.register()` API is ready
- ✅ Fan-out / fan-in is implemented
- ✅ `post_response` phase is wired and passing `teacher_response`
- ✅ `pre_results` are passed to the teacher

Before landing MS4, the P1 items above should be addressed, especially **`test_coordinator.py`** and the **log prefix fix**, to ensure the coordinating layer is trustworthy before adding the first real specialist.

---

## Summary Scorecard

| Dimension         | Score | Notes                                                                        |
| ----------------- | ----- | ---------------------------------------------------------------------------- |
| Contract fidelity | 7/10  | Phase model correct; tool ownership contract deferred (expected)             |
| Code quality      | 8/10  | Clean, DRY, readable; model builder duplication is the main debt             |
| Test coverage     | 5/10  | Core orchestration tested; coordinator itself has zero tests                 |
| Observability     | 7/10  | Good log convention; log prefix mismatch and Phase F persistence gap         |
| MS4 readiness     | 8/10  | Registry and fan-out ready; need coordinator tests before adding specialists |
