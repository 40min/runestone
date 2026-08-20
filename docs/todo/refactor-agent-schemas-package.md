# Refactor Agent Schemas Into a Focused Package

## Plan Control

- Dart task: [`GoHUvEPacDic` — Refactor agent schemas module into focused package](https://app.dartai.com/t/GoHUvEPacDic-Refactor-agent-schemas-module)
- Plan ID: `GoHUvEPacDic-agent-schemas-v2`
- Plan state: `READY_TO_FREEZE`
- Freeze candidate identity: `GoHUvEPacDic-agent-schemas-v2@5aeab1cd32affe74c436f1d0fe42ff64de065ec9`
- Repository baseline: `5aeab1cd32affe74c436f1d0fe42ff64de065ec9`
- SDD tier: `S0`
- Implementation owners: one
- Planning artifact: this document; implementation must not mutate it

## Clarification Log and Assumptions

1. Dart's reliable task-list endpoint confirms the task title, board (`General/runestone`), status (`Doing`), and priority (`Medium`). The task-detail endpoint fails in the current connector, the task has no comments, and the available browser session is not authenticated, so no separate task description was available.
2. The task title and current repository shape are treated as the complete scope: replace the mixed `src/runestone/agents/schemas.py` module with focused leaf modules under `src/runestone/agents/schemas/` without changing runtime behavior.
3. `runestone.agents.schemas` is an internal module, not a supported third-party Python API. Package-level compatibility re-exports are therefore out of scope and would also conflict with the repository rule that package `__init__.py` files stay empty.
4. Schema field names, defaults, validators, descriptions, Pydantic configuration, dataclass options, and serialized shapes must remain unchanged. This is a structural refactor, not a schema redesign.
5. `NewsSpecialistArticle` currently has no production caller. It remains present because removing dead types is separate cleanup and would widen a behavior-preserving refactor.
6. No database, API wire-format, frontend, dependency, deployment, or migration work is required.

If assumption 3 is false and an external caller needs `from runestone.agents.schemas import ...`, stop before implementation. Supporting that import requires an explicit reviewed exception to the empty-`__init__.py` policy and a revised plan.

## SDD Tier Resolution

The canonical resolver input was:

```json
{
  "taskCount": 1,
  "executableOwners": ["schema-refactor-owner"],
  "capabilityHints": ["bounded-mechanical"],
  "riskFlags": {
    "architecture": false,
    "security": false,
    "performance": false,
    "browser": false,
    "externalEnvironment": false
  },
  "requirementsBytes": 0,
  "externalSpecification": false
}
```

It was saved as `.tier-request.json` for the command and removed immediately after resolution:

```bash
agent-lifecycle tier resolve --request .tier-request.json
```

The repository-local resolver returned:

```json
{
  "schemaVersion": "agent-sdd-tier-resolution.v1",
  "tier": "S0",
  "reasons": ["single-owner-bounded-mechanical-low-risk"],
  "requestDigest": "a97a5a051d063a1caa8083d7fae2c3e9e33db0066ff38a34f30e2489f8566082"
}
```

The change has one executable owner, one bounded structural task, no intended behavior change, and no elevated architecture, security, performance, browser, or external-environment risk. Independent plan review is still required by the request before this candidate is ready to freeze.

## Developer Overview

`src/runestone/agents/schemas.py` currently mixes six concerns: chat transport models, news payloads, memory signals/status, Teacher output, coordinator state, and a shared emotion normalizer. This forces unrelated consumers to depend on one broad module and lets constants such as `TeacherEmotion` leak through an incidental import.

The target state is an empty `runestone.agents.schemas` package containing five cohesive leaf modules. Every production and test consumer imports the owning leaf module directly. Constants continue to come from `runestone.constants`. The split must preserve all existing runtime and validation behavior.

No orchestration flow changes. The change only moves definitions and updates imports.

## Requirements

- **R1 — Focused ownership:** Each existing symbol from `agents/schemas.py` has exactly one clear leaf-module owner.
- **R2 — Behavior preservation:** All schema validation, normalization, defaults, serialization, dataclass semantics, and API response shapes remain identical.
- **R3 — Explicit imports:** Production and test code imports schema symbols from leaf modules and imports `TeacherEmotion` / `DEFAULT_TEACHER_EMOTION` directly from `runestone.constants`.
- **R4 — Empty package boundary:** `src/runestone/agents/schemas/__init__.py` is byte-empty; no compatibility exports or `__all__` are introduced.
- **R5 — Clean replacement:** The old `src/runestone/agents/schemas.py` file and all direct symbol imports from `runestone.agents.schemas` are removed.
- **R6 — Regression evidence:** Affected agent, API, and service tests pass separately by fixture scope, followed by the repository readiness gate.

## Target Package Design

Create this package:

```text
src/runestone/agents/schemas/
├── __init__.py       # empty by policy
├── chat.py           # chat/API payloads and emotion normalization
├── coordinator.py    # routing, side-effect, and coordinator lifecycle payloads
├── memory.py         # memory status and Teacher-declared memory signals
├── news.py           # news citation and specialist article payloads
└── teacher.py        # structured Teacher output and internal generation result
```

### Exact symbol ownership

| Leaf module | Symbols moved without behavior changes |
| --- | --- |
| `news.py` | `NewsSource`, `NewsSpecialistArticle` |
| `chat.py` | `normalize_teacher_emotion`, `ChatMessage`, `ChatRequest`, `ChatResponse`, `ChatHistoryResponse`, `ImageChatResponse`, `VoiceTranscriptionResponse` |
| `memory.py` | `AgentPersonalInfoStatus`, `LearningMemorySignal` |
| `teacher.py` | `TeacherOutput`, `TeacherGenerationResult` |
| `coordinator.py` | `RoutingItem`, `CoordinatorPlan`, `TeacherSideEffect`, `CoordinatorRow` |

### Internal dependency direction

```text
news.py ──────────────────────► chat.py ─────────────┐
runestone.constants ──────────► chat.py              │
runestone.constants ─────────────────────────────────┤
memory.py ───────────────────────────────────────────┤──► teacher.py
runestone.schemas.vocabulary_save ───────────────────┘

coordinator.py  # independent of the other schema leaves
```

Rules:

- `chat.py` imports `NewsSource` from `news.py` and emotion constants from `runestone.constants`.
- `teacher.py` imports `TeacherEmotion` and `DEFAULT_TEACHER_EMOTION` directly from `runestone.constants`, `normalize_teacher_emotion` from `chat.py`, `LearningMemorySignal` from `memory.py`, and `WordSaveCandidate` from the existing shared vocabulary schema.
- No leaf imports from the package `__init__.py`.
- No new base class, registry, facade, dynamic loader, or compatibility module is needed.

## Implementation Workstream

### WS1 — Package extraction and import migration

- Owner: `schema-refactor-owner`
- Depends on: none
- Parallel execution: none; this is the only executable workstream
- Goal: perform the structural split and migrate all repository consumers in one coherent change

Steps:

1. Create the empty package initializer and the five leaf modules shown above.
2. Move definitions verbatim by ownership table, preserving module/class/function docstrings where they still describe the new owner.
3. Use module-level imports and preserve the existing Python 3.13 typing style; do not add `from __future__ import annotations`, local imports, keyword-only API markers, or forwarding wrappers.
4. Update every production consumer to import from the owning leaf. Where current code imports `TeacherEmotion` or `DEFAULT_TEACHER_EMOTION` through `agents.schemas`, import it directly from `runestone.constants` instead.
5. Update test imports to the same leaf modules; tests must exercise the production import contract rather than a compatibility facade.
6. Delete `src/runestone/agents/schemas.py` only after all definitions and imports are accounted for.
7. Run the structural checks, scoped regression tests, and final readiness gate in the evidence plan.

## Exact Write-Set Manifest

The implementation owner has exclusive write ownership of the following paths.

### Package replacement

- `src/runestone/agents/schemas.py` — delete
- `src/runestone/agents/schemas/__init__.py` — create empty
- `src/runestone/agents/schemas/chat.py` — create
- `src/runestone/agents/schemas/coordinator.py` — create
- `src/runestone/agents/schemas/memory.py` — create
- `src/runestone/agents/schemas/news.py` — create
- `src/runestone/agents/schemas/teacher.py` — create

### Production import migration

- `src/runestone/agents/coordinator.py`
- `src/runestone/agents/manager.py`
- `src/runestone/agents/prompts.py`
- `src/runestone/agents/specialists/base.py`
- `src/runestone/agents/specialists/learning_memory_keeper.py`
- `src/runestone/agents/specialists/memory_maintainer/personal_info.py`
- `src/runestone/agents/specialists/teacher.py`
- `src/runestone/agents/tools/memory.py`
- `src/runestone/api/chat_endpoints.py`
- `src/runestone/services/agent_side_effect_service.py`
- `src/runestone/services/chat_service.py`
- `src/runestone/services/memory_item_service.py`

### Test import migration

- `tests/agents/test_coordinator.py`
- `tests/agents/test_coordinator_schemas.py`
- `tests/agents/test_manager.py`
- `tests/agents/test_teacher.py`
- `tests/agents/specialists/test_learning_memory_keeper.py`
- `tests/agents/specialists/test_personal_memory_keeper.py`
- `tests/agents/specialists/test_word_keeper.py`
- `tests/services/test_agent_side_effect_service.py`
- `tests/services/test_memory_item_service.py`

No other path may be modified without reopening this plan. If implementation discovers another direct import, stop, amend the manifest and inventory evidence, and return the candidate for independent plan review before editing that path.

## Read-Only Inputs and Forbidden Writes

Read-only authority/input paths:

- `AGENTS.md`
- `pyproject.toml`
- `Makefile`
- `docs/todo/refactor-agent-schemas-package.md`
- current callers returned by `rg -n "from runestone\\.agents\\.schemas|import runestone\\.agents\\.schemas" src tests`

Forbidden without a reopened plan:

- Alembic migrations, database models, repositories, or persisted data
- API routes or response-field changes beyond import paths
- frontend files
- dependency or lock files
- deployment/configuration files
- unrelated schema cleanup, renaming, validator rewrites, Pydantic modernization, or dead-code removal
- package-level re-exports in any `__init__.py`

## Acceptance Criteria and Evidence Contract

| ID | Acceptance criterion | Requirements | Evidence |
| --- | --- | --- | --- |
| **AC1** | The old module is replaced by the five-leaf package and an empty initializer. | R1, R4, R5 | E1 |
| **AC2** | Every symbol in the ownership table exists once and retains its prior definition semantics. | R1, R2 | E2, E3 |
| **AC3** | No production or test file imports symbols from package root; emotion constants come directly from `runestone.constants`. | R3, R5 | E2 |
| **AC4** | Affected agent schema/orchestration tests pass. | R2, R6 | E3 |
| **AC5** | Affected API chat tests pass. | R2, R6 | E4 |
| **AC6** | Affected service tests pass under service-scoped fixture discovery. | R2, R6 | E5 |
| **AC7** | The repository-wide readiness gate passes with no implementation-related regression. | R2, R6 | E6 |
| **AC8** | Final review confirms the diff is limited to the exact write set and contains no compatibility facade or unrelated cleanup. | R1–R6 | E7 |

### Evidence commands

**E1 — Package shape**

```bash
test ! -f src/runestone/agents/schemas.py
test -f src/runestone/agents/schemas/__init__.py
test ! -s src/runestone/agents/schemas/__init__.py
find src/runestone/agents/schemas -maxdepth 1 -type f -print | sort
```

Expected files are only `__init__.py`, `chat.py`, `coordinator.py`, `memory.py`, `news.py`, and `teacher.py`.

**E2 — Import and symbol inventory**

```bash
rg -n "from (runestone\.agents\.schemas|\.+schemas) import|from runestone\.agents import schemas|from \.+ import schemas|^import runestone\.agents\.schemas([[:space:]]|$)" src tests
rg -n "^(class|def) (NewsSource|NewsSpecialistArticle|AgentPersonalInfoStatus|ChatMessage|ChatRequest|ChatResponse|ChatHistoryResponse|ImageChatResponse|LearningMemorySignal|TeacherOutput|TeacherGenerationResult|VoiceTranscriptionResponse|RoutingItem|CoordinatorPlan|TeacherSideEffect|CoordinatorRow|normalize_teacher_emotion)\b" src/runestone/agents/schemas
rg -n "TeacherEmotion|DEFAULT_TEACHER_EMOTION" \
  src/runestone/agents/schemas \
  src/runestone/agents/manager.py \
  src/runestone/agents/specialists/teacher.py \
  src/runestone/services/chat_service.py
```

The first command must return no package-root imports, whether absolute or relative. The second must show every moved symbol exactly once. Inspect the bounded third result: every import of `TeacherEmotion` or `DEFAULT_TEACHER_EMOTION` must come directly from `runestone.constants`; the schema leaves may use those imported names but must not redefine them.

**E3 — Agent regression tests**

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python -m pytest \
  tests/agents/test_coordinator_schemas.py \
  tests/agents/test_coordinator.py \
  tests/agents/test_manager.py \
  tests/agents/test_teacher.py \
  tests/agents/specialists/test_learning_memory_keeper.py \
  tests/agents/specialists/test_personal_memory_keeper.py \
  tests/agents/specialists/test_word_keeper.py \
  -v
```

**E4 — API regression tests**

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python -m pytest tests/api/test_chat_endpoints.py -v
```

**E5 — Service regression tests**

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python -m pytest \
  tests/services/test_chat_service.py \
  tests/services/test_agent_side_effect_service.py \
  tests/services/test_memory_item_service.py \
  -v
```

Agent, API, and service paths intentionally run as separate commands so directory-scoped fixtures are discovered reproducibly.

**E6 — Repository readiness**

```bash
make check-readiness
```

No dependency or security surface changes, so `make security-check` is not an additional gate for this task.

**E7 — Final scope audit**

```bash
git diff --check
git diff --name-status -- src/runestone/agents tests/agents src/runestone/api/chat_endpoints.py \
  src/runestone/services tests/api/test_chat_endpoints.py tests/services
```

Inspect the diff against the write-set manifest and confirm that moved definitions differ only where import paths or now-inaccurate module docstrings require it.

## Execution Budget and Context Profile

- Implementation budget: one owner, one coherent change, no parallel workers.
- Review budget: one independent code review after implementation; one focused correction round if findings are limited to this plan.
- Retry budget: rerun only the failing scoped command after an in-scope fix, then rerun `make check-readiness` once the scoped checks pass.
- Escalation boundary: reopen planning for any behavior change, package-root compatibility requirement, additional schema ownership decision, new dependency, migration, or write outside the manifest.
- Small-context packet: the implementer needs **Plan Control**, **Clarification Log and Assumptions**, **Requirements**, **Target Package Design**, **Implementation Workstream**, **Exact Write-Set Manifest**, **Read-Only Inputs and Forbidden Writes**, and **Acceptance Criteria and Evidence Contract**, plus `AGENTS.md`. Chat history is not authority.

## Dependency DAG and Handoff

```text
WS1 package extraction + import migration
  ├── E1/E2 structural evidence
  ├── E3/E4/E5 scoped regression evidence
  └── E6 readiness evidence
        └── E7 independent final implementation audit
```

The implementation owner hands off the diff and command outputs identified as E1–E6. The final reviewer is read-only and returns findings first, verifies E7, and issues one of: `READY`, `CHANGES_REQUIRED`, or `BLOCKED`. Publication, commit, push, PR creation, and Dart status changes are outside this implementation plan unless separately authorized.

## Independent Plan Review Request

The reviewer must use the `audit-agent-plan` review matrix and inspect this document plus the repository baseline. Required review outputs:

1. findings ordered by severity;
2. requirement-to-acceptance-to-evidence coverage check;
3. SDD tier and scope assessment;
4. ownership/write-set and dependency-DAG assessment;
5. validation-command and small-context-fit assessment;
6. freeze verdict: `READY_TO_FREEZE`, `CHANGES_REQUIRED`, or `BLOCKED`;
7. exact required edits for any non-ready verdict.

## Review Record

### Audit 1 — `CHANGES_REQUIRED`

The independent `audit-agent-plan` sub-agent found three Medium and three Low issues:

- contradictory handling of newly discovered write paths;
- incomplete evidence for relative package-root imports and direct emotion-constant ownership;
- a missing `runestone.constants -> teacher.py` dependency edge;
- an incomplete small-context packet;
- an initializer existence check that could pass when the file was absent;
- tier evidence without the exact invocation and canonical request.

Revision 2 resolved each finding in the corresponding contract/evidence section above and was submitted for the fresh audit recorded below.

### Audit 2 — `READY_TO_FREEZE`

The same independent reviewer re-audited revision 2 and confirmed:

- no Medium or High findings remain;
- R1–R6 have complete acceptance and evidence coverage;
- all 12 production and 9 test consumers are covered by the exact write set;
- the five-module split is minimal, cohesive, and acyclic;
- empty-initializer and import-origin evidence is sufficient;
- the S0 tier is justified and reproducible;
- the execution, retry, review, and small-context budgets are appropriate.

During the read-only audit, the reviewer also verified the scoped commands against the current baseline: 195 agent tests, 24 API tests, and 54 service tests passed. Implementation must still rerun E1–E7 on its own diff. Verdict: `READY_TO_FREEZE`.
