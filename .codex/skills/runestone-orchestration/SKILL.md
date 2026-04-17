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

## Adapter Map

- For every task operation in the global lifecycle, use `runestone-task-management`.
- For every implementation convention question, use `AGENTS.md` and the surrounding code.
- For checks, inspect the repo's project config or existing scripts and choose the smallest command set that validates the changed surface.

## Summary Additions

When the global lifecycle asks for an outcome summary, include Runestone-specific traceability:

- Active task title and id.
- PR/CR link if one was created.
