# Numeric Vocabulary Priority (0-9)

## Summary
- Replace the boolean vocabulary priority with a numeric scale where `0` is highest priority and `9` is lowest/default.
- Keep the existing field name `priority_learn` across backend and frontend contracts for this change, but change its type from `bool` to constrained `int`.
- Rework daily-word selection to use a single deterministic ordering: `priority_learn ASC`, then `updated_at ASC`, then `id ASC`, with the existing cooldown and exclusion filters still applied.
- Update Telegram and agent-driven word prioritization so they adjust the numeric value instead of flipping a flag.
- Update docs to reflect the new priority model, selection rules, and command behavior.

## Key Changes
- Add an Alembic migration that converts `vocabulary.priority_learn` from boolean to integer, backfills `TRUE -> 5` and `FALSE -> 9`, makes the column `NOT NULL`, sets server/default to `9`, and adds a `0..9` check constraint.
- Implement migration downgrade by mapping `priority_learn < 9` back to `TRUE` and `9` back to `FALSE`.
- Update the SQLAlchemy model, Pydantic schemas, and service/repository code so `priority_learn` is numeric on create, update, and response payloads.
- Reuse the existing vocabulary create/update endpoints rather than adding a new one: `POST /api/vocabulary/item`, `POST /api/vocabulary`, and `PUT /api/vocabulary/{id}` will accept `priority_learn: 0..9`; omitted values default to `9` for normal/manual saves.
- Change vocabulary stats so `words_prioritized_count` counts active words with `priority_learn < 9`.
- Replace the current two-bucket random selection logic with one query that orders all eligible words by priority and then oldest `updated_at`; this same ordering will drive full daily portions, replacements, and bumped selections.
- Change Telegram `/postpone` so it removes the word from today’s selection, persists `priority_learn = min(priority_learn + 1, 9)`, then refills the gap using the new ordering.
- Change `prioritize_words_for_learning` and WordKeeper-backed saves so they apply `priority--` semantics: existing/restored words become `max(priority_learn - 1, 0)`. For brand-new agent-created words, create them at `4` so the tool still behaves like “default 5, then priority--”.
- Update the vocabulary UI to edit priority in the existing add/edit modal using a 0-9 select with clear help text (`0 = highest`, `9 = lowest/default`), and change the table’s Priority column from a checkbox to a read-only numeric display.
- Update developer-facing and user-facing docs that describe vocabulary priority, daily selection, Telegram `/postpone`, and agent word prioritization so they no longer refer to a boolean flag.

## Test Plan
- Migration test/verification: existing prioritized rows end up at `5`, unprioritized rows at `9`, inserts default to `9`, and out-of-range writes fail.
- Repository tests: daily selection respects cooldown/exclusions and returns rows in `priority ASC, updated_at ASC` order.
- Service and Telegram tests: `/postpone` increments toward `9`, agent prioritization decrements toward `0`, and stats count `< 9` as prioritized.
- API/schema tests: create/update/response payloads validate `priority_learn` as `0..9`.
- Frontend tests: modal renders numeric priority controls, save payloads contain integers, and the table/stats render numeric priority correctly.
- Docs check: updated docs consistently describe `0..9`, default `9`, migration backfill (`5`/`9`), and the new selection/tie-break rules.

## Assumptions
- `updated_at` is the intended “update_date” tie-break field, and older `updated_at` should be selected first.
- Keeping the field name `priority_learn` is preferred for this change to avoid an unnecessary API rename.
- Normal user-created vocabulary defaults to `9`; only agent prioritization actively decreases the numeric value.
