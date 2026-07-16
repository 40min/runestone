# Recall State Persistence

Runestone stores per-user recall delivery state and the ordered recall words queue in the application database. The Telegram polling offset remains in `state/offset.txt`; it is a single bot-wide cursor and is not part of the database-backed recall state.

The database migration is `8c3e4a1f2b7d_add_recall_state_tables.py`. This is a clean cutover from the former `state.json` representation: existing file-backed recall users, queues, and cursors are not imported. After deployment, a linked user must send `/start` to create or enable database-backed recall state. The worker fills an empty queue during its normal delivery flow. This branch assumes the revision has not yet been deployed; a database already stamped with an earlier form of the same revision would require a follow-up migration because Alembic will not rerun it.

## Data Model

### `recall_user_states`

This table has one row per Runestone user:

| Column | Meaning |
| --- | --- |
| `user_id` | Primary key and foreign key to `users.id`. The existing user row remains the source of account identity and Telegram username. |
| `telegram_chat_id` | Nullable Telegram chat destination. `/start` updates it; a state without a chat id cannot receive recall messages. |
| `is_enabled` | Recall delivery preference, defaulting to `false`. This is separate from `users.active`: delivery requires both an active account and enabled recall state. |
| `next_word_index` | Zero-based cursor identifying the next position to send from the ordered queue. It defaults to `0` and has a non-negative check constraint. |
| `created_at`, `updated_at` | Recall-state timestamps. |

`user_id` replaces the duplicated `db_user_id` and username key previously stored in `state.json`. Telegram username lookup is normalized and resolved through `users.telegram_username`; recall state does not copy the username.

### `recall_queue_items`

The former embedded `daily_selection` array is normalized into one row per queued vocabulary item:

| Column | Meaning |
| --- | --- |
| `id` | Queue-row primary key. |
| `user_id` | Foreign key to `recall_user_states.user_id`. |
| `vocabulary_id` | Foreign key to `vocabulary.id`. The queue does not duplicate `word_phrase`. |
| `position` | Zero-based ordering within the user's queue. It has a non-negative check constraint. |
| `created_at` | Queue-row creation timestamp. |

The table enforces uniqueness for both `(user_id, position)` and `(user_id, vocabulary_id)`. A composite foreign key from `(user_id, vocabulary_id)` to the matching vocabulary row also prevents a queue from referencing another user's word. A user therefore cannot have two words at the same position or the same vocabulary item twice in one queue. Reads join to `vocabulary` for the current phrase, translation, and example phrase, then sort by `position`, with `vocabulary_id` as a deterministic secondary order.

Application DTOs still expose the queue as `daily_selection`, but this is a transport-facing name. Each DTO entry contains the vocabulary id and the joined display fields used by Telegram; there is no serialized words array or copied vocabulary text in the recall tables.

## Queue And Cursor Rules

The queue and `next_word_index` are related but stored separately: queue rows define the stable order, and the cursor points into that order.

- Creating the first selection replaces the queue and resets the cursor to `0`.
- `/bump_words` replaces the complete queue and resets the cursor to `0`.
- Topping up a short queue appends new words after the existing positions and leaves the cursor unchanged.
- A successful Telegram send updates the vocabulary learning timestamp and advances `next_word_index` in one database commit. Cursor advancement wraps against the authoritative queue length, so a completed cycle resumes at position `0`. A failed send rolls back and does not advance it.
- Removing, postponing, or discarding an invalid word compacts the remaining positions to `0..n-1` and adjusts the cursor to keep the same logical next word where possible.
- If a removed word was before the cursor, the cursor decreases by one. If the queue becomes empty, or the adjusted cursor is outside the shortened queue, it resets to `0`.
- `/remove` also marks the vocabulary item as not being learned and lowers its learning priority.
- `/postpone` raises the numeric learning-priority value, removes the item from the current queue, and then attempts to backfill the queue to `WORDS_PER_DAY`. The postponed vocabulary ID is excluded from that refill, so a small candidate pool cannot immediately select the same word again.

The backend vocabulary endpoints temporarily own cross-service orchestration for both hard deletion and explicit soft deletion (`PUT` with `in_learn=false`). They ask `RecallService` to remove and compact any queued reference, ask `VocabularyService` to mutate the owned vocabulary item, then ask `RecallService` to refill a shortened queue when removal changed it. All phases use the same request-scoped session and are committed once; a not-found item, vocabulary-update failure, or refill failure rolls back the complete operation. Deleting vocabulary for a user without recall state remains a normal vocabulary mutation without queue maintenance.

For example, given queue `[A, B, C]` with `next_word_index = 2`, removing `A` produces `[B, C]` with `next_word_index = 1`, so `C` remains the next word. Removing `C` instead produces `[A, B]` with `next_word_index = 0` because the previous cursor is now past the end.

## Transactions And Concurrency

Repository mutations lock the relevant `recall_user_states` row with `SELECT ... FOR UPDATE` before replacing or appending queue rows, removing a word, or changing the cursor. Full queue replacement, queue compaction, cursor adjustment, and related vocabulary changes are performed through the same request- or job-scoped database session.

Scheduled delivery checks its configured delivery window before opening a database session. It then enumerates active recall states in one short-lived session and opens a fresh session for each user delivery. Within that per-user session, delivery acquires the user's recall-state row lock before validating enabled state and chat linkage, loading or creating the selection, resolving invalid items, and choosing the next word. After taking that lock it performs a fresh scalar read of `users.active`, bypassing any identity-mapped `User` object, so deactivation between enumeration and delivery prevents the send. The lock remains held across the injected Telegram send callback. This serializes delivery with other workers and queue mutations for that user, preventing two replicas from sending from the same cursor concurrently, while a failed transaction for one user cannot contaminate later users. Invalid-item cleanup and an exhausted selection's replacement also occur while holding that lock.

After Telegram accepts the message, `RecallService` writes learning metadata without committing, advances and wraps the cursor, and commits both changes together. Send failures and exceptions roll back the open transaction. If invalid-item cleanup exhausts its retries, that cleanup is committed before the job finishes.

Command-facing remove and postpone workflows construct their return state without committing. Their per-update transaction provider commits after the application outcome and outgoing messages have been prepared. A commit failure discards those messages and leaves the update unacknowledged. Scheduled delivery remains different: `deliver_next_word` constructs its return state and owns the final commit or rollback because its row lock deliberately spans the send callback.

Telegram remains an external side effect and cannot participate in the database transaction. There is therefore one unavoidable retry window: Telegram may accept a message and the subsequent database commit may fail, in which case the accepted message can be sent again on a later run. Eliminating that ambiguity would require an external idempotency or delivery protocol.

## Service Ownership

`RecallRepository` owns recall-state reads, row locking, queue persistence, and authoritative cursor adjustment. `RecallService` owns transport-independent recall rules such as enable/disable, selection creation, bump, postpone, queue cleanup/refill, and the complete scheduled-delivery transaction. Command-facing service operations are transaction-neutral: they neither commit successful work nor roll back failures. `VocabularyService` owns vocabulary lookup, learning metadata, priority, and deletion. Each service accesses only its own repository. Vocabulary repository mutations used by these coordinated flows flush without committing. Composition roots construct all repositories over the same scoped `AsyncSession`; the vocabulary endpoints currently use that shared session as a pragmatic transaction boundary until a dedicated application coordinator or unit of work is introduced.

`runestone.recall.providers` exposes the two worker lifecycle modes explicitly. `provide_recall_transaction()` opens a fresh session and one transaction for a Telegram command update, committing or rolling back exactly once at provider exit. `provide_recall_session()` opens and closes a fresh session without owning application commits; scheduled delivery uses it because `deliver_next_word` retains transaction ownership across the callback. These modes are separate contracts rather than flags on one provider.

The main consumers are:

- `TelegramCommandProcessor` for `/start`, `/stop`, `/state`, `/postpone`, `/remove`, and `/bump_words`;
- `TelegramRecallDelivery` for scheduled queue selection and delivery;
- request-scoped `ChatService`, which loads ordered recall words through its injected `RecallService` and supplies the resulting plain list to `AgentsManager` for Teacher context. This separate best-effort read path rolls back only after a database failure because `ChatService` intentionally continues on the same request session; successful reads remain transaction-neutral.

Telegram polling fetches and sorts updates before opening a database session. Structurally irrelevant updates are acknowledged without a session. Each relevant update opens at most one fresh transaction provider, applies the command, and prepares immutable outgoing message data. Only after the provider commits and closes does the processor call Telegram. Successful reads and mutations do not commit or roll back independently.

The file offset acknowledges only the highest contiguous handled prefix. Expected domain failures preserve their existing user-facing response and advance after provider rollback. A database or SQLAlchemy failure found anywhere in the exception cause chain before or during commit rolls back, emits no success message, stops the batch, and retains that update's offset for a later poll with a fresh session. Once commit succeeds, a later session-cleanup failure is logged without suppressing the prepared response or replaying the command. Unknown non-database application failures follow the generic handled-error policy and advance. A Telegram send failure after commit is logged and advances because command application has already succeeded; exactly-once outbound delivery would require a separate idempotency or outbox design.

The worker injects provider functions into the Telegram processors and does not open a batch- or job-level database session. Backend request operations continue to construct repositories and services around their request-scoped `AsyncSession`; recall persistence does not retain a startup-long database session.

## Filesystem State That Remains

`TelegramUpdateOffsetStore` continues to read and write `state/offset.txt`. The value is one polling cursor for the Telegram bot's ordered `getUpdates` stream, not a per-user recall property. The state directory and Hugging Face cache setup therefore remain required even though `state.json`, its backups, and the old combined state manager have been removed.
