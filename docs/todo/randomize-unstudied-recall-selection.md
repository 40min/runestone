# Randomize Unstudied Recall Selection

## Problem

The extra unstudied portion of a recall queue is currently selected in ascending vocabulary-ID order. When more eligible unstudied words exist than `WORDS_UNSTUDIED_EXTRA_COUNT`, each refill keeps choosing the same oldest words until they are recalled and their learning metadata changes. This makes bumping or refilling the queue feel repetitive.

## Proposed Change

Select eligible unstudied words in random order before applying the configured limit.

Concretely, change `VocabularyRepository.select_unstudied_words()` to order its existing filtered query by PostgreSQL `random()` instead of `Vocabulary.id.asc()`. Update its docstring and the corresponding `VocabularyService.select_unstudied_candidates()` docstring so they describe randomized selection.

This is an S0, single-owner change. Expected write set:

- `src/runestone/db/vocabulary_repository.py`
- `src/runestone/services/vocabulary_service.py`
- `tests/db/test_vocabulary_repository.py`
- `tests/services/test_services_vocabulary_service.py` only if its wording asserts deterministic behavior

## Behavior to Preserve

- Candidates belong to the requesting user and have `in_learn = true`.
- Candidates are unstudied: `coalesce(learned_times, 0) = 0`.
- The existing cooldown filter, exclusion list, and result limit continue to apply.
- Current queue composition remains unchanged: priority words are selected first, then the configured extra unstudied portion is appended.
- Queue locking, cursor handling, refill capacity, and transaction ownership remain unchanged.
- If the eligible pool is no larger than the limit, all eligible words are returned; only their order may vary.

## Acceptance Criteria

1. With an eligible unstudied pool larger than the requested limit, selection is not biased toward the lowest vocabulary IDs.
2. The repository query applies random ordering before `LIMIT` while retaining all current eligibility and exclusion filters.
3. Existing initial-selection, bump, postpone, removal, and refill flows continue using the same service API and queue-size rules.
4. Repository tests verify eligibility, exclusions, limits, and randomized query ordering without flaky assertions that two calls must return different results.

## Test Strategy

- Update the repository test that currently asserts ascending ID order.
- Assert the generated statement uses PostgreSQL random ordering, or otherwise inspect the query contract deterministically; do not use probabilistic repeated-call assertions.
- Keep data-backed assertions for user ownership, active-learning status, unstudied status, cooldown, exclusions, and limits.
- Run the focused checks:

  ```bash
  uv run pytest tests/db/test_vocabulary_repository.py -k select_unstudied_words -v
  uv run pytest tests/services/test_services_vocabulary_service.py -k select_unstudied_candidates -v
  uv run pytest tests/recall/test_service.py -k "unstudied or refill or bump" -v
  ```

- Before publishing the implementation, run `make check-readiness`.

## Risks and Mitigations

- `ORDER BY random()` sorts the eligible pool and can become expensive for very large per-user vocabularies. The current scope accepts this simple implementation because selection is user-scoped and bounded; measure query latency before introducing sampling or a more complex random-key design.
- Random output must not make tests flaky. Verify the query structure and invariant filters rather than expecting different results from consecutive calls.

## Non-Goals

- Preventing an unstudied word from appearing in consecutive queues across separate transactions.
- Persisting selection history or introducing a no-repeat window.
- Changing priority-word selection, queue sizes, cooldown policy, or learning metadata.
- Adding configuration for deterministic seeds or alternative sampling strategies.

## Completion Evidence

The implementation is complete when the focused tests and repository-wide readiness gate pass, the diff stays within the write set above, and an independent final review confirms that only unstudied-candidate ordering changed.
