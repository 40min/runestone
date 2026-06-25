# Bump Words Exclude And Randomize

## Context

- Task: `guZU7UsKDvZX`
- Task URL: <https://app.dartai.com/t/guZU7UsKDvZX-bug-bump-words-must-change>
- Branch: `fix/bump-words-exclude-and-randomize`

## Agreed Behavior

- Keep normal daily recall selection deterministic.
- Use a bump-only selector for `/bump_words`.
- Exclude the current daily selection on the first bump pass.
- Order bump results by `priority_learn` first, then `random()`.
- If the first pass returns too few words, backfill the remainder with a second bump pass.
- Allow previously bumped words back into the second pass when needed, but exclude words already selected in the first pass so duplicates cannot appear.
- Do not change priority or `last_learned` as part of `/bump_words`.

## Checklist

- [x] Add bump-only repository selector with priority-first randomized ordering.
- [x] Add bump-only service helper and two-pass bump fallback.
- [x] Add repository and service tests for exclusion, fallback, and no-duplicate behavior.
- [x] Run focused backend tests.
- [ ] Run `make check-readiness` before staging or commit.
