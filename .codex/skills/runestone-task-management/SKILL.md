---
name: runestone-task-management
description: Manage Runestone project tasks through the Dart MCP server. Use when working in /Users/40min/www/runestone and the user asks to create, list, inspect, update, comment on, complete, prioritize, assign, relate, or delete Runestone tasks, or when they refer to Runestone project work in Dart.
---

# Runestone Task Management

This is a Runestone-specific wrapper around the global `/Users/40min/.codex/skills/project-task-management` workflow. Use the global skill's Dart CRUD rules, with the defaults below.

## Defaults

- Project name: `Runestone`.
- Repository: `/Users/40min/www/runestone`.
- Default Dart dartboard: `General/runestone`.
- Statuses: `To-do`, `Doing`, `Done`.
- If `General/runestone` is not an available dartboard, call `mcp__dart__get_config` and choose the closest Runestone-related dartboard or ask briefly when the mapping is unclear.

## Workflow

1. Apply the global `project-task-management` workflow.
2. Scope list/search/create operations to the `General/runestone` dartboard by default.
3. For new tasks, include repo context in the description when useful: `Repository: /Users/40min/www/runestone`.
4. Preserve any existing task fields unless the user explicitly asks to change them.
5. Report task title, id, and the Runestone dartboard after creating or changing a task.

## Runestone Conventions

- Prefer concise implementation-oriented titles, for example `Fix async agent manager cancellation`.
- Put code paths, test names, PR links, and acceptance criteria in the description.
- Use comments for progress notes or investigation summaries instead of rewriting the original description.
- When a request comes from current repo work, mention relevant changed files or tests in the task description if they are known.
