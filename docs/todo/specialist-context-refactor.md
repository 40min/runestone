# Shrink Specialist Context and Bound Pre-Result Prompt Input

## Plan Control

- Dart task: [`jYmtBABn4nIZ` — ref: SpecialistContext bloating](https://app.dartai.com/t/jYmtBABn4nIZ-ref-SpecialistContext-bloating)
- Plan ID: `jYmtBABn4nIZ-specialist-context-v1`
- Plan state: `READY_TO_FREEZE`
- Freeze candidate identity: `jYmtBABn4nIZ-specialist-context-v1@0ef511a895413ad556e928176e088c0e9217fa7a`
- Repository baseline: `0ef511a895413ad556e928176e088c0e9217fa7a`
- SDD tier: `S2`
- Implementation owners: one code owner plus one independent read-only reviewer
- Planning artifact: this document; implementation must not mutate it

## Clarification Log and Assumptions

1. The user approved the research recommendation: remove the two dead `SpecialistContext` fields, retain the shared context for now, bound the real teacher prompt boundary, preserve intentional specialist history, and compare prompt-size evidence.
2. Dart's reliable task-list endpoint confirmed the task ID, title, board (`General/runestone`), status (`Doing`), and assignee. The task-detail endpoint is broken, the browser session is logged out, and the Dart comment endpoint is also broken, so the repository investigation and the user's clarification are the scope authority.
3. `SpecialistContext` is an in-process dispatch envelope, not an LLM message bus. No specialist serializes the full model; each constructs an explicit prompt payload.
4. `pre_results` and `chat_history_size` have no production reader on `SpecialistContext`. Manager-level `pre_results` remains required for teacher input, source extraction, vocabulary deduplication, background orchestration, and persistence flow.
5. The aggregate pre-result prompt budget will be 12,000 characters, including the `[PRE_RESPONSE_SPECIALISTS]` header and line separators. This preserves the existing maximum allowance for one `info_for_teacher` value while preventing multiple specialists from multiplying it.
6. A `no_action` result is omitted only when its `info_for_teacher` value is empty after normalization. A non-empty teacher-facing summary remains visible regardless of status. Error entries remain visible under the existing safe summary contract.
7. NewsAgent keeps a two-message history window. PersonalMemoryKeeper keeps the two-message manager window but exposes only the extracted previous teacher message to its LLM. WordKeeper and LearningMemoryKeeper continue receiving zero raw history.
8. No per-specialist context hierarchy, generic registry redesign, coordinator routing change, model change, database change, deployment change, or new telemetry system is authorized.
9. The agent-schemas package refactor landed as PR #253 during plan review, triggering revision 1's explicit reopen rule. Revision 3 is revalidated against the focused leaf-package shape at `0ef511a895413ad556e928176e088c0e9217fa7a`; the seven-file write set remains sufficient and the consumed schema-refactor TODO is absent.

## SDD Tier Resolution

The canonical resolver input was:

```json
{
  "taskCount": 2,
  "executableOwners": ["specialist-context-owner"],
  "capabilityHints": ["contract-refactor", "prompt-budgeting", "telemetry-validation"],
  "riskFlags": {
    "architecture": true,
    "security": false,
    "performance": true,
    "browser": false,
    "externalEnvironment": false
  },
  "requirementsBytes": 9000,
  "externalSpecification": false
}
```

It was written temporarily to `.tier-request-specialist-context.json`, resolved with:

```bash
agent-lifecycle tier resolve --request .tier-request-specialist-context.json
```

and removed immediately afterward. The resolver returned:

```json
{
  "schemaVersion": "agent-sdd-tier-resolution.v1",
  "tier": "S2",
  "reasons": ["architecture-risk", "performance-risk"],
  "requestDigest": "5b0971d7fa616ec0c2f68a3377e4be62dc96b7750f6e2d9eeeed7f6470a11d49"
}
```

S2 is appropriate because the change alters a shared agent dispatch contract and a teacher prompt-size boundary. The executable code remains one-owner and sequential; the elevated tier adds specification, measurement, and independent review requirements rather than parallel implementation.

## Product Specification

### Problem

`SpecialistContext` currently exposes nine fields to every specialist. Two fields, `pre_results` and `chat_history_size`, have no specialist consumer. Their presence creates false coupling and causes Pydantic to allocate replacement outer list/dict containers even though the payload is never sent to a model.

The actual cross-agent prompt boundary is separate: pre-response `SpecialistResult` objects flow through `TeacherAgent._format_pre_results()`. That formatter correctly excludes machine-oriented artifacts, but it permits up to 12,000 characters per specialist and has no aggregate budget. Multiple pre-specialist summaries can therefore enlarge one TeacherAgent prompt beyond the intended single-result limit. Empty `no_action` results also add non-useful context.

### Desired outcome

- The shared specialist envelope contains only fields with current production consumers.
- Manager-owned orchestration data remains available at the manager boundary without being copied into every specialist context.
- Teacher pre-result context is deterministic, safe, ordered, artifact-free, and capped at 12,000 total characters.
- Empty `no_action` results do not create a teacher system message.
- Specialist routing, persistence, history policy, user-visible behavior, and result schemas remain otherwise unchanged.
- Prompt-size improvement is proved deterministically in tests and observed through existing component token telemetry when a comparable runtime sample is available.

### Non-goals

- Replacing `SpecialistContext` with per-specialist models or explicit method arguments.
- Removing `SpecialistResult`, changing `info_for_teacher`'s per-result validation, or exposing artifacts to the teacher.
- Changing coordinator prompts, available specialists, routing reasons, post-stage scheduling, or retry behavior.
- Reducing TeacherAgent's conversation-history limit or any specialist history window.
- Adding a tokenizer dependency, model provider call, metrics database, dashboard, or production log-level change.
- Combining this work with the agent-schemas package refactor or unrelated Pydantic modernization.

### Behavioral contract

#### Specialist dispatch envelope

`SpecialistContext` retains exactly:

- `message`
- `history`
- `user`
- `teacher_response`
- `vocabulary_candidates`
- `learning_memory_signals`
- `routing_reason`

It no longer defines `pre_results` or `chat_history_size`. `AgentsManager._run_specialists()` no longer accepts or forwards `pre_results`; the effective history size remains a manager-owned local policy used only to slice `history`.

#### Teacher pre-result formatting

- Introduce one named aggregate budget: `PRE_RESULTS_MAX_CHARS = 12000` on `TeacherAgent`.
- Preserve input order for included results.
- Include the `[PRE_RESPONSE_SPECIALISTS]` header only when at least one result survives filtering.
- Omit an entry only when `status == "no_action"` and `info_for_teacher` is not a string or `not info_for_teacher.strip()`. Use this predicate only for inclusion; preserve the original string for an included entry.
- Continue excluding `actions`, `artifacts`, `routing_reason`, latency, and technical error details.
- Continue applying the existing per-value sanitization/truncation behavior, then enforce the aggregate budget including header, separators, names, statuses, and summaries.
- Make newline accounting exact rather than copying the current side-effect formatter's off-by-one behavior. Before every subsequent line, calculate `available = PRE_RESULTS_MAX_CHARS - len("\n".join(lines)) - 1`. If `available <= 0`, stop. If the candidate line exceeds `available`, truncate it to exactly `available` with `_truncate_text()`, append the non-empty remainder, and stop. Otherwise append it and continue. The returned string must never exceed the budget; an exhaustion regression must reach exactly 12,000 characters.
- If all entries are filtered, `_format_pre_results()` returns `""` and `generate_response()` does not add an empty system message.

#### Measurement contract

Character-budget evidence is the deterministic merge gate. Existing model-cost interaction logs may be used for an observational before/after comparison of `usage.input_token` for the `teacher` component, but token telemetry is not an exact acceptance gate because provider tokenization, tool paths, caching, and model versions can drift. No claim of measured token reduction may be made without a comparable sample.

## Requirements

- **R1 — Dead-field removal:** Remove `pre_results` and `chat_history_size` from the shared specialist context and specialist-dispatch call boundary.
- **R2 — Orchestration preservation:** Keep manager-level `pre_results` and all existing uses outside `_run_specialists()` intact.
- **R3 — Aggregate prompt budget:** Bound the complete formatted pre-result system message to 12,000 characters.
- **R4 — Noise filtering:** Do not inject empty `no_action` results or an empty pre-result system message.
- **R5 — Information boundary:** Keep machine artifacts and technical details out of the TeacherAgent prompt.
- **R6 — History preservation:** Preserve current manager-owned history windows and previous-teacher-message behavior.
- **R7 — Evidence:** Provide structural, behavioral, scoped regression, readiness, and independent-review evidence; record observational token evidence only when comparable runtime data exists.
- **R8 — Durable documentation:** Update the authoritative agent-swarm architecture to describe the reduced dispatch envelope and aggregate pre-result prompt budget.

## Developer Overview

This is two related but distinct cleanups:

1. Remove unused data from an internal Python dispatch model. This improves contract accuracy and avoids unnecessary Pydantic container allocation, but it is not itself a token optimization.
2. Bound and filter the serializer that actually enters the TeacherAgent context. This is the token-window optimization.

The manager remains the orchestration owner. Specialists continue receiving one shared context to preserve the registry interface. TeacherAgent remains the only consumer of pre-response specialist summaries. The implementation may mirror the small local loop shape of `_format_recent_side_effects()`, but it must use the newline-aware arithmetic specified above and must not introduce a general prompt-budget abstraction.

## Workstreams and Dependency DAG

### WS1 — Contract cleanup and prompt budgeting

- Owner: `specialist-context-owner`
- Write access: exact write set below
- Depends on: frozen plan and unchanged baseline/import shape
- Goal: implement R1-R6 and R8 in one coherent diff

Steps:

1. Run the refreshed baseline/package-shape preflight below. Confirm no other executor owns any of the seven write-set files and stop on drift.
2. Capture pre-change deterministic formatter evidence with the exact E8 provider-free command.
3. Remove the two dead model fields and the `_run_specialists(pre_results=...)` parameter/keywords without removing any manager-level orchestration use.
4. Add the aggregate TeacherAgent budget and filter using the specified newline-aware arithmetic and existing `_truncate_text()` helper.
5. Ensure `generate_response()` adds the system message only for non-empty formatted output.
6. Add focused regressions for the context field set, dispatch behavior, exact total length, whitespace filtering, ordering, all forbidden prompt fields, safe error summaries, and history preservation.
7. Update the authoritative architecture document.

WS1 preflight:

```bash
test "$(git rev-parse HEAD)" = "0ef511a895413ad556e928176e088c0e9217fa7a"
test ! -f src/runestone/agents/schemas.py
test -f src/runestone/agents/schemas/__init__.py
test ! -s src/runestone/agents/schemas/__init__.py
test -f src/runestone/agents/schemas/chat.py
test -f src/runestone/agents/schemas/coordinator.py
test -f src/runestone/agents/schemas/memory.py
test -f src/runestone/agents/schemas/news.py
test -f src/runestone/agents/schemas/teacher.py
git diff --quiet -- \
  src/runestone/agents/specialists/base.py \
  src/runestone/agents/manager.py \
  src/runestone/agents/specialists/teacher.py \
  tests/agents/specialists/test_base.py \
  tests/agents/test_manager.py \
  tests/agents/test_teacher.py \
  docs/agent-swarm-architecture.md
git diff --cached --quiet -- \
  src/runestone/agents/specialists/base.py \
  src/runestone/agents/manager.py \
  src/runestone/agents/specialists/teacher.py \
  tests/agents/specialists/test_base.py \
  tests/agents/test_manager.py \
  tests/agents/test_teacher.py \
  docs/agent-swarm-architecture.md
```

The executor must also reserve or confirm exclusive ownership of the seven paths through the active orchestration mechanism. Filesystem checks cannot prove that another worker is about to edit them. If the baseline, focused schema-package shape, imports, or owned files have drifted, stop and reopen this plan.

### WS2 — Validation, observation, and review

- Owner: lead for test execution; independent reviewer for final read-only audit
- Write access: none except mutable run artifacts outside the plan
- Depends on: WS1 complete
- Goal: prove the bounded contract and check for regressions

Steps:

1. Run structural and focused evidence commands.
2. Run the three baseline test files and then `make check-readiness`.
3. Compare deterministic formatted lengths against the captured baseline.
4. Inspect already-existing comparable model-cost logs, or use an already-authorized local/mock provider, if either is available. Any replay against an external model provider requires separate authority even when credentials or configuration already exist. Do not enable debug logging globally. Record unavailable or incomparable observation as `not_observed`.
5. Submit the final diff and evidence to independent implementation audit.

```text
Freeze plan
   └── WS1 contract cleanup + prompt budget + tests + docs
         ├── structural evidence
         ├── focused regression evidence
         └── deterministic size comparison
               └── readiness gate
                     ├── optional comparable token observation
                     └── independent implementation audit
```

No files are shared between concurrent executable owners; implementation is sequential.

## Exact Write-Set Manifest

The implementation owner has exclusive write ownership of:

### Production

- `src/runestone/agents/specialists/base.py`
- `src/runestone/agents/manager.py`
- `src/runestone/agents/specialists/teacher.py`

### Tests

- `tests/agents/specialists/test_base.py`
- `tests/agents/test_manager.py`
- `tests/agents/test_teacher.py`

### Durable documentation

- `docs/agent-swarm-architecture.md`

No other path may be modified. If implementation discovers a required write outside this manifest, stops and returns the plan for independent re-review before editing that path.

## Read-Only Inputs and Forbidden Writes

Read-only authority and inputs:

- `AGENTS.md`
- `Makefile`
- `pyproject.toml`
- `docs/todo/specialist-context-refactor.md`
- focused schema leaves under `src/runestone/agents/schemas/`
- specialist implementations under `src/runestone/agents/specialists/`
- current model-cost tracking under `src/runestone/model_costs/`
- current direct references returned by `rg`/AST inspection

Forbidden without a reopened plan:

- changes to specialist prompt payloads other than TeacherAgent pre-result formatting
- per-specialist context classes, registry generics, adapters, facades, or fallback dispatch
- changes to `SpecialistResult` fields or the 12,000-character per-result validator
- coordinator schemas/prompts, history sizes, routing policy, or specialist availability
- side-effect persistence, repositories, database models, migrations, API, frontend, dependencies, lockfiles, configuration, deployment, or global logging level
- production model calls or paid telemetry experiments without separate authority
- staging, commit, push, PR creation, deployment, Dart mutation, or publication unless separately authorized

## Acceptance Criteria and Evidence Contract

| ID | Acceptance criterion | Requirements | Evidence |
| --- | --- | --- | --- |
| **AC1** | `SpecialistContext` has exactly the seven retained fields and no dead fields. | R1 | E1, E2 |
| **AC2** | `_run_specialists()` no longer accepts/forwards `pre_results`, while manager-level teacher/source/dedupe/background uses remain intact. | R1, R2 | E1, E3 |
| **AC3** | Included pre-results preserve order, exclude artifacts, and produce at most 12,000 total characters including header/separators. | R3, R5 | E4 |
| **AC4** | Empty `no_action` results are omitted; non-empty summaries remain; all-filtered input creates no TeacherAgent system message. | R4 | E4 |
| **AC5** | NewsAgent, PersonalMemoryKeeper, WordKeeper, and LearningMemoryKeeper retain their current effective history behavior. | R6 | E3 |
| **AC6** | The affected baseline suite passes and repository readiness reports no implementation regression. | R1-R6 | E5, E6 |
| **AC7** | Architecture documentation describes the in-process envelope separately from the bounded LLM prompt boundary. | R8 | E7 |
| **AC8** | Deterministic output size does not increase for any baseline scenario and decreases for multi-result and empty-no-action scenarios; token claims remain explicitly observational. | R3, R4, R7 | E8 |
| **AC9** | Independent final review finds no Medium or High correctness, scope, or evidence issue. | R1-R8 | E9 |

### E1 — Static dead-field and call-boundary inventory

```bash
rg -n "pre_results|chat_history_size" src/runestone/agents/specialists/base.py
rg -n "pre_results=pre_results or \[\]|chat_history_size=effective_history_size" src/runestone/agents/manager.py
rg -n "def _run_specialists|pre_results" src/runestone/agents/manager.py
```

The first two commands must return no matches. The third is a bounded manual check: `_run_specialists` has no `pre_results` parameter, while legitimate manager-level `pre_results` uses for teacher input, sources, dedupe, background lifecycle, and persistence remain.

### E2 — Context model contract

Add a focused test asserting:

```python
set(SpecialistContext.model_fields) == {
    "message",
    "history",
    "user",
    "teacher_response",
    "vocabulary_candidates",
    "learning_memory_signals",
    "routing_reason",
}
```

Run:

```bash
.venv/bin/pytest -q tests/agents/specialists/test_base.py
```

### E3 — Manager dispatch and history regressions

```bash
.venv/bin/pytest -q tests/agents/test_manager.py
```

The existing news two-message, personal two-message, word zero-history/previous-teacher, and learning zero-history tests must remain enabled and pass. Add or adjust a capture test proving dead fields are absent without weakening these assertions.

### E4 — Teacher pre-result formatter regressions

```bash
.venv/bin/pytest -q tests/agents/test_teacher.py -k "pre_result or generate_response"
```

Required test cases:

- one ordinary action result remains unchanged;
- sentinel values from `artifacts`, `actions`, `routing_reason`, `latency_ms`, and a raw technical-error field are absent;
- a safe non-empty `info_for_teacher` summary from an `error` result remains visible while its raw technical-error sentinel stays absent;
- two long included results produce `len(formatted) == TeacherAgent.PRE_RESULTS_MAX_CHARS == 12000` in the exhaustion case;
- order is preserved until the aggregate budget is exhausted;
- an empty `no_action` entry is omitted;
- a whitespace-only `no_action` entry is omitted;
- a `no_action` entry with non-empty teacher information remains;
- all-filtered input returns an empty string and does not append a pre-result `SystemMessage`;
- aggregate truncation emits a bounded warning.

### E5 — Affected baseline suite

```bash
.venv/bin/pytest -q \
  tests/agents/specialists/test_base.py \
  tests/agents/test_manager.py \
  tests/agents/test_teacher.py
```

Planning baseline on `0ef511a895413ad556e928176e088c0e9217fa7a`: **141 passed**, with four existing deprecation warnings.

### E6 — Repository readiness

```bash
make check-readiness
```

No dependency, auth, configuration, or security surface changes are planned, so `make security-check` is not an additional gate.

### E7 — Documentation and scope audit

```bash
git diff -- docs/agent-swarm-architecture.md
rg -n "dispatch envelope|PRE_RESPONSE_SPECIALISTS|12,000|manager-owned.*history" \
  docs/agent-swarm-architecture.md
git diff --check
git diff --name-status
git status --short
git ls-files --others --exclude-standard
```

Inspect the documentation diff, not just grep success. It must explicitly state all seven retained dispatch-envelope fields, preserve the manager-owned history policy, identify `[PRE_RESPONSE_SPECIALISTS]` as the LLM serialization boundary, and record the aggregate 12,000-character budget. The complete tracked and untracked repository status must be limited to the exact implementation write set plus this planning artifact; it must not contain unrelated cleanup.

### E8 — Reproducible size evidence and optional token observation

Before editing production code, run the following provider-free command with `EVIDENCE_STAGE=baseline`. After implementation, run the identical command with `EVIDENCE_STAGE=post`. It records the repository identity, exact fixture payloads, input/output hashes, formatted text, and character counts in separate JSON artifacts.

```bash
EVIDENCE_STAGE=baseline .venv/bin/python - <<'PY'
import hashlib
import json
import os
import subprocess
from pathlib import Path

from runestone.agents.specialists.teacher import TeacherAgent

stage = os.environ["EVIDENCE_STAGE"]
if stage not in {"baseline", "post"}:
    raise SystemExit("EVIDENCE_STAGE must be baseline or post")

cases = {
    "ordinary": [
        {
            "name": "word_keeper",
            "result": {
                "status": "action_taken",
                "info_for_teacher": "Saved 2 vocabulary items.",
                "artifacts": {"sentinel": "SECRET"},
            },
        }
    ],
    "double_max": [
        {"name": "news_agent", "result": {"status": "action_taken", "info_for_teacher": "x" * 12000}},
        {"name": "word_keeper", "result": {"status": "action_taken", "info_for_teacher": "y" * 12000}},
    ],
    "empty_no_action": [
        {"name": "news_agent", "result": {"status": "no_action", "info_for_teacher": ""}}
    ],
    "whitespace_no_action": [
        {"name": "news_agent", "result": {"status": "no_action", "info_for_teacher": "  \n\t  "}}
    ],
}

evidence = {
    "schema_version": "specialist-context-size-evidence.v1",
    "stage": stage,
    "repository_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "scenarios": {},
}
for scenario_id, payload in cases.items():
    input_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    output = TeacherAgent._format_pre_results(payload)
    evidence["scenarios"][scenario_id] = {
        "input": payload,
        "input_sha256": hashlib.sha256(input_json.encode()).hexdigest(),
        "formatted_chars": len(output),
        "formatted_sha256": hashlib.sha256(output.encode()).hexdigest(),
        "formatted_text": output,
    }

target_dir = Path("/tmp/runestone-specialist-context-evidence/0ef511a")
target_dir.mkdir(parents=True, exist_ok=True)
target = target_dir / f"{stage}.json"
target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
print(target)
PY
```

The independently reproduced planning baseline for these exact fixtures is:

| Scenario | Baseline characters | Baseline SHA-256 |
| --- | ---: | --- |
| `ordinary` | 82 | `87e1e882ab4331449b603c031ecaf9fee5c9d02ddb19c09ca6c9843133dccf60` |
| `double_max` | 24,087 | `1c6687fe0af2e3dddc66c5660610258678b08987063abebd144bc00b0309b7be` |
| `empty_no_action` | 60 | `fb127f42bba4a4a3a860b94d713f9ce0c318f4d1b576ea2486f50c7293a88b9d` |
| `whitespace_no_action` | 59 | `6aad5e925bc37a9446df611217d0c25c573f78279b03ba61cec09a856cf3a175` |

Compare the two artifacts with:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

root = Path("/tmp/runestone-specialist-context-evidence/0ef511a")
baseline = json.loads((root / "baseline.json").read_text())
post = json.loads((root / "post.json").read_text())
freeze_head = "0ef511a895413ad556e928176e088c0e9217fa7a"
assert baseline["repository_head"] == freeze_head
assert post["repository_head"] == freeze_head
expected_baseline = {
    "ordinary": (82, "87e1e882ab4331449b603c031ecaf9fee5c9d02ddb19c09ca6c9843133dccf60"),
    "double_max": (24087, "1c6687fe0af2e3dddc66c5660610258678b08987063abebd144bc00b0309b7be"),
    "empty_no_action": (60, "fb127f42bba4a4a3a860b94d713f9ce0c318f4d1b576ea2486f50c7293a88b9d"),
    "whitespace_no_action": (59, "6aad5e925bc37a9446df611217d0c25c573f78279b03ba61cec09a856cf3a175"),
}
for scenario_id, (chars, digest) in expected_baseline.items():
    before = baseline["scenarios"][scenario_id]
    after = post["scenarios"][scenario_id]
    assert (before["formatted_chars"], before["formatted_sha256"]) == (chars, digest)
    assert before["input_sha256"] == after["input_sha256"]

assert post["scenarios"]["ordinary"]["formatted_text"] == baseline["scenarios"]["ordinary"]["formatted_text"]
assert post["scenarios"]["double_max"]["formatted_chars"] == 12000
assert post["scenarios"]["empty_no_action"]["formatted_chars"] == 0
assert post["scenarios"]["whitespace_no_action"]["formatted_chars"] == 0
print("specialist-context size evidence: PASS")
PY
```

If already-existing comparable model-cost logs are available, record `component=teacher` and `usage.input_token` for the same provider/model/scenario. An already-authorized local/mock provider is also acceptable. Any external-provider replay requires separate authority. Label provider/model/cache/tool differences and treat unavailable or incomparable data as `not_observed`, not as failure and not as proof of no improvement.

### E9 — Independent implementation audit

The reviewer receives the frozen plan, diff, E1-E8 outputs, and baseline identity. The reviewer checks requirement traceability, exact write scope, prompt-boundary safety, history preservation, validation truthfulness, and any baseline drift before issuing `READY`, `CHANGES_REQUIRED`, or `BLOCKED`.

## Rollback and Release Safety

- The change has no database or persisted-data migration. Rollback is a normal code revert of the exact write set.
- A formatter defect can affect teacher context quality but not stored specialist artifacts. Existing artifacts remain available for source extraction, dedupe, and side-effect persistence.
- If focused tests show loss of required teacher information, stop and revise the filtering/budget rule; do not restore dead context fields as a workaround.
- If readiness fails outside the affected surface, distinguish baseline failure from implementation regression and report it precisely.
- Deployment and production observation are outside this plan unless separately authorized.

## Execution Budget and Context Profile

- Implementation budget: one owner, one coherent code/test/docs workstream.
- Independent review budget: one plan audit with one correction round; one final implementation audit with one focused correction round.
- Test retry budget: rerun only the failing focused command after an in-scope fix; rerun E5 and E6 after focused checks pass.
- Context budget: implementer should read this plan and `AGENTS.md`, then use bounded anchors rather than whole-file reads for large files: `class SpecialistContext`, `_effective_specialist_history_size`, `_run_specialists`, `_format_pre_results`, `_format_recent_side_effects`, and tests whose names contain `pre_result`, `history`, or `specialist_context`. Read only directly referenced specialist/model-cost inputs when an anchor requires it. Broad repository scans are not authority.
- Small-context packet (`small-context-profile.v1`): **Plan Control**, **Clarification Log and Assumptions**, **Product Specification / Behavioral contract**, **Requirements**, **Developer Overview**, **Workstreams**, **Exact Write-Set Manifest**, **Read-Only Inputs and Forbidden Writes**, and **Acceptance Criteria and Evidence Contract**, plus the bounded anchors above and `AGENTS.md`. Chat history is not authority.
- Reopen triggers: baseline or focused schema-package/import-shape drift, required write outside the manifest, change to filtering semantics or aggregate budget, new telemetry infrastructure, or any history/routing behavior change.

## Plan Lock and Mutable Run Artifacts

Once this candidate reaches `READY_TO_FREEZE`, the freeze identity above is the immutable planning authority. Implementation evidence, command outputs, diffs, observations, and review notes are mutable run artifacts and must not be written into this plan during execution. If a contract change is needed, reopen and independently review a new plan revision rather than editing a frozen plan in place.

## Independent Plan Review Request

The reviewer must use the `audit-agent-plan` review matrix and inspect this document plus the repository baseline. Required output:

1. findings ordered by severity;
2. requirement-to-acceptance-to-evidence coverage matrix;
3. SDD tier and assumption assessment;
4. exact write-set, overlap, and dependency-DAG assessment;
5. validation-command, performance-evidence, and small-context-fit assessment;
6. freeze verdict: `READY_TO_FREEZE`, `CHANGES_REQUIRED`, or `BLOCKED`;
7. exact edits for any non-ready verdict.

## Review Record

### Audit 1 — `CHANGES_REQUIRED`

The independent reviewer found no High issue and confirmed the scope, S2 tier, seven-file write set, sequential DAG, and 141-test baseline. Six Medium and two Low gaps prevented freeze:

- ambiguous newline accounting could reproduce the existing side-effect formatter's off-by-one behavior;
- whitespace-only `no_action` normalization was undefined;
- forbidden prompt-field evidence was incomplete;
- size comparison was not independently reproducible;
- configured external providers could be misread as replay authority;
- the overlapping schema-package plan lacked an executable mutual-exclusion handoff;
- the small-context packet required overly broad file reads;
- durable-documentation evidence was too weak.

Revision 2 defines exact arithmetic and normalization, expands prompt-boundary tests, adds provider-free artifacts and baseline hashes, makes external calls separately authorized, adds symmetric baseline/ownership preflight, bounds the context packet, and strengthens documentation evidence.

### Audit 2 — `CHANGES_REQUIRED`

Revision 2 was re-audited after PR #253 landed during planning. The reviewer confirmed all Audit 1 issues were resolved, but returned `CHANGES_REQUIRED` because the repository had crossed the documented schema-refactor reopen trigger. It also required E8 to assert the freeze identity and E7 to include untracked files.

Revision 3 refreshes the baseline and package-shape preflight, removes consumed-plan references, asserts both evidence artifacts against the freeze identity, and inventories untracked files.

### Audit 3 — `READY_TO_FREEZE`

The independent reviewer found no High, Medium, or Low findings and confirmed:

- R1-R8 have complete acceptance and evidence coverage;
- the freeze identity matches the current post-PR-#253 baseline;
- the focused schema-package preflight and seven-path write set are correct;
- exact newline accounting, whitespace filtering, forbidden-field isolation, and safe error summaries are fully specified;
- E7 inventories tracked and untracked scope;
- E8 is provider-free, reproducible, and asserts both artifacts against the freeze identity;
- the sequential DAG, ownership, retry/review budgets, small-context packet, and plan/run separation are enforceable.

Verdict: `READY_TO_FREEZE`. Implementation remains separately authorized work.
