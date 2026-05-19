# Documentation Guidelines

## Filename Convention

All files under `docs/` should follow this naming style:

- Use lowercase only
- Use kebab-case words separated by hyphens
- Use descriptive, intent-first names
- Keep the `.md` extension
- Avoid version/date suffixes unless they are necessary for meaning

Examples:

- `structured-intent-architecture.md`
- `agent-swarm-architecture.md`
- `tool-db-di.md`

## Stable Docs

- [`agent-swarm-architecture.md`](agent-swarm-architecture.md): current agent routing, tool ownership, async-post behavior, and memory boundaries
- [`memory-maintainer.md`](memory-maintainer.md): chat-reset background memory cleanup flow and maintainer tool contract

## `docs/todo` Purpose

Use `docs/todo/` for temporary planning documents about upcoming work.

- Files in `docs/todo/` are intentionally temporary
- After implementation, extract lasting decision logs into stable docs
- Delete the temporary `docs/todo/` file once its decisions are captured
