---
name: runestone-grooming
description: Use when working in /Users/40min/www/runestone and the user wants to groom, triage, clarify, deduplicate, close, prioritize, or organize Runestone Dart tasks. Applies the generic dev-grooming workflow to the General/runestone Dart board.
---

# Runestone Grooming

## Purpose

Thin Runestone adapter for the global `dev-grooming` workflow.

Use this when the user asks to groom, triage, clean up, review, close, clarify, organize, or continue working through Runestone tasks in Dart.

## Defaults

- Repository: `/Users/40min/www/runestone`
- Dart board: `General/runestone`
- Project name: `Runestone`
- Statuses: `To-do`, `Doing`, `Done`
- Use the Runestone task-management conventions for Dart CRUD.

## Workflow

1. Apply the global `dev-grooming` skill.
2. Supply `General/runestone` as the Dart board/project scope.
3. Include clickable Dart links for every task mention.
4. Before updating task details, show the proposed text and ask for approval.
5. Add a grooming timemark to every approved detail update, for example: `Groomed 2026-04-22 11:44 EEST.`
6. Use shallow code scans in `/Users/40min/www/runestone` when task meaning depends on current implementation.
7. Keep grooming step-by-step; after each update, move to the next likely high-level or subtask candidate.

## Runestone-Specific Notes

- Prefer Makefile target names in acceptance criteria when verification is relevant, especially `make lint-check`, `make backend-test`, `make frontend-test`, and `make check-readiness`.
- For schema changes, mention Alembic and migration/backfill safety.
- For agent, Teacher, Specialist, memory, recall, and vocabulary tasks, do a quick `rg` scan before drafting code-state details.
- Respect existing parent tasks such as `Chat with teacher agent` and `ref: agent's swarm`; groom their subtasks when they are the active focus.
