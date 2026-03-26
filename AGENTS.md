# Agent Instructions (Runestone)

## `__init__.py` Policy

Keep package `__init__.py` files empty unless there is an explicit, reviewed reason to add code.

## Docstrings And Comments

Write docstrings and comments to explain intent, invariants, and business rules, not to narrate obvious code.

- Add module docstrings for service, agent, and other orchestration-heavy files when they benefit from a one-line responsibility summary.
- Add class docstrings for public services/managers that explain ownership boundaries and what the class coordinates.
- Add method docstrings for public or non-trivial internal methods when behavior, side effects, lifecycle, or return semantics are not obvious.
- At public entry points, describe parameters when the name alone is ambiguous or domain-specific, for example flags, cursors, ids, and tuning values such as playback `speed`.
- Prefer documenting parameters at the first meaningful boundary where another reader would need the explanation; do not repeat the same parameter prose through every downstream helper.
- Prefer concise prose in sentence case. Keep docstrings current with the actual async/background behavior and collaborator names.
- Use inline comments sparingly for non-obvious decisions, phase boundaries, truncation/capping rules, persistence order guarantees, or intentionally surprising behavior.
- Avoid comments that just restate the next line, numbered “step” comments for routine CRUD flow, or stale references to old architecture.
- When useful, explain why an operation happens in a specific order, especially around persistence, background tasks, and history trimming.
