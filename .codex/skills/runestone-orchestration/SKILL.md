---
name: runestone-orchestration
description: Thin Runestone adapter for the global dev-work-item-orchestration lifecycle. Use when working in /Users/40min/www/runestone and the user says "let's do ...", "start ...", "implement ...", "take this through PR", or otherwise wants a Runestone change carried through branch, Dart task management, implementation, checks, commit, and final task completion.
---

# Runestone Orchestration

Use this skill as the Runestone adapter for `/Users/40min/.codex/skills/dev-work-item-orchestration`.

## Sources Of Truth

- Lifecycle sequence and gates: `/Users/40min/.codex/skills/dev-work-item-orchestration/SKILL.md`.
- Dart task CRUD and generic task safety: `/Users/40min/.codex/skills/dev-project-task-management/SKILL.md`.
- Runestone Dart defaults: `/Users/40min/www/runestone/.codex/skills/runestone-task-management/SKILL.md`.
- Repository conventions: `/Users/40min/www/runestone/AGENTS.md`.

Load those files when this skill triggers. Do not copy their rules into this skill.

## Runestone Defaults

- Repository: `/Users/40min/www/runestone`.
- Task wrapper skill: `runestone-task-management`.
- Branch names: use `feat/<slug>` for new functionality and `fix/<slug>` for bug fixes. Do not use the generic `codex/` branch prefix for Runestone work.

## Trigger Coverage

Treat this adapter as the default entrypoint for implementation work in `/Users/40min/www/runestone`, not only for exact phrase matches.

Trigger this skill when the user:

- asks to implement code changes (for example: "implement this", "please implement this plan", "apply this plan", "fix this", "add this endpoint")
- asks to carry work through checks/commit/PR
- asks to continue or finish an in-flight Runestone change that already has code edits

Do not wait for literal phrases like "let's do", "start", or "take this through PR" if the implementation intent is already clear.

If implementation work started without lifecycle tracking, switch into this lifecycle at the next user turn and continue from the correct current step.

## Adapter Map

- For every task operation in the global lifecycle, use `runestone-task-management`.
- For every implementation convention question, use `AGENTS.md` and the surrounding code.
- For checks, inspect the repo's project config or existing scripts and choose the smallest command set that validates the changed surface.

## Temporary Readiness Override

`make check-readiness` is temporarily disabled as a blocking finalisation gate for Runestone work until the current readiness failures are fixed.

- During this temporary period, run scoped checks that cover the changed surface (for example backend target tests, frontend target tests, lint, and frontend build where relevant).
<!-- - Report `make check-readiness` status when it is run, but do not block commit/push solely on its failure during this temporary period.
- Always create or link a dedicated Dart follow-up task for restoring `make check-readiness` as a strict required finalisation gate. -->

## Summary Additions

When the global lifecycle asks for an outcome summary, include Runestone-specific traceability:

- Active task title and id.
- PR/CR link if one was created.
