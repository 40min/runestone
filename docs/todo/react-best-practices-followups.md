# Frontend React Follow-Ups

Status: `FREEZE_CANDIDATE`

SDD tier: `S2` (multiple independently releasable frontend slices plus browser evidence)

Reviewed: 2026-08-31 at `869c95dfe27e0f60048d67c09c6d1ade48e196f9`

Task: [inspect frontend's code -- request advices on optimisation](https://app.dartai.com/t/CKaggf6UgudV-inspect-frontends-code-request)

## Developer overview

This plan refreshes the April 7, 2026 React audit against the current frontend. The original direction is still sound, but several statements are now only partly true: Login and Register already submit through their forms, compact FileUpload zoom already supports keyboard activation, and `DataTable.onRowClick` has no production caller. The remaining work should preserve native browser and MUI behavior, remove obsolete flexibility, and avoid a broad visual or state-management rewrite.

The user-visible result is a frontend where every action has an equivalent keyboard-operable native control, whose profile form preserves browser constraint validation, and whose chat synchronization no longer suppresses Hook dependency checks. A separate lean-cleanup slice removes current code and dependencies that have no remaining purpose.

No backend contract, database, visual redesign, router migration, state-management library, React Compiler rollout, or MUI/Tailwind replacement is part of this work.

## Clarification log and assumptions

- The Dart task has an empty description, so the repository, the existing todo, and the task title define scope.
- This document prepares future implementation; it does not authorize staging, committing, pushing, opening a PR, or completing the Dart task.
- Current behavior and styling are the compatibility baseline unless an acceptance criterion below explicitly changes interaction semantics.
- The three implementation slices are separate review and rollback units. Do not combine them into one large refactor PR.
- Accessibility work prefers native `button`, MUI `IconButton`, and MUI `Dialog` behavior over hand-written `role`, `tabIndex`, and keyboard handlers.
- Package removals must be proven by build, focused tests, lockfile validation, and the security gate; package declarations alone are not sufficient evidence.
- Browser evidence requires a locally configured active test account. If one is unavailable, the browser gate remains blocked rather than being replaced by synthetic evidence.

## Research basis

Current primary guidance still supports the core audit:

- React says suppressing `react-hooks/exhaustive-deps` risks stale closures and recommends restructuring the Effect rather than “tricking” the dependency list: [exhaustive-deps](https://react.dev/reference/eslint-plugin-react-hooks/lints/exhaustive-deps) and [Removing Effect Dependencies](https://react.dev/learn/removing-effect-dependencies).
- React describes Effects as synchronization with external systems and recommends keeping event-specific work in event handlers: [You Might Not Need an Effect](https://react.dev/learn/you-might-not-need-an-effect).
- Native form submission performs interactive constraint validation; direct/programmatic submission paths can bypass it: [MDN constraint validation](https://developer.mozilla.org/en-US/docs/Web/HTML/Guides/Constraint_validation).
- WAI guidance says every interactive element must be keyboard-operable, while a table is normally static and actions inside it should remain separate focusable widgets: [Keyboard Interface](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/) and [Table Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/table/).
- MUI Dialog supplies modal semantics and inherits Modal behavior; prefer it over rebuilding dialog focus and dismissal behavior: [MUI Dialog](https://mui.com/material-ui/react-dialog/).
- Tailwind v4 handles imports and vendor prefixing itself, so `autoprefixer` is unnecessary in this PostCSS setup: [Tailwind v4 upgrade guide](https://tailwindcss.com/docs/upgrade-guide#using-postcss).
- Current `dompurify` and `uuid` packages ship TypeScript declarations; the installed packages also expose their own `.d.ts` entry points. Separate `@types/dompurify` and `@types/uuid` packages are redundant.

## Current-state audit

| Original item | Current status | Evidence and updated decision |
| --- | --- | --- |
| Auth/profile form submission | Partly resolved | `Login.tsx` and `Register.tsx` use `form.onSubmit` with submit buttons. `Profile.tsx:287-294` still intercepts the submit button click. Limit the fix to Profile and add a regression for invalid email. |
| Image sidebar keyboard access | Still current | `ImageSidebar.tsx:44-69` uses a clickable `Box` thumbnail and `ImageSidebar.tsx:91-108` uses a clickable `Box` close control. Replace both with native/MUI buttons and use Dialog semantics. |
| File preview zoom | Partly resolved | Compact mode has manual Enter/Space support and tests. Full mode still attaches `onClick` to the image at `FileUpload.tsx:401-408`. Use one native zoom trigger and one dialog behavior across both modes; do not duplicate manual keyboard logic. |
| Interactive table/card rows | Original diagnosis is stale | `DataTable.onRowClick` is not passed by its only production caller, so delete that unused generic API and its clickable default-card/table behavior. `VocabularyLedger.tsx:233-256` intentionally supports click-anywhere editing; preserve it as a pointer convenience while keeping the explicit Edit button as the equivalent keyboard and screen-reader action. |
| Hook dependency suppressions | Still current | Suppressions remain in `Profile.tsx:68-72` and `useChat.ts:274-279`. Both should be removed with behavior-focused tests. |

## Additional findings

### High-value additions to the implementation scope

1. **Vocabulary ledger semantics:** preserve article-level click-anywhere editing as an intentional pointer shortcut. Keep the labeled Edit button as the semantic keyboard/screen-reader action, and ensure Boost/Edit activation does not bubble into an additional row edit.
2. **Chat polling lifecycle:** `fetchHistory` depends on `isLoading`; the polling, BroadcastChannel, and initial-load Effects therefore inherit callback churn. Make history fetching stable without suppressing dependencies and prove that polling, focus/visibility refresh, optimistic reconciliation, and cleanup still work.
3. **Specialize the analysis table:** `DataTable.tsx` is a 300-line generic with one production caller, unused row-click behavior, and an unused default mobile branch. Replace it with a focused vocabulary-analysis table/card component instead of extending the generic API.
4. **Use the existing ID utility:** `useChat.ts` and `ResultsDisplay.tsx` import `uuid`, while `utils/id.ts` already wraps native `crypto.randomUUID()` with the project fallback. Use `generateId` consistently and remove `uuid` plus `@types/uuid`.
5. **Remove redundant frontend plumbing:** remove `@types/dompurify`, remove Tailwind v4’s redundant `autoprefixer` plugin/dependency, and remove repeated `DOMPurify.sanitize(parseMarkdown(...))` calls because `parseMarkdown` already returns sanitized HTML.

### Deferred candidates, not acceptance criteria for this task

- `AgentMemoryModal.tsx` is large and duplicates its clear-category controls for compact and desktop layouts. Consolidate responsive markup only when that surface receives focused product work; do not create a component hierarchy solely to reduce file length.
- `ResultsDisplay.tsx`, `AddEditVocabularyModal.tsx`, and `FileUpload.tsx` are large, but line count alone is not a refactor requirement. Extract only coherent behavior that is exercised by focused tests.
- `ContentCard` has one caller and `CustomButton` can likely be shorter, as the Ponytail review records. Defer both until their callers receive focused work; this candidate does not have sufficient visual-style evidence to change widely shared presentation primitives safely.
- React Compiler adoption, a data-fetching library, a router, a form library, and a design-system migration need separate product and architecture decisions.

## Product specification

### Requirements

- `R1` Profile submission has one owner: the form `onSubmit`. Invalid native constraints prevent `updateProfile` calls.
- `R2` Image thumbnails, zoom triggers, close actions, and vocabulary edit actions are discoverable native controls with accessible names and visible focus.
- `R3` Image dialogs close through their labeled close button, Escape, and MUI-supported backdrop behavior, and restore focus to the trigger.
- `R4` Static tables and articles remain static semantics. VocabularyLedger may keep its pointer-only row shortcut because the same edit action is exposed by a named native Edit button; do not add row-level `role="button"`, `tabIndex`, or custom Enter/Space handlers. The complete Boost/Edit action areas, including Tooltip wrappers around disabled controls, must stop propagation so enabled, highest-priority-disabled, and in-flight-disabled states cannot fall through to row editing.
- `R5` No application Effect suppresses `react-hooks/exhaustive-deps`. Profile refresh and chat history synchronization retain their current externally visible behavior.
- `R6` Chat history still loads initially, polls with backoff, refreshes on focus/visibility and BroadcastChannel events, avoids overlapping history fetches, and reconciles optimistic messages without duplication.
- `R7` The analysis vocabulary table keeps selection, select-all, responsive mobile rendering, and the current visible columns while deleting unused generic behavior.
- `R8` Removed direct dependencies have no production import or build-time need, Markdown is sanitized once at its parser boundary, and the pinned lockfile stays synchronized.

### Acceptance criteria and evidence

| ID | Acceptance criterion | Required evidence |
| --- | --- | --- |
| `AC1` | Profile has no submit-button `onClick`; clicking submit or pressing Enter reaches the same handler, and an invalid email never calls `updateProfile`. | `E1` focused Profile tests |
| `AC2` | Every ImageSidebar thumbnail is a named button; its modal uses Dialog semantics and a named close button; keyboard open/close and focus restoration work. | `E2` new ImageSidebar tests plus browser keyboard pass |
| `AC3` | Full and compact FileUpload previews expose a native named zoom control and the same dialog close behavior; no clickable `<img>` or hand-written button role remains. | `E3` focused FileUpload tests plus browser keyboard pass |
| `AC4` | Row background click opens Edit exactly once; each Enter/Space activation of the named Edit button opens Edit once; enabled Boost performs Boost without opening Edit; clicking the highest-priority-disabled or in-flight-disabled Boost action area performs neither Boost nor Edit. | `E4` focused VocabularyView tests for all five states plus pointer/keyboard browser pass |
| `AC5` | The analysis table has no unused row-click API/default branch and preserves desktop/mobile selection behavior. | `E5` focused ResultsDisplay/table tests |
| `AC6` | Both application `exhaustive-deps` suppressions are gone, and lint passes without replacement suppressions or latest-ref escape hatches. | `E6` `rg` audit plus lint |
| `AC7` | Initial chat history, polling/backoff, hidden-document behavior, focus/visibility refresh, BroadcastChannel sync, optimistic reconciliation in both GET/POST completion orders, and unmount cleanup pass without duplicate user or assistant messages. | `E7` focused `useChat` tests |
| `AC8` | `uuid`, `@types/uuid`, `@types/dompurify`, and `autoprefixer` are absent from package manifests/lockfile when no transitive package requires them; Markdown remains sanitized exactly once at the parser boundary. | `E8` import/package audit, focused parser/render tests, build, lockfile and security checks |
| `AC9` | Each slice passes its focused tests; the final integrated branch passes the repository readiness gate and applicable browser checks. | `E9` command logs and browser checklist |

## Implementation plan and write ownership

The slices are separate PRs and execute A, then B, then C. Within a slice, one executable owner owns each bounded worker packet below. Other agents may inspect those paths read-only, but must not make overlapping edits.

### Slice A — native interaction semantics

Depends on: none.

Packet A1 — Profile form write set:

- `frontend/src/components/auth/Profile.tsx`
- `frontend/src/components/auth/Profile.test.tsx`

Packet A2 — Image interaction write set:

- `frontend/src/components/chat/ImageSidebar.tsx`
- `frontend/src/components/chat/ImageSidebar.test.tsx` (new)
- `frontend/src/components/FileUpload.tsx`
- `frontend/src/components/FileUpload.test.tsx`

Packet A3 — Static list/table actions write set:

- `frontend/src/components/vocabulary/VocabularyLedger.tsx`
- `frontend/src/components/VocabularyView.test.tsx`
- `frontend/src/components/ui/DataTable.tsx` (delete after replacement)
- `frontend/src/components/ui/VocabularyAnalysisTable.tsx` (new focused replacement)
- `frontend/src/components/ui/VocabularyAnalysisTable.test.tsx` (new)
- `frontend/src/components/ui/index.ts`
- `frontend/src/components/ResultsDisplay.tsx`
- `frontend/src/components/ResultsDisplay.test.tsx`

Implementation contract:

1. Remove Profile’s submit-button click handler. Keep `type="submit"` and form `onSubmit` as the sole path.
2. Replace ImageSidebar’s clickable Boxes with a thumbnail button/`IconButton` and a labeled close `IconButton`; use MUI `Dialog` for the image overlay.
3. Replace both FileUpload zoom affordances with the same native control pattern. Preserve drag/drop, file selection, compact/full layouts, and image rendering.
4. Preserve VocabularyLedger’s article `onClick`, pointer cursor, and hover treatment as click-anywhere editing for pointer users. Keep the article out of the tab order and accessibility button semantics because the named Edit button owns keyboard/screen-reader activation. Isolate propagation at the complete Boost/Edit action wrapper or with an equivalent article-origin guard; do not rely only on a disabled button handler because MUI disabled ButtonBase controls use `pointer-events: none`. Test row background, keyboard Edit, enabled Boost, highest-priority-disabled Boost area, and in-flight-disabled Boost area as distinct cases.
5. Replace generic DataTable with the focused analysis table. Preserve select-all and row checkbox behavior and responsive rendering; delete `onRowClick`, the generic render API, and unused branches.

Stop conditions:

- Stop if MUI Dialog cannot preserve the current visual overlay without changing image sizing or dismissal behavior; record the delta before proceeding.

Focused validation:

```bash
cd frontend
npm run test:run -- src/components/auth/Profile.test.tsx src/components/chat/ImageSidebar.test.tsx src/components/FileUpload.test.tsx src/components/VocabularyView.test.tsx src/components/ResultsDisplay.test.tsx src/components/ui/VocabularyAnalysisTable.test.tsx
npm run lint
npm run build
```

Browser evidence at desktop and narrow mobile viewport:

- Start the app with `make run-dev`, open `http://localhost:5173`, and sign in with an existing locally configured active test account. If the account or backend dependencies are unavailable, record the gate as blocked.
- Use viewport sizes 1280×800 and 390×844.
- In Analyzer, choose a local image file to expose the full and compact preview controls. In Chat, upload one local image with the paperclip control to expose ImageSidebar. In Profile, enter an invalid email.
- Tab to each thumbnail/preview/edit action; visible focus is present.
- Enter/Space activates buttons without custom key handlers.
- Escape and backdrop click each close both image dialogs, and focus returns to each opener.
- Profile invalid email blocks both click and Enter submission.
- In Vocabulary, clicking non-control row space opens Edit once and keyboard activation of Edit opens it once.
- Enabled Boost changes priority without opening Edit. Clicking a highest-priority-disabled Boost area does nothing. With network throttling holding an update request in flight, clicking the temporarily disabled Boost area also does not Boost again or open Edit.

### Slice B — Effect and chat lifecycle correctness

Depends on: Slice A.

Owner write set:

- `frontend/src/components/auth/Profile.tsx`
- `frontend/src/components/auth/Profile.test.tsx`
- `frontend/src/hooks/useAuth.ts`
- `frontend/src/hooks/useAuth.test.tsx`
- `frontend/src/hooks/useChat.ts`
- `frontend/src/hooks/useChat.test.ts`

Implementation contract:

1. Remove `loading` from `refreshUserData`’s guard/dependencies in `useAuth`; `refreshInProgressRef` remains the refresh-overlap guard. This makes the callback stable across profile-update loading transitions. Include `refreshUserData` in Profile’s Effect dependencies and remove the suppression. Test mount/token re-synchronization and prove a profile update’s loading transition does not trigger an extra refresh. Do not add “run once” ref guards merely to satisfy a call-count assertion.
2. Move pure chat message mapping/merging/max-id helpers to module scope as ordinary functions.
3. Make `fetchHistory` independent of render-only `isLoading` callback churn. Keep `fetchInProgressRef` as the history-fetch overlap guard. Before removing the old send-state gate, add controlled deferred-promise regressions for both orders: GET completes before POST, and POST completes before GET. Each must end with exactly one user and one assistant message for the exchange.
4. Add `fetchHistory` to the initial-load Effect dependency list and remove the suppression. Token/API-client changes should re-synchronize; ordinary loading-state changes must not restart the polling lifecycle.
5. Preserve timer and event-listener cleanup. Do not introduce `useEffectEvent`, a latest-callback ref, or a new polling abstraction unless the focused tests prove the simpler callback structure insufficient.

Stop conditions:

- Stop if removing the send-state gate exposes duplicate/dropped messages; keep the regression, restore the invariant with the smallest explicit guard, and re-review the dependency graph.
- Stop if the polling Effect is recreated when `isLoading` toggles after the refactor.

Focused validation:

```bash
cd frontend
npm run test:run -- src/components/auth/Profile.test.tsx src/hooks/useAuth.test.tsx src/hooks/useChat.test.ts
npm run lint
```

### Slice C — Ponytail cleanup and dependency reduction

Depends on: Slices A and B, because it edits their integration seams and package state.

Packet C1 — Native IDs and Results rendering write set:

- `frontend/src/hooks/useChat.ts`
- `frontend/src/hooks/useChat.test.ts`
- `frontend/src/components/ResultsDisplay.tsx`
- `frontend/src/components/ResultsDisplay.test.tsx`
- `frontend/src/utils/id.ts`
- `frontend/src/utils/id.test.ts`

Packet C2 — Markdown and dependency cleanup write set:

- `frontend/src/components/ui/MarkdownDisplay.tsx`
- `frontend/src/components/ui/MarkdownDisplay.test.tsx`
- `frontend/src/utils/markdownParser.ts`
- `frontend/src/utils/markdownParser.test.ts`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/postcss.config.js`

Implementation contract:

1. In C1, replace all `uuidv4()` calls with the existing `generateId()` boundary. Also remove ResultsDisplay’s redundant `DOMPurify.sanitize(renderedOcrHtml)` wrapper while keeping `parseMarkdown()` as the sanitizer boundary and retaining the ResultsDisplay regression. Keep the packages until C2 so C1 is a source-only, independently testable migration.
2. In C2, remove `uuid`, `@types/uuid`, and `@types/dompurify`; keep `dompurify` itself at the single parser/sanitizer boundary.
3. In C2, pass `parseMarkdown()` output directly from `MarkdownDisplay.tsx` because it is already sanitized. Retain tests proving scripts, unsafe URLs, and forbidden attributes remain removed.
4. In C2, remove `autoprefixer` from PostCSS config and dev dependencies; Tailwind v4 remains the prefixing owner.
5. In C2, regenerate the pinned lockfile, reconcile installed packages, and then verify the lockfile with repository Make targets.

Stop conditions:

- Stop a dependency removal if it remains in the lockfile as a transitive dependency; report it as “not direct” rather than claiming complete removal.

Packet C1 focused validation:

```bash
cd frontend
npm run test:run -- src/hooks/useChat.test.ts src/components/ResultsDisplay.test.tsx src/utils/id.test.ts
npm run lint
```

Packet C2 focused and clean-install validation:

```bash
make frontend-lockfile-sync
make install-frontend
make frontend-lockfile-check
cd frontend
npm run test:run -- src/hooks/useChat.test.ts src/components/ResultsDisplay.test.tsx src/components/ui/MarkdownDisplay.test.tsx src/utils/id.test.ts src/utils/markdownParser.test.ts
npm run lint
npm run build
cd ..
make security-check
```

## Dependency DAG and integration ownership

```text
Slice A: interaction semantics ─> Slice B: Effect lifecycle ─> Slice C1: native IDs ─> Slice C2: dependency cleanup ─> final readiness
```

- Slice A packets A1-A3 may run in parallel because their write sets are disjoint. The lead integrates and validates the packets into Slice A; workers must not merge them themselves.
- Slice B starts from accepted Slice A. Slice C1 starts from accepted Slice B, and C2 starts from accepted C1. Shared seams therefore have one writer at a time.
- The lead owns conflict resolution, final `rg` audits, browser evidence collation, todo disposition, and the final readiness gate.
- During execution, store mutable progress and evidence in Dart comments and PR descriptions. After freeze, change this plan only through a reviewed revision; do not silently rewrite acceptance criteria.

## Ponytail review — over-engineering only

`frontend/src/components/ui/DataTable.tsx:L18-300: yagni: 300-line generic table has one production caller, an unused row-click API, and an unused default mobile branch. Replace it with a focused vocabulary-analysis table and native checkbox actions.`

`frontend/src/utils/id.ts:L7-15 + frontend/package.json:stdlib: the project wraps crypto.randomUUID but two components also carry uuid and @types/uuid. Use generateId everywhere; remove both packages.`

`frontend/src/components/ui/MarkdownDisplay.tsx:L3-17 + frontend/src/components/ResultsDisplay.tsx:L11-131: shrink: parseMarkdown already sanitizes, then both consumers sanitize again. Keep one sanitizer boundary in parseMarkdown.`

`frontend/src/components/ui/ContentCard.tsx:L6-35: yagni: configurable wrapper has one caller, SurfaceCard. Inline the Box into SurfaceCard and delete ContentCard.`

`frontend/postcss.config.js:L1-6 + frontend/package.json:native: Tailwind v4 already handles vendor prefixing. Remove autoprefixer and its configuration.`

`frontend/package.json:delete: @types/dompurify and @types/uuid duplicate declarations shipped by installed dompurify and uuid. Nothing replaces them.`

`frontend/src/components/ui/CustomButton.tsx:L5-135: shrink: native button props are redeclared and variant styles repeat size ternaries. Derive from MUI ButtonProps and a compact style map.`

Estimated `net: -180 lines possible.`

## Final validation and audit gates

After all accepted slices are integrated:

```bash
rg -n "eslint-disable.*react-hooks/exhaustive-deps|uuidv4|from ['\"]uuid['\"]|DOMPurify\.sanitize\(parseMarkdown|onRowClick" frontend/src
rg -n '"(@types/dompurify|@types/uuid|autoprefixer|uuid)"' frontend/package.json frontend/package-lock.json
rg -n "autoprefixer" frontend/postcss.config.js
make check-readiness
make security-check
git diff --check
```

Expected `rg` result: no matches for removed in-scope source patterns. `ContentCard` remains a documented deferred finding. A dependency’s transitive lockfile occurrence is allowed only when `npm explain <package>` identifies the owner and the final report names it; direct manifest entries and obsolete source imports must be absent.

Final audit must verify:

- `R1-R8` trace to `AC1-AC9` and `E1-E9`.
- No worker wrote outside its declared slice ownership.
- Focused tests were run before the broad gate and failures were not hidden by a later unrelated pass.
- Browser claims include actual keyboard checks, not synthetic tests alone.
- No new dependencies or abstractions were introduced to replace deleted ones without reopening the plan.
- The Dart task stays out of `Done` until implementation, checks, publication closeout, and user approval are complete.

## Rollback and todo disposition

- Each slice is independently revertible; there is no schema or persisted-data migration.
- If a browser regression is found, revert only the responsible slice rather than restoring the old generic APIs wholesale.
- Before the final implementation PR is published, move durable decisions into tests/code/PR notes and delete this todo when all accepted slices are consumed. Keep it only if it still tracks explicitly deferred work.

## Freeze candidate identity and budgets

- Candidate: `react-best-practices-followups-s2-r6@869c95d`
- Change budget: three focused PRs; no backend files; no new runtime dependencies; no visual redesign.
- Context budget: each worker packet contains at most eight write paths, two production behavior areas, one focused test command, and only its slice contract plus related acceptance/evidence rows. Split the packet before execution if any limit is exceeded. Do not assign a host-independent token ceiling; use the execution host’s small-context profile and these structural limits.
- Review budget: one independent plan audit before freeze; one independent code review per implementation slice; rerun review when behavior or ownership changes.
- Freeze rule: `READY_TO_FREEZE` requires no open Medium/High plan-audit finding. Any change to `R1-R8`, write ownership, dependency order, or browser evidence reopens the plan.
