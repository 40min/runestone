#!/usr/bin/env python3
"""Destructive-but-restoring local PostgreSQL recall workflow verification.

This utility is deliberately outside the normal pytest suite. It exercises the
real service/repository transaction paths and reads ORM rows directly for every
assertion. Telegram delivery and polling are recorded in memory; no network or
LLM operation is permitted.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy import delete, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from runestone.api.schemas import VocabularyUpdate
from runestone.config import settings
from runestone.constants import VOCABULARY_PRIORITY_HIGH
from runestone.core.exceptions import RecallOperationError, WordNotInSelectionError
from runestone.db.database import SessionLocal, engine
from runestone.db.models import RecallQueueItemDB, RecallUserStateDB, User, Vocabulary
from runestone.db.recall_repository import RecallRepository
from runestone.db.user_repository import UserRepository
from runestone.db.vocabulary_repository import VocabularyRepository
from runestone.schemas.vocabulary_save import PriorityWordSaveItem
from runestone.services.recall_service import RecallService
from runestone.services.recall_types import RecallQueueWord, RecallState
from runestone.services.telegram_command_service import TelegramCommandService
from runestone.services.user_service import UserService
from runestone.services.vocabulary_service import VocabularyService
from runestone.state.telegram_update_offset_store import TelegramUpdateOffsetStore

DEFAULT_USER_ID = 5
DEFAULT_CHAT_ID = 9_005_005
ADVISORY_LOCK_NAMESPACE = 0x5253434C  # "RSCL"
RECOVERY_FILE_TEMPLATE = "/tmp/runestone-recall-integration-user-{user_id}.json"
FIXTURE_TIMESTAMP = datetime(2000, 1, 1, tzinfo=timezone.utc)
COVERAGE_MANIFEST_PATH = Path(__file__).with_name("coverage_manifest.json")
SUPPORTED_CASES = (
    "selection-pools",
    "normal-delivery",
    "delivery-edge",
    "hard-delete",
    "hard-delete-edge",
    "commands",
    "commands-edge",
    "postpone-bump",
    "eligibility",
    "offset-recovery",
    "concurrency",
    "isolation",
    "rollback",
    "lifecycle",
    "vocabulary-context",
    "worker-lifecycle",
    "delivery-races",
)


class NetworkForbidden:
    """Fail loudly if a recall-only scenario unexpectedly reaches an LLM."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"Integration utility attempted to use LLM attribute {name!r}")


class FixtureCandidateVocabularyService(VocabularyService):
    """Use production vocabulary behavior but restrict recall selection to fixtures.

    The adapter changes only the candidate boundary used by this destructive
    harness. Lookups and mutations still execute through the production service
    and repository. Excluding every non-fixture ID prevents a user-5 word from
    being delivered or mutated accidentally.
    """

    def __init__(self, *args, fixture_ids: set[int], **kwargs):
        super().__init__(*args, **kwargs)
        self.fixture_ids = fixture_ids

    async def _selection_exclusions(self, user_id: int, explicit: list[int] | None) -> list[int]:
        result = await self.repo.db.execute(
            select(Vocabulary.id).where(
                Vocabulary.user_id == user_id,
                ~Vocabulary.id.in_(self.fixture_ids),
            )
        )
        return list(dict.fromkeys([*result.scalars().all(), *(explicit or [])]))

    async def select_daily_candidates(
        self,
        user_id: int,
        cooldown_days: int,
        limit: int,
        excluded_word_ids: list[int] | None = None,
    ) -> list[RecallQueueWord]:
        return await super().select_daily_candidates(
            user_id,
            cooldown_days,
            limit,
            await self._selection_exclusions(user_id, excluded_word_ids),
        )

    async def select_alternative_candidates(
        self,
        user_id: int,
        cooldown_days: int,
        limit: int,
        excluded_word_ids: list[int] | None = None,
    ) -> list[RecallQueueWord]:
        return await super().select_alternative_candidates(
            user_id,
            cooldown_days,
            limit,
            await self._selection_exclusions(user_id, excluded_word_ids),
        )


class MemoryOffsetStore:
    """Record Telegram offset behavior without touching the configured file."""

    def __init__(self, initial: int = 0):
        self.offset = initial
        self.writes: list[int] = []

    def get_update_offset(self) -> int:
        return self.offset

    def set_update_offset(self, offset: int) -> None:
        self.offset = offset
        self.writes.append(offset)


class FailingOffsetStore(MemoryOffsetStore):
    def set_update_offset(self, offset: int) -> None:
        raise OSError("synthetic offset write failure")


class FailFirstRecallProxy:
    """Inject one real PostgreSQL error, then delegate to the real service."""

    def __init__(self, db: AsyncSession, delegate: RecallService):
        self.db = db
        self.delegate = delegate
        self.failed = False

    async def get_state_for_telegram_username(self, username: str):
        if not self.failed:
            self.failed = True
            await self.db.execute(text("SELECT 1 / 0"))
        return await self.delegate.get_state_for_telegram_username(username)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)


class RecordingTelegramCommandService(TelegramCommandService):
    """Use production command dispatch while replacing Telegram I/O in memory."""

    def __init__(self, recall_service: Any, offset_store: MemoryOffsetStore):
        # Avoid the production constructor because its bot-token validation is
        # irrelevant when both polling and sending are overridden below.
        self.offset_store = offset_store
        self.recall_service = recall_service
        self.bot_token = "integration-test-no-network"
        self.base_url = "network-is-forbidden"
        self.outbox: list[dict[str, Any]] = []
        self.pending_updates: list[dict[str, Any]] = []

    async def _send_message(self, chat_id: int, message_text: str, parse_mode: str | None = None) -> bool:
        self.outbox.append({"chat_id": chat_id, "text": message_text, "parse_mode": parse_mode})
        return True

    async def _fetch_updates(self) -> tuple[list, int]:
        return list(self.pending_updates), 0


@dataclass(frozen=True)
class OriginalQueueItem:
    id: int
    vocabulary_id: int
    position: int
    created_at: datetime


@dataclass(frozen=True)
class FixtureVocabulary:
    """Stable fixture values that remain usable after session expiration."""

    id: int
    word_phrase: str
    translation: str
    example_phrase: str | None
    in_learn: bool
    priority_learn: int


@dataclass(frozen=True)
class OriginalState:
    user_id: int
    user_active: bool
    telegram_username: str | None
    current_chat_id: str
    user_updated_at: datetime
    state_exists: bool
    telegram_chat_id: int | None
    is_enabled: bool
    next_word_index: int
    state_created_at: datetime | None
    state_updated_at: datetime | None
    queue_items: list[OriginalQueueItem]


@dataclass
class CaseResult:
    name: str
    passed: bool
    detail: str
    before: dict[str, Any]
    after: dict[str, Any]
    traceback: str | None = None


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def stable_fingerprint(rows: list[dict[str, Any]]) -> dict[str, Any]:
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=json_value).encode()
    return {"count": len(rows), "sha256": hashlib.sha256(encoded).hexdigest(), "rows": rows}


async def read_nonfixture_vocabulary_fingerprint(
    db: AsyncSession,
    user_id: int,
    fixture_prefix: str | None = None,
) -> dict[str, Any]:
    db.expire_all()
    stmt = select(Vocabulary).where(Vocabulary.user_id == user_id).order_by(Vocabulary.id.asc())
    if fixture_prefix:
        stmt = stmt.where(~Vocabulary.word_phrase.startswith(fixture_prefix, autoescape=True))
    result = await db.execute(stmt)
    rows = [
        {
            "id": word.id,
            "user_id": word.user_id,
            "word_phrase": word.word_phrase,
            "translation": word.translation,
            "example_phrase": word.example_phrase,
            "extra_info": word.extra_info,
            "in_learn": word.in_learn,
            "priority_learn": word.priority_learn,
            "last_learned": json_value(word.last_learned),
            "learned_times": word.learned_times,
            "created_at": json_value(word.created_at),
            "updated_at": json_value(word.updated_at),
        }
        for word in result.scalars().all()
    ]
    return stable_fingerprint(rows)


async def read_other_recall_fingerprint(db: AsyncSession, user_id: int) -> dict[str, Any]:
    db.expire_all()
    states_result = await db.execute(
        select(RecallUserStateDB).where(RecallUserStateDB.user_id != user_id).order_by(RecallUserStateDB.user_id.asc())
    )
    queue_result = await db.execute(
        select(RecallQueueItemDB)
        .where(RecallQueueItemDB.user_id != user_id)
        .order_by(RecallQueueItemDB.user_id.asc(), RecallQueueItemDB.position.asc())
    )
    rows = [
        {
            "kind": "state",
            "user_id": state.user_id,
            "telegram_chat_id": state.telegram_chat_id,
            "is_enabled": state.is_enabled,
            "next_word_index": state.next_word_index,
            "created_at": json_value(state.created_at),
            "updated_at": json_value(state.updated_at),
        }
        for state in states_result.scalars().all()
    ]
    rows.extend(
        {
            "kind": "queue",
            "id": item.id,
            "user_id": item.user_id,
            "vocabulary_id": item.vocabulary_id,
            "position": item.position,
            "created_at": json_value(item.created_at),
        }
        for item in queue_result.scalars().all()
    )
    return stable_fingerprint(rows)


async def read_database_identity(db: AsyncSession) -> dict[str, Any]:
    result = await db.execute(
        text(
            "SELECT current_database(), current_user, "
            "COALESCE(inet_server_addr()::text, 'local'), inet_server_port()"
        )
    )
    database, current_user, server_address, server_port = result.one()
    url = make_url(settings.database_url)
    return {
        "dialect": url.get_backend_name(),
        "configured_host": url.host,
        "configured_port": url.port,
        "configured_database": url.database,
        "current_database": database,
        "current_user": current_user,
        "server_address": server_address,
        "server_port": server_port,
    }


def read_offset_file_snapshot() -> dict[str, Any]:
    path = Path(settings.telegram_offset_file_path).resolve()
    return {
        "path": str(path),
        "exists": path.exists(),
        "content": path.read_text(encoding="utf-8") if path.exists() else None,
    }


async def read_original_state(db: AsyncSession, user_id: int) -> OriginalState:
    user = await db.get(User, user_id)
    if user is None:
        raise RuntimeError(f"User {user_id} does not exist")

    state = await db.get(RecallUserStateDB, user_id)
    queue_items: list[OriginalQueueItem] = []
    if state is not None:
        result = await db.execute(
            select(RecallQueueItemDB)
            .where(RecallQueueItemDB.user_id == user_id)
            .order_by(RecallQueueItemDB.position.asc())
        )
        queue_items = [
            OriginalQueueItem(
                id=item.id,
                vocabulary_id=item.vocabulary_id,
                position=item.position,
                created_at=item.created_at,
            )
            for item in result.scalars().all()
        ]

    return OriginalState(
        user_id=user_id,
        user_active=bool(user.active),
        telegram_username=user.telegram_username,
        current_chat_id=user.current_chat_id,
        user_updated_at=user.updated_at,
        state_exists=state is not None,
        telegram_chat_id=state.telegram_chat_id if state else None,
        is_enabled=bool(state.is_enabled) if state else False,
        next_word_index=state.next_word_index if state else 0,
        state_created_at=state.created_at if state else None,
        state_updated_at=state.updated_at if state else None,
        queue_items=queue_items,
    )


async def read_evidence(db: AsyncSession, user_id: int, fixture_prefix: str) -> dict[str, Any]:
    """Read state directly from tables, independently of service return values."""
    user = await db.get(User, user_id, populate_existing=True)
    state = await db.get(RecallUserStateDB, user_id, populate_existing=True)
    queue_result = await db.execute(
        select(
            RecallQueueItemDB.position,
            RecallQueueItemDB.vocabulary_id,
            Vocabulary.word_phrase,
            Vocabulary.user_id.label("vocabulary_user_id"),
            Vocabulary.in_learn,
        )
        .join(Vocabulary, Vocabulary.id == RecallQueueItemDB.vocabulary_id)
        .where(RecallQueueItemDB.user_id == user_id)
        .order_by(RecallQueueItemDB.position.asc())
    )
    fixture_result = await db.execute(
        select(
            Vocabulary.id,
            Vocabulary.word_phrase,
            Vocabulary.in_learn,
            Vocabulary.priority_learn,
            Vocabulary.learned_times,
            Vocabulary.last_learned,
            Vocabulary.updated_at,
        )
        .where(
            Vocabulary.user_id == user_id,
            Vocabulary.word_phrase.startswith(fixture_prefix, autoescape=True),
        )
        .order_by(Vocabulary.id.asc())
    )
    queue = [
        {
            "position": position,
            "vocabulary_id": vocabulary_id,
            "word_phrase": phrase,
            "vocabulary_user_id": vocabulary_user_id,
            "in_learn": in_learn,
        }
        for position, vocabulary_id, phrase, vocabulary_user_id, in_learn in queue_result.all()
    ]
    fixtures = [
        {
            "id": row.id,
            "word_phrase": row.word_phrase,
            "in_learn": row.in_learn,
            "priority_learn": row.priority_learn,
            "learned_times": row.learned_times,
            "last_learned": json_value(row.last_learned),
            "updated_at": json_value(row.updated_at),
        }
        for row in fixture_result.all()
    ]
    return {
        "user": {
            "id": user.id if user else None,
            "active": bool(user.active) if user else None,
            "telegram_username": user.telegram_username if user else None,
        },
        "recall_state": (
            {
                "telegram_chat_id": state.telegram_chat_id,
                "is_enabled": bool(state.is_enabled),
                "next_word_index": state.next_word_index,
                "created_at": json_value(state.created_at),
                "updated_at": json_value(state.updated_at),
            }
            if state
            else None
        ),
        "queue": queue,
        "fixtures": fixtures,
    }


def assert_queue_invariants(evidence: dict[str, Any], words_per_day: int) -> None:
    queue = evidence["queue"]
    positions = [item["position"] for item in queue]
    vocabulary_ids = [item["vocabulary_id"] for item in queue]
    require(positions == list(range(len(queue))), f"queue positions are not contiguous: {positions}")
    require(len(vocabulary_ids) == len(set(vocabulary_ids)), "queue contains duplicate vocabulary IDs")
    require(len(queue) <= words_per_day, f"queue exceeds WORDS_PER_DAY={words_per_day}")
    require(
        all(item["vocabulary_user_id"] == evidence["user"]["id"] for item in queue),
        "queue references another user's vocabulary",
    )
    require(all(item["in_learn"] for item in queue), "queue contains inactive vocabulary")
    state = evidence["recall_state"]
    if state is not None:
        cursor = state["next_word_index"]
        require(cursor >= 0, f"cursor is negative: {cursor}")
        require(
            cursor == 0 if not queue else cursor < len(queue), f"cursor {cursor} invalid for queue size {len(queue)}"
        )


def queue_words(fixtures: list[FixtureVocabulary], limit: int) -> list[RecallQueueWord]:
    return [
        RecallQueueWord(
            id=word.id,
            word_phrase=word.word_phrase,
            translation=word.translation,
            example_phrase=word.example_phrase,
        )
        for word in fixtures[:limit]
    ]


async def create_fixtures(db: AsyncSession, user_id: int, prefix: str, count: int) -> list[FixtureVocabulary]:
    fixture_rows = [
        Vocabulary(
            user_id=user_id,
            word_phrase=f"{prefix}{index:02d}",
            translation=f"fixture translation {index:02d}",
            example_phrase=None if index % 3 == 0 else f"fixture example {index:02d}",
            in_learn=index != 3,
            priority_learn=(0, 4, 9)[index % 3],
            last_learned=datetime.now(timezone.utc) if index == 1 else (FIXTURE_TIMESTAMP if index == 2 else None),
            learned_times=1 if index in (1, 2) else 0,
            created_at=FIXTURE_TIMESTAMP,
            updated_at=FIXTURE_TIMESTAMP,
        )
        for index in range(count)
    ]
    db.add_all(fixture_rows)
    await db.commit()
    fixtures = []
    for word in fixture_rows:
        await db.refresh(word)
        fixtures.append(
            FixtureVocabulary(
                id=word.id,
                word_phrase=word.word_phrase,
                translation=word.translation,
                example_phrase=word.example_phrase,
                in_learn=bool(word.in_learn),
                priority_learn=word.priority_learn,
            )
        )
    return fixtures


def build_recall_service(
    db: AsyncSession,
    fixture_ids: set[int],
) -> tuple[RecallService, RecallRepository, FixtureCandidateVocabularyService]:
    recall_repository = RecallRepository(db)
    vocabulary_service = FixtureCandidateVocabularyService(
        VocabularyRepository(db),
        settings,
        cast(BaseChatModel, NetworkForbidden()),
        fixture_ids=fixture_ids,
    )
    recall_service = RecallService(
        recall_repository,
        vocabulary_service,
        UserService(UserRepository(db)),
        settings,
    )
    return recall_service, recall_repository, vocabulary_service


async def prepare_fixture_state(
    db: AsyncSession,
    recall_repository: RecallRepository,
    user_id: int,
    fixtures: list[FixtureVocabulary],
    *,
    enabled: bool = True,
    cursor: int = 0,
) -> RecallState:
    await recall_repository.upsert_for_user(user_id, chat_id=DEFAULT_CHAT_ID, is_enabled=enabled)
    await recall_repository.replace_queue(
        user_id,
        queue_words(fixtures, settings.words_per_day),
        next_word_index=cursor,
    )
    await db.commit()
    state = await recall_repository.get_recall_state(user_id)
    if state is None:
        raise AssertionError("fixture recall state was not created")
    return state


def telegram_update(
    update_id: int,
    username: str,
    command: str,
    *,
    reply_word: str | None = None,
    chat_id: int = DEFAULT_CHAT_ID,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "chat": {"id": chat_id},
        "from": {"username": username},
        "text": command,
        "entities": [{"type": "bot_command", "offset": 0, "length": len(command)}],
    }
    if reply_word is not None:
        message["reply_to_message"] = {"text": f"🇸🇪 {reply_word}\n🇬🇧 fixture"}
    return {"update_id": update_id, "message": message}


class RecallWorkflow:
    def __init__(
        self,
        db: AsyncSession,
        user_id: int,
        fixture_prefix: str,
        fixtures: list[FixtureVocabulary],
        recall_service: RecallService,
        recall_repository: RecallRepository,
        vocabulary_service: VocabularyService,
    ):
        self.db = db
        self.user_id = user_id
        self.fixture_prefix = fixture_prefix
        self.fixtures = fixtures
        self.recall_service = recall_service
        self.recall_repository = recall_repository
        self.vocabulary_service = vocabulary_service
        self.case_before: dict[str, Any] | None = None

    async def evidence(self) -> dict[str, Any]:
        self.db.expire_all()
        evidence = await read_evidence(self.db, self.user_id, self.fixture_prefix)
        assert_queue_invariants(evidence, settings.words_per_day)
        return evidence

    async def reset(self, *, enabled: bool = True, cursor: int = 0) -> RecallState:
        for fixture in self.fixtures:
            await self.db.execute(
                update(Vocabulary)
                .where(Vocabulary.id == fixture.id)
                .values(
                    in_learn=True,
                    priority_learn=VOCABULARY_PRIORITY_HIGH,
                    last_learned=None,
                    learned_times=0,
                    updated_at=FIXTURE_TIMESTAMP,
                )
            )
        await self.db.commit()
        return await prepare_fixture_state(
            self.db,
            self.recall_repository,
            self.user_id,
            self.fixtures,
            enabled=enabled,
            cursor=cursor,
        )

    async def configure_fixture_pool(
        self,
        eligible_ids: set[int],
        *,
        cooldown_ids: set[int] | None = None,
        priorities: dict[int, int] | None = None,
    ) -> None:
        cooldown_ids = cooldown_ids or set()
        priorities = priorities or {}
        for fixture in self.fixtures:
            await self.db.execute(
                update(Vocabulary)
                .where(Vocabulary.id == fixture.id)
                .values(
                    in_learn=fixture.id in eligible_ids or fixture.id in cooldown_ids,
                    priority_learn=priorities.get(fixture.id, VOCABULARY_PRIORITY_HIGH),
                    last_learned=datetime.now(timezone.utc) if fixture.id in cooldown_ids else None,
                    learned_times=0,
                    updated_at=FIXTURE_TIMESTAMP,
                )
            )
        await self.db.commit()

    async def selection_pools(self) -> str:
        await self.reset()
        self.case_before = await self.evidence()

        await self.db.execute(delete(RecallQueueItemDB).where(RecallQueueItemDB.user_id == self.user_id))
        await self.db.execute(delete(RecallUserStateDB).where(RecallUserStateDB.user_id == self.user_id))
        await self.db.commit()
        require(await self.recall_repository.get_recall_state(self.user_id) is None, "read created a missing state")
        require(await self.db.get(RecallUserStateDB, self.user_id) is None, "missing-state read persisted a row")

        await self.recall_repository.upsert_for_user(self.user_id, chat_id=DEFAULT_CHAT_ID, is_enabled=True)
        await self.db.commit()

        short_ids = {self.fixtures[0].id, self.fixtures[1].id}
        await self.configure_fixture_pool(short_ids)
        await self.recall_repository.replace_queue(self.user_id, [], next_word_index=0)
        await self.db.commit()
        short_sends: list[int] = []

        async def record_short(_chat_id: int, word: RecallQueueWord) -> bool:
            short_sends.append(word.id)
            return True

        await self.recall_service.deliver_next_word(self.user_id, record_short)
        short = await self.evidence()
        require({row["vocabulary_id"] for row in short["queue"]} == short_ids, "short pool was not selected exactly")
        require(short_sends == [self.fixtures[0].id], "short pool delivery did not follow deterministic priority")

        await self.configure_fixture_pool(set())
        await self.recall_repository.replace_queue(self.user_id, [], next_word_index=0)
        await self.db.commit()
        empty_sends: list[int] = []

        async def record_empty(_chat_id: int, word: RecallQueueWord) -> bool:
            empty_sends.append(word.id)
            return True

        await self.recall_service.deliver_next_word(self.user_id, record_empty)
        empty = await self.evidence()
        require(not empty["queue"] and empty["recall_state"]["next_word_index"] == 0, "empty pool made a queue")
        require(not empty_sends, "empty pool emitted a message")

        eligible = {self.fixtures[2].id, self.fixtures[3].id, self.fixtures[5].id}
        cooldown = {self.fixtures[4].id}
        await self.configure_fixture_pool(
            eligible,
            cooldown_ids=cooldown,
            priorities={self.fixtures[2].id: 0, self.fixtures[3].id: 4, self.fixtures[5].id: 9},
        )
        await self.db.execute(
            update(Vocabulary)
            .where(Vocabulary.id == self.fixtures[3].id)
            .values(last_learned=FIXTURE_TIMESTAMP, learned_times=1, updated_at=FIXTURE_TIMESTAMP)
        )
        await self.db.commit()
        candidates = await self.vocabulary_service.select_daily_candidates(
            self.user_id,
            settings.cooldown_days,
            settings.words_per_day,
        )
        require(
            [word.id for word in candidates] == [self.fixtures[2].id, self.fixtures[3].id, self.fixtures[5].id],
            "filters/order differ",
        )
        await self.reset()
        return "missing-state read, short/empty pools, cooldown, inactive, and priority filters verified"

    async def normal_delivery(self) -> str:
        await self.reset(cursor=0)
        await self.recall_repository.replace_queue(self.user_id, [], next_word_index=0)
        await self.db.commit()
        before = await self.evidence()
        self.case_before = before
        require(not before["queue"], "normal-delivery setup did not start with an empty queue")
        sent: list[dict[str, Any]] = []

        async def accept(chat_id: int, word: RecallQueueWord) -> bool:
            sent.append({"chat_id": chat_id, "word_id": word.id, "word_phrase": word.word_phrase})
            return True

        for _ in range(settings.words_per_day):
            await self.recall_service.deliver_next_word(self.user_id, accept)
        after = await self.evidence()
        queue_ids = [row["vocabulary_id"] for row in after["queue"]]
        sent_ids = [row["word_id"] for row in sent]
        require(len(queue_ids) == settings.words_per_day, "empty queue was not populated to target size")
        require(sent_ids == queue_ids, f"delivery order {sent_ids} does not match queue order {queue_ids}")
        fixture_rows = {row["id"]: row for row in after["fixtures"]}
        require(all(vocabulary_id in fixture_rows for vocabulary_id in queue_ids), "normal queue selected non-fixtures")
        for vocabulary_id in queue_ids:
            learned = fixture_rows[vocabulary_id]
            require(learned["learned_times"] == 1, f"fixture {vocabulary_id} learning count is not 1")
            require(learned["last_learned"] is not None, f"fixture {vocabulary_id} lacks last_learned")
        require(after["recall_state"]["next_word_index"] == 0, "full delivery cycle did not wrap cursor to zero")
        return f"populated empty queue, delivered {len(sent)} words in order, and wrapped cursor"

    async def delivery_edge(self) -> str:
        await self.reset()
        self.case_before = await self.evidence()

        sends: list[int] = []

        async def record(_chat_id: int, word: RecallQueueWord) -> bool:
            sends.append(word.id)
            return True

        await self.recall_service.disable_for_user(self.user_id, chat_id=DEFAULT_CHAT_ID)
        disabled_before = await self.evidence()
        require(await self.recall_service.deliver_next_word(self.user_id, record) is None, "disabled state delivered")
        require(await self.evidence() == disabled_before and not sends, "disabled delivery mutated state")

        await self.recall_repository.upsert_for_user(self.user_id, chat_id=None, is_enabled=True)
        await self.db.commit()
        null_chat_before = await self.evidence()
        require(await self.recall_service.deliver_next_word(self.user_id, record) is None, "null chat delivered")
        require(await self.evidence() == null_chat_before and not sends, "null-chat delivery mutated state")

        await self.reset()
        invalid_id = self.fixtures[0].id
        await self.db.execute(update(Vocabulary).where(Vocabulary.id == invalid_id).values(in_learn=False))
        await self.db.commit()
        await self.recall_service.deliver_next_word(self.user_id, record)
        repaired = await self.evidence()
        require(invalid_id not in [row["vocabulary_id"] for row in repaired["queue"]], "invalid word remains queued")
        require(sends and sends[-1] != invalid_id, "invalid queued word was sent")

        await self.reset()
        all_ids = {fixture.id for fixture in self.fixtures}
        await self.configure_fixture_pool(set())
        # Direct setup keeps now-inactive rows queued so delivery must clean them.
        await self.recall_repository.replace_queue(
            self.user_id,
            queue_words(self.fixtures, settings.words_per_day),
            next_word_index=0,
        )
        await self.db.commit()
        sends_before = len(sends)
        await self.recall_service.deliver_next_word(self.user_id, record)
        exhausted = await self.evidence()
        require(not exhausted["queue"], "all-invalid queue was not exhausted")
        require(len(sends) == sends_before, "all-invalid queue emitted a message")
        require(all(row["id"] in all_ids for row in exhausted["fixtures"]), "fixture evidence drifted")
        await self.reset()
        return "disabled/null-chat no-op and one/all-invalid queue repair verified"

    async def hard_delete(self) -> str:
        initial_cursor = min(2, settings.words_per_day - 1)
        await self.reset(cursor=initial_cursor)
        target_fixture = self.fixtures[-1]
        hard_delete_queue = [target_fixture, *self.fixtures[: settings.words_per_day - 1]]
        await self.recall_repository.replace_queue(
            self.user_id,
            queue_words(hard_delete_queue, settings.words_per_day),
            next_word_index=initial_cursor,
        )
        await self.db.commit()
        before = await self.evidence()
        self.case_before = before
        target = before["queue"][0]

        # This mirrors the temporary endpoint orchestration: both services join
        # the caller-owned transaction, followed by one commit.
        queue_changed = await self.recall_service.remove_queue_item(self.user_id, target["vocabulary_id"])
        deleted = await self.vocabulary_service.hard_delete_item(target["vocabulary_id"], self.user_id)
        if queue_changed:
            await self.recall_service.refill_queue(self.user_id)
        require(deleted, "fixture hard delete reported no deletion")
        await self.db.commit()

        after = await self.evidence()
        require(
            target["vocabulary_id"] not in [row["vocabulary_id"] for row in after["queue"]],
            "deleted word remains queued",
        )
        require(target["vocabulary_id"] not in [row["id"] for row in after["fixtures"]], "vocabulary row still exists")
        require(len(after["queue"]) == settings.words_per_day, "queue was not refilled to target size")
        expected_cursor = RecallRepository._cursor_after_removal(initial_cursor, 0, settings.words_per_day - 1)
        require(
            after["recall_state"]["next_word_index"] == expected_cursor,
            "cursor did not preserve the logical next word",
        )
        return f"hard-deleted fixture {target['vocabulary_id']} and restored queue size"

    async def hard_delete_edge(self) -> str:
        await self.reset(cursor=min(2, settings.words_per_day - 1))
        self.case_before = await self.evidence()

        not_queued = self.fixtures[-2]
        queue_before = await self.evidence()
        require(await self.vocabulary_service.hard_delete_item(not_queued.id, self.user_id), "not-queued delete failed")
        await self.db.commit()
        queue_after = await self.evidence()
        require(queue_after["queue"] == queue_before["queue"], "not-queued delete changed queue")
        require(queue_after["recall_state"] == queue_before["recall_state"], "not-queued delete changed state")

        no_state_target = self.fixtures[-3]
        await self.db.execute(delete(RecallQueueItemDB).where(RecallQueueItemDB.user_id == self.user_id))
        await self.db.execute(delete(RecallUserStateDB).where(RecallUserStateDB.user_id == self.user_id))
        await self.db.commit()
        require(
            await self.vocabulary_service.hard_delete_item(no_state_target.id, self.user_id), "no-state delete failed"
        )
        await self.db.commit()
        require(await self.db.get(RecallUserStateDB, self.user_id) is None, "deletion created recall state")

        await self.reset(cursor=min(2, settings.words_per_day - 1))
        missing_before = await self.evidence()
        require(
            not await self.vocabulary_service.hard_delete_item(-9_999_999, self.user_id), "missing delete succeeded"
        )
        await self.db.rollback()
        require(await self.evidence() == missing_before, "missing delete changed state")

        foreign_result = await self.db.execute(
            select(Vocabulary.id).where(Vocabulary.user_id != self.user_id).order_by(Vocabulary.id.asc()).limit(1)
        )
        foreign_id = foreign_result.scalar_one_or_none()
        if foreign_id is not None:
            require(
                not await self.vocabulary_service.hard_delete_item(foreign_id, self.user_id),
                "foreign vocabulary delete succeeded",
            )
            await self.db.rollback()

        rollback_target = self.fixtures[0].id
        rollback_before = await self.evidence()
        require(await self.recall_service.remove_queue_item(self.user_id, rollback_target), "rollback remove failed")
        require(await self.vocabulary_service.hard_delete_item(rollback_target, self.user_id), "rollback delete failed")
        # Synthetic refill failure at the endpoint-owned transaction boundary.
        await self.db.rollback()
        require(await self.evidence() == rollback_before, "delete/refill failure did not roll back")

        cursor = min(2, settings.words_per_day - 1)
        for position in sorted({0, cursor, settings.words_per_day - 1}):
            await self.reset(cursor=cursor)
            state_before = await self.evidence()
            target_id = state_before["queue"][position]["vocabulary_id"]
            require(
                await self.recall_service.remove_queue_item(self.user_id, target_id), "position delete remove failed"
            )
            require(await self.vocabulary_service.hard_delete_item(target_id, self.user_id), "position delete failed")
            pending = await self.evidence()
            expected = RecallRepository._cursor_after_removal(cursor, position, settings.words_per_day - 1)
            require(pending["recall_state"]["next_word_index"] == expected, f"cursor wrong for position {position}")
            await self.db.rollback()
            require(await self.evidence() == state_before, f"position {position} rollback drifted")

        await self.reset()
        return "not-queued/no-state/missing/foreign/refill-rollback and cursor-position deletes verified"

    async def commands(self) -> str:
        command_failures: list[str] = []
        state = await self.reset(enabled=False)
        self.case_before = await self.evidence()
        username = (await self.db.get(User, self.user_id)).telegram_username
        require(bool(username), "temporary Telegram username is missing")
        offset_store = MemoryOffsetStore(100)
        telegram = RecordingTelegramCommandService(self.recall_service, offset_store)

        await telegram._process_single_update(telegram_update(101, username, "/start"))
        started = await self.evidence()
        require(started["recall_state"]["is_enabled"], "/start did not enable recall")
        require(started["recall_state"]["telegram_chat_id"] == DEFAULT_CHAT_ID, "/start did not persist chat ID")

        started_queue = [row["vocabulary_id"] for row in started["queue"]]
        started_cursor = started["recall_state"]["next_word_index"]
        outbox_before_repeat = len(telegram.outbox)
        await telegram._process_single_update(telegram_update(109, username, "/start"))
        repeated_start = await self.evidence()
        require(repeated_start["recall_state"]["is_enabled"], "repeated /start disabled recall")
        require(
            [row["vocabulary_id"] for row in repeated_start["queue"]] == started_queue,
            "repeated /start replaced the queue",
        )
        require(
            repeated_start["recall_state"]["next_word_index"] == started_cursor,
            "repeated /start changed the cursor",
        )
        require(len(telegram.outbox) == outbox_before_repeat + 1, "repeated /start emitted no response")
        if "already" not in telegram.outbox[-1]["text"].lower():
            command_failures.append("C02 repeated /start did not preserve an already-enabled response")

        outbox_size = len(telegram.outbox)
        await telegram._process_single_update(telegram_update(102, username, "/state"))
        require(len(telegram.outbox) == outbox_size + 1, "/state did not emit a response")
        require("Current State" in telegram.outbox[-1]["text"], "/state response is malformed")

        for command in ("/postpone", "/remove"):
            before_missing_reply = await self.evidence()
            outbox_size = len(telegram.outbox)
            await telegram._process_single_update(telegram_update(110, username, command))
            after_missing_reply = await self.evidence()
            require(after_missing_reply == before_missing_reply, f"{command} without a reply changed database state")
            require(len(telegram.outbox) == outbox_size + 1, f"{command} without a reply gave no guidance")

        state = await self.recall_repository.get_recall_state(self.user_id) or state
        postpone_word = state.daily_selection[0]
        queue_ids = {word.id for word in state.daily_selection}
        # Make the postponed word the only eligible refill candidate. Correct
        # behavior must explicitly exclude it and accept a temporarily short
        # queue; otherwise the command immediately re-adds the same word.
        await self.db.execute(
            update(Vocabulary)
            .where(
                Vocabulary.user_id == self.user_id,
                Vocabulary.word_phrase.startswith(self.fixture_prefix, autoescape=True),
                ~Vocabulary.id.in_(queue_ids),
            )
            .values(last_learned=datetime.now(timezone.utc))
        )
        await self.db.commit()
        await telegram._process_single_update(
            telegram_update(103, username, "/postpone", reply_word=postpone_word.word_phrase)
        )
        require(
            "postponed" in telegram.outbox[-1]["text"].lower(),
            f"/postpone command failed: {telegram.outbox[-1]['text']}",
        )
        postponed = await self.evidence()
        postponed_readded = postpone_word.id in [row["vocabulary_id"] for row in postponed["queue"]]
        postponed_vocab = next(row for row in postponed["fixtures"] if row["id"] == postpone_word.id)
        require(postponed_vocab["priority_learn"] == VOCABULARY_PRIORITY_HIGH + 1, "/postpone did not lower urgency")

        await self.db.execute(
            update(Vocabulary)
            .where(
                Vocabulary.user_id == self.user_id,
                Vocabulary.word_phrase.startswith(self.fixture_prefix, autoescape=True),
            )
            .values(last_learned=None, updated_at=FIXTURE_TIMESTAMP)
        )
        await self.db.commit()

        old_queue = [row["vocabulary_id"] for row in postponed["queue"]]
        await telegram._process_single_update(telegram_update(104, username, "/bump_words"))
        bumped = await self.evidence()
        require([row["vocabulary_id"] for row in bumped["queue"]] != old_queue, "/bump_words did not replace queue")
        require(bumped["recall_state"]["next_word_index"] == 0, "/bump_words did not reset cursor")

        state = await self.recall_repository.get_recall_state(self.user_id)
        require(state is not None and state.daily_selection, "queue missing before /remove")
        fixture_ids = {fixture.id for fixture in self.fixtures}
        remove_word = next((word for word in state.daily_selection if word.id in fixture_ids), None)
        require(remove_word is not None, "bumped queue contains no fixture word safe to remove")
        await telegram._process_single_update(
            telegram_update(105, username, "/remove", reply_word=remove_word.word_phrase)
        )
        removed = await self.evidence()
        removed_vocab = next(row for row in removed["fixtures"] if row["id"] == remove_word.id)
        require(not removed_vocab["in_learn"], "/remove did not deactivate vocabulary")
        require(remove_word.id not in [row["vocabulary_id"] for row in removed["queue"]], "/remove left word queued")

        await telegram._process_single_update(telegram_update(106, username, "/stop"))
        stopped = await self.evidence()
        require(not stopped["recall_state"]["is_enabled"], "/stop did not disable recall")

        # These commands are intentionally asserted as unknown-command no-ops:
        # the current production command service has no /help or /status branch.
        before_unknown = await self.evidence()
        outbox_size = len(telegram.outbox)
        await telegram._process_single_update(telegram_update(107, username, "/help"))
        await telegram._process_single_update(telegram_update(108, username, "/status"))
        after_unknown = await self.evidence()
        require(after_unknown == before_unknown, "unknown commands unexpectedly changed database state")
        require(len(telegram.outbox) == outbox_size, "unknown commands unexpectedly emitted messages")

        telegram.pending_updates = [
            telegram_update(120, username, "/state"),
            telegram_update(125, username, "/help"),
        ]
        await telegram.process_updates()
        require(offset_store.offset == 126, f"polling offset should be 126, got {offset_store.offset}")
        require(offset_store.writes[-1:] == [126], f"unexpected offset writes: {offset_store.writes}")
        if postponed_readded:
            command_failures.append("D03 /postpone selected the postponed word as its own immediate refill")
        require(not command_failures, "; ".join(command_failures))
        return "verified 6 supported commands; /help and /status are no-ops; offset advanced to 126"

    async def commands_edge(self) -> str:
        await self.reset(enabled=False)
        self.case_before = await self.evidence()
        username = (await self.db.get(User, self.user_id)).telegram_username
        require(bool(username), "temporary username missing")
        telegram = RecordingTelegramCommandService(self.recall_service, MemoryOffsetStore())

        await telegram._process_single_update(telegram_update(201, f"@{username.upper()}", "/start"))
        normalized = await self.evidence()
        require(normalized["recall_state"]["is_enabled"], "case/@ username variation was not normalized")

        await self.recall_service.disable_for_user(self.user_id, chat_id=DEFAULT_CHAT_ID)
        await self.db.execute(update(User).where(User.id == self.user_id).values(active=False))
        await self.db.commit()
        await telegram._process_single_update(telegram_update(202, username, "/start"))
        inactive = await self.evidence()
        require(not inactive["recall_state"]["is_enabled"], "inactive profile was enabled")
        require("not active" in telegram.outbox[-1]["text"], "inactive profile response is missing")
        await self.db.execute(update(User).where(User.id == self.user_id).values(active=True))
        await self.db.commit()

        missing_outbox = len(telegram.outbox)
        await telegram._process_single_update(telegram_update(203, f"missing_{uuid4().hex}", "/start"))
        require(len(telegram.outbox) == missing_outbox + 1, "missing profile got no response")
        require("couldn't find" in telegram.outbox[-1]["text"], "missing profile response is wrong")

        baseline = await self.evidence()
        malformed_updates = [
            {"update_id": 204},
            {"update_id": 205, "message": {"chat": {"id": DEFAULT_CHAT_ID}, "from": {}, "text": "/state"}},
            {
                "update_id": 206,
                "message": {
                    "chat": {},
                    "from": {"username": username},
                    "text": "/state",
                    "entities": [{"type": "bot_command"}],
                },
            },
            {
                "update_id": 207,
                "message": {
                    "chat": {"id": DEFAULT_CHAT_ID},
                    "from": {"username": username},
                    "text": "plain text",
                    "entities": [],
                },
            },
        ]
        outbox_before = len(telegram.outbox)
        for malformed in malformed_updates:
            await telegram._process_single_update(malformed)
        require(await self.evidence() == baseline, "malformed/non-command update changed database")
        require(len(telegram.outbox) == outbox_before, "malformed/non-command update emitted reply")

        for command in ("/remove", "/postpone"):
            outbox_before = len(telegram.outbox)
            await telegram._process_single_update(
                {
                    **telegram_update(208, username, command),
                    "message": {
                        **telegram_update(208, username, command)["message"],
                        "reply_to_message": {"text": "not a recall word"},
                    },
                }
            )
            require(len(telegram.outbox) == outbox_before + 1, f"unparsable {command} got no response")
            require("Could not find" in telegram.outbox[-1]["text"], f"unparsable {command} response is wrong")

        await telegram._process_single_update(
            telegram_update(209, username, "/remove", reply_word=f"{self.fixture_prefix}unknown")
        )
        require("not found" in telegram.outbox[-1]["text"], "unknown remove response is wrong")

        await self.reset(enabled=True)
        absent_fixture = self.fixtures[settings.words_per_day + 1]
        absent_before = await self.evidence()
        await telegram._process_single_update(
            telegram_update(210, username, "/postpone", reply_word=absent_fixture.word_phrase)
        )
        require("not in today's selection" in telegram.outbox[-1]["text"], "not-in-selection response is wrong")
        require(await self.evidence() == absent_before, "not-in-selection command mutated database")
        return "normalization, authorization, malformed updates/replies, unknown and absent words verified"

    async def postpone_bump(self) -> str:
        failures: list[str] = []
        cursor = min(2, settings.words_per_day - 1)
        await self.reset(cursor=cursor)
        self.case_before = await self.evidence()

        for position in sorted({0, cursor, settings.words_per_day - 1}):
            state = await self.reset(cursor=cursor)
            before_ids = [word.id for word in state.daily_selection]
            target = state.daily_selection[position]
            await self.db.execute(
                update(Vocabulary).where(Vocabulary.id == target.id).values(last_learned=datetime.now(timezone.utc))
            )
            await self.db.commit()
            result = await self.recall_service.postpone_word(state, target.word_phrase)
            after_ids = [word.id for word in result.daily_selection]
            require(target.id not in after_ids, f"postponed position {position} was re-added")
            expected_cursor = RecallRepository._cursor_after_removal(cursor, position, settings.words_per_day - 1)
            require(result.next_word_index == expected_cursor, f"postpone cursor wrong at position {position}")
            if position < cursor:
                require(after_ids[result.next_word_index] == before_ids[cursor], "before-cursor logical next changed")
            elif position > cursor:
                require(after_ids[result.next_word_index] == before_ids[cursor], "after-cursor logical next changed")
            elif len(before_ids) > 1:
                expected_next = before_ids[(cursor + 1) % len(before_ids)]
                require(after_ids[result.next_word_index] == expected_next, "at-cursor logical next changed")

        state = await self.reset(cursor=0)
        only = state.daily_selection[0]
        await self.configure_fixture_pool({only.id})
        await self.recall_repository.replace_queue(self.user_id, [state.daily_selection[0]], next_word_index=0)
        await self.db.commit()
        single_state = await self.recall_repository.get_recall_state(self.user_id)
        require(single_state is not None, "single-item state missing")
        single_result = await self.recall_service.postpone_word(single_state, only.word_phrase)
        if only.id in [word.id for word in single_result.daily_selection]:
            failures.append("D03 postponed single eligible word was immediately re-added")
        require(single_result.next_word_index == 0, "single-item postpone cursor is not zero")

        state = await self.reset(cursor=0)
        target = state.daily_selection[0]
        await self.db.execute(
            update(Vocabulary).where(Vocabulary.id == target.id).values(last_learned=datetime.now(timezone.utc))
        )
        await self.db.commit()
        refilled = await self.recall_service.postpone_word(state, target.word_phrase)
        require(target.id not in [word.id for word in refilled.daily_selection], "alternative refill re-added target")
        require(len(refilled.daily_selection) == settings.words_per_day, "alternative refill did not reach target")

        state = await self.reset(cursor=cursor)
        absent = self.fixtures[settings.words_per_day + 2]
        queue_before = [word.id for word in state.daily_selection]
        removed = await self.recall_service.remove_word_completely(state, absent.word_phrase)
        require([word.id for word in removed.daily_selection] == queue_before, "absent soft remove changed queue")
        absent_row = await self.db.get(Vocabulary, absent.id, populate_existing=True)
        require(absent_row is not None and not absent_row.in_learn, "absent soft remove did not deactivate")

        state = await self.reset()
        old_ids = {word.id for word in state.daily_selection}
        bumped = await self.recall_service.bump_words(state)
        require(old_ids.isdisjoint({word.id for word in bumped.daily_selection}), "full bump reused old IDs")
        require(len(bumped.daily_selection) == settings.words_per_day, "full bump did not fill queue")
        require(bumped.next_word_index == 0, "full bump cursor is not zero")

        state = await self.reset()
        current_ids = {word.id for word in state.daily_selection}
        alternatives = {self.fixtures[settings.words_per_day].id, self.fixtures[settings.words_per_day + 1].id}
        await self.configure_fixture_pool(alternatives, cooldown_ids=current_ids)
        insufficient = await self.recall_service.bump_words(state)
        require(
            {word.id for word in insufficient.daily_selection} == alternatives,
            "insufficient bump did not retain exactly available alternatives",
        )
        require(insufficient.next_word_index == 0, "insufficient bump cursor is not zero")

        state = await self.reset()
        await self.configure_fixture_pool(set(), cooldown_ids={fixture.id for fixture in self.fixtures})
        empty = await self.recall_service.bump_words(state)
        require(not empty.daily_selection and empty.next_word_index == 0, "no-alternative bump did not clear queue")
        await self.reset()
        require(not failures, "; ".join(failures))
        return "postpone cursor positions/no-alternative/refill and bump full/short/empty pools verified"

    async def eligibility(self) -> str:
        await self.reset(enabled=True)
        self.case_before = await self.evidence()
        active_states = await self.recall_service.get_active_recall_states()
        require(
            self.user_id in [state.user_id for state in active_states], "enabled active user is not delivery-eligible"
        )

        await self.recall_service.disable_for_user(self.user_id, chat_id=DEFAULT_CHAT_ID)
        disabled_states = await self.recall_service.get_active_recall_states()
        require(
            self.user_id not in [state.user_id for state in disabled_states], "disabled recall state remains eligible"
        )

        await self.recall_repository.upsert_for_user(self.user_id, chat_id=DEFAULT_CHAT_ID, is_enabled=True)
        await self.db.execute(update(User).where(User.id == self.user_id).values(active=False))
        await self.db.commit()
        inactive_states = await self.recall_service.get_active_recall_states()
        require(self.user_id not in [state.user_id for state in inactive_states], "inactive account remains eligible")

        sent_while_inactive: list[int] = []

        async def record_inactive_send(_chat_id: int, word: RecallQueueWord) -> bool:
            sent_while_inactive.append(word.id)
            return True

        inactive_delivery = await self.recall_service.deliver_next_word(self.user_id, record_inactive_send)
        await self.db.execute(update(User).where(User.id == self.user_id).values(active=True))
        await self.db.commit()
        require(inactive_delivery is None, "direct delivery proceeded after account deactivation")
        require(not sent_while_inactive, f"inactive account received words: {sent_while_inactive}")
        return "active+enabled eligible; disabled and inactive states excluded"

    async def offset_recovery(self) -> str:
        await self.reset(enabled=True)
        self.case_before = await self.evidence()
        username = (await self.db.get(User, self.user_id)).telegram_username
        require(bool(username), "temporary username missing")

        with tempfile.TemporaryDirectory(prefix="runestone-recall-offset-") as directory:
            offset_path = Path(directory) / "offset.txt"
            store = TelegramUpdateOffsetStore(str(offset_path))
            require(store.get_update_offset() == 0, "missing offset did not default to zero")
            offset_path.write_text("malformed", encoding="utf-8")
            require(store.get_update_offset() == 0, "malformed offset did not default to zero")
            offset_path.write_text("41", encoding="utf-8")
            require(store.get_update_offset() == 41, "valid offset was not read")

        proxy = FailFirstRecallProxy(self.db, self.recall_service)
        batch_store = MemoryOffsetStore(300)
        batch = RecordingTelegramCommandService(proxy, batch_store)
        batch.pending_updates = [
            telegram_update(301, username, "/state"),
            telegram_update(302, username, "/state"),
        ]
        await batch.process_updates()
        transaction_usable = True
        try:
            await self.db.execute(text("SELECT 1"))
        except Exception:
            transaction_usable = False
        await self.db.rollback()
        later_processed = any("Current State" in message["text"] for message in batch.outbox)

        await self.reset(enabled=True)
        failing_store = FailingOffsetStore(400)
        failing = RecordingTelegramCommandService(self.recall_service, failing_store)
        failing.pending_updates = [telegram_update(401, username, "/stop")]
        await failing.process_updates()
        stopped = await self.evidence()
        require(not stopped["recall_state"]["is_enabled"], "command did not commit before offset write failure")
        require(failing_store.offset == 400, "failing offset store changed its cursor")

        require(transaction_usable, "real PostgreSQL failure left the shared command session aborted")
        require(later_processed, "later update in failed PostgreSQL batch was silently discarded")
        require(batch_store.offset == 303, "successful recovered batch did not advance offset")
        return "file offset defaults, aborted-batch recovery, and offset-write failure verified"

    async def concurrency(self) -> str:
        await self.reset(cursor=0)
        self.case_before = await self.evidence()
        fixture_ids = {fixture.id for fixture in self.fixtures}
        sent: list[int] = []
        sent_lock = asyncio.Lock()

        async def deliver_once(db: AsyncSession) -> None:
            service, _, _ = build_recall_service(db, fixture_ids)

            async def record(_chat_id: int, word: RecallQueueWord) -> bool:
                async with sent_lock:
                    sent.append(word.id)
                await asyncio.sleep(0.05)
                return True

            await service.deliver_next_word(self.user_id, record)

        await self.db.rollback()
        async with SessionLocal() as first_db, SessionLocal() as second_db:
            await asyncio.wait_for(
                asyncio.gather(deliver_once(first_db), deliver_once(second_db)),
                timeout=10,
            )
        require(len(sent) == 2 and len(set(sent)) == 2, f"concurrent delivery duplicated cursor item: {sent}")

        race_failures: list[str] = []
        await self.reset(enabled=True)
        await self.db.rollback()
        async with SessionLocal() as delivery_db, SessionLocal() as deactivate_db:
            delivery_service, _, _ = build_recall_service(delivery_db, fixture_ids)
            enumerated = await delivery_service.get_active_recall_states()
            require(self.user_id in [state.user_id for state in enumerated], "race setup did not enumerate user")
            await deactivate_db.execute(update(User).where(User.id == self.user_id).values(active=False))
            await deactivate_db.commit()
            raced_sends: list[int] = []

            async def record_race(_chat_id: int, word: RecallQueueWord) -> bool:
                raced_sends.append(word.id)
                return True

            outcome = await delivery_service.deliver_next_word(self.user_id, record_race)
            if outcome is not None or raced_sends:
                race_failures.append(f"G03 inactive race delivered {raced_sends}")
        await self.db.execute(update(User).where(User.id == self.user_id).values(active=True))
        await self.db.commit()

        username = (await self.db.get(User, self.user_id, populate_existing=True)).telegram_username
        require(bool(username), "concurrent start username missing")

        async def enable_once(db: AsyncSession) -> None:
            service, _, _ = build_recall_service(db, fixture_ids)
            await service.enable_for_username(username, DEFAULT_CHAT_ID)

        await self.db.rollback()
        async with SessionLocal() as first_db, SessionLocal() as second_db:
            await asyncio.wait_for(
                asyncio.gather(enable_once(first_db), enable_once(second_db)),
                timeout=10,
            )
        state_count_result = await self.db.execute(
            select(RecallUserStateDB).where(RecallUserStateDB.user_id == self.user_id)
        )
        require(len(state_count_result.scalars().all()) == 1, "concurrent start created duplicate states")

        await self.reset(cursor=0)
        delete_target = self.fixtures[-4]
        await self.recall_repository.replace_queue(
            self.user_id,
            queue_words([delete_target, *self.fixtures[: settings.words_per_day - 1]], settings.words_per_day),
            next_word_index=0,
        )
        await self.db.commit()
        await self.db.rollback()

        async def delete_and_refill(db: AsyncSession) -> None:
            service, _, vocabulary = build_recall_service(db, fixture_ids)
            require(await service.remove_queue_item(self.user_id, delete_target.id), "concurrent delete missed queue")
            require(await vocabulary.hard_delete_item(delete_target.id, self.user_id), "concurrent hard delete failed")
            await asyncio.sleep(0.05)
            await service.refill_queue(self.user_id)
            await db.commit()

        async def refill_only(db: AsyncSession) -> None:
            await asyncio.sleep(0.01)
            service, _, _ = build_recall_service(db, fixture_ids)
            await service.refill_queue(self.user_id)
            await db.commit()

        async with SessionLocal() as delete_db, SessionLocal() as refill_db:
            await asyncio.wait_for(
                asyncio.gather(delete_and_refill(delete_db), refill_only(refill_db)),
                timeout=10,
            )
        final = await self.evidence()
        require(delete_target.id not in [row["vocabulary_id"] for row in final["queue"]], "deleted ID reappeared")
        require(not race_failures, "; ".join(race_failures))
        return "two deliveries, deactivation race, concurrent start, and delete/refill locking verified"

    async def isolation(self) -> str:
        state = await self.reset(cursor=0)
        self.case_before = await self.evidence()
        expected_words = [word.word_phrase.strip() for word in state.daily_selection]
        loaded_words = await self.recall_service.load_current_recall_words(self.user_id)
        require(loaded_words == expected_words, "Teacher recall words do not match persisted order")

        foreign_result = await self.db.execute(
            select(Vocabulary).where(Vocabulary.user_id != self.user_id).order_by(Vocabulary.id.asc()).limit(1)
        )
        foreign = foreign_result.scalars().first()
        require(foreign is not None, "cross-user isolation requires at least one existing foreign vocabulary row")

        foreign_before = {
            "id": foreign.id,
            "user_id": foreign.user_id,
            "in_learn": foreign.in_learn,
            "priority_learn": foreign.priority_learn,
            "last_learned": json_value(foreign.last_learned),
            "learned_times": foreign.learned_times,
            "updated_at": json_value(foreign.updated_at),
        }
        foreign_id = foreign.id
        require(
            await self.vocabulary_service.get_learnable_item(foreign_id, self.user_id) is None,
            "foreign vocabulary was readable as owned",
        )
        require(
            not await self.vocabulary_service.hard_delete_item(foreign_id, self.user_id),
            "foreign vocabulary was deleted",
        )
        require(not await self.recall_service.remove_queue_item(self.user_id, foreign_id), "foreign ID removed queue")
        await self.db.rollback()
        refreshed = await self.db.get(Vocabulary, foreign_id, populate_existing=True)
        require(refreshed is not None, "foreign vocabulary disappeared")
        foreign_after = {
            "id": refreshed.id,
            "user_id": refreshed.user_id,
            "in_learn": refreshed.in_learn,
            "priority_learn": refreshed.priority_learn,
            "last_learned": json_value(refreshed.last_learned),
            "learned_times": refreshed.learned_times,
            "updated_at": json_value(refreshed.updated_at),
        }
        require(foreign_after == foreign_before, "foreign vocabulary fields changed")
        return "Teacher ordering and ownership-protected cross-user operations verified"

    async def lifecycle(self) -> str:
        """Exercise lifecycle transitions that retain one deployed recall aggregate."""
        cursor = min(2, settings.words_per_day - 1)
        await self.reset(enabled=False, cursor=cursor)
        self.case_before = await self.evidence()
        user = await self.db.get(User, self.user_id, populate_existing=True)
        require(user is not None and user.telegram_username, "temporary username missing")
        username = user.telegram_username
        telegram = RecordingTelegramCommandService(self.recall_service, MemoryOffsetStore())

        initial = await self.evidence()
        queue_ids = [row["vocabulary_id"] for row in initial["queue"]]
        changed_chat_id = DEFAULT_CHAT_ID + 77
        await telegram._process_single_update(telegram_update(501, username, "/start", chat_id=changed_chat_id))
        started = await self.evidence()
        require(started["recall_state"]["telegram_chat_id"] == changed_chat_id, "/start did not refresh chat ID")
        require([row["vocabulary_id"] for row in started["queue"]] == queue_ids, "/start replaced the queue")
        require(started["recall_state"]["next_word_index"] == cursor, "/start changed the cursor")

        await telegram._process_single_update(telegram_update(502, username, "/stop", chat_id=changed_chat_id))
        stopped = await self.evidence()
        require(not stopped["recall_state"]["is_enabled"], "/stop did not disable state")
        require([row["vocabulary_id"] for row in stopped["queue"]] == queue_ids, "/stop discarded the queue")
        require(stopped["recall_state"]["next_word_index"] == cursor, "/stop changed the cursor")

        await telegram._process_single_update(telegram_update(503, username, "/start", chat_id=changed_chat_id))
        restarted = await self.evidence()
        require(restarted["recall_state"]["is_enabled"], "/start after /stop did not re-enable")
        require([row["vocabulary_id"] for row in restarted["queue"]] == queue_ids, "restart discarded the queue")
        require(restarted["recall_state"]["next_word_index"] == cursor, "restart changed cursor")

        new_username = f"{username}_renamed"
        await self.db.execute(update(User).where(User.id == self.user_id).values(telegram_username=new_username))
        await self.db.commit()
        old_outbox_size = len(telegram.outbox)
        await telegram._process_single_update(telegram_update(504, username, "/state"))
        require(len(telegram.outbox) == old_outbox_size + 1, "old username received no authorization response")
        require("not authorized" in telegram.outbox[-1]["text"], "old username remained authorized")
        await telegram._process_single_update(telegram_update(505, new_username, "/start", chat_id=changed_chat_id))
        renamed = await self.evidence()
        require(renamed["recall_state"]["is_enabled"], "new username could not operate existing state")
        require([row["vocabulary_id"] for row in renamed["queue"]] == queue_ids, "username change replaced queue")

        await self.db.execute(delete(RecallQueueItemDB).where(RecallQueueItemDB.user_id == self.user_id))
        await self.db.execute(delete(RecallUserStateDB).where(RecallUserStateDB.user_id == self.user_id))
        await self.db.commit()
        await telegram._process_single_update(telegram_update(506, new_username, "/stop"))
        absent_stop = await self.evidence()
        require(absent_stop["recall_state"] is not None, "/stop with no row did not create disabled state")
        require(not absent_stop["recall_state"]["is_enabled"], "/stop with no row created enabled state")
        require(not absent_stop["queue"], "/stop with no row created a queue")
        return "chat refresh, stop/start retention, username relink, and absent-state stop verified"

    async def vocabulary_context(self) -> str:
        """Verify deployed vocabulary edits are reflected by queue consumers."""
        cursor = min(1, settings.words_per_day - 1)
        state = await self.reset(enabled=True, cursor=cursor)
        self.case_before = await self.evidence()
        target = state.daily_selection[cursor]
        queue_ids = [word.id for word in state.daily_selection]

        edited_phrase = f"{self.fixture_prefix}edited_[unicode]_å"
        edited_translation = "translation (edited)!"
        edited_example = "Example - edited."
        await self.vocabulary_service.update_vocabulary_item(
            target.id,
            VocabularyUpdate(
                word_phrase=edited_phrase,
                translation=edited_translation,
                example_phrase=edited_example,
            ),
            self.user_id,
        )
        await self.db.commit()
        edited = await self.recall_repository.get_recall_state(self.user_id)
        require(edited is not None, "state disappeared after vocabulary edit")
        require([word.id for word in edited.daily_selection] == queue_ids, "edit changed queue membership")
        require(edited.next_word_index == cursor, "edit changed cursor")
        edited_word = edited.daily_selection[cursor]
        require(
            (edited_word.word_phrase, edited_word.translation, edited_word.example_phrase)
            == (edited_phrase, edited_translation, edited_example),
            "queue consumer did not observe edited vocabulary text",
        )
        await self.vocabulary_service.update_vocabulary_item(
            target.id,
            VocabularyUpdate(priority_learn=VOCABULARY_PRIORITY_HIGH + 3),
            self.user_id,
        )
        await self.db.commit()
        reprioritized = await self.recall_repository.get_recall_state(self.user_id)
        require(reprioritized is not None, "state disappeared after priority edit")
        require([word.id for word in reprioritized.daily_selection] == queue_ids, "priority edit reordered queue")
        require(reprioritized.next_word_index == cursor, "priority edit changed cursor")
        teacher_words = await self.recall_service.load_current_recall_words(self.user_id)
        require(teacher_words[cursor] == edited_phrase, "Teacher context did not observe edited phrase")

        delivered: list[RecallQueueWord] = []

        async def record(_chat_id: int, word: RecallQueueWord) -> bool:
            delivered.append(word)
            return True

        await self.recall_service.deliver_next_word(self.user_id, record)
        require(delivered and delivered[0].id == target.id, "delivery did not use cursor-selected edited item")
        require(delivered[0].word_phrase == edited_phrase, "delivery did not observe edited phrase")

        after_delivery = await self.recall_repository.get_recall_state(self.user_id)
        require(after_delivery is not None, "state disappeared after delivery")
        postpone_target = after_delivery.daily_selection[after_delivery.next_word_index]
        postponed = await self.recall_service.postpone_word(after_delivery, postpone_target.word_phrase)
        teacher_after_postpone = await self.recall_service.load_current_recall_words(self.user_id)
        require(
            teacher_after_postpone == [word.word_phrase for word in postponed.daily_selection],
            "Teacher context drifted after postpone",
        )

        remove_target = postponed.daily_selection[postponed.next_word_index]
        removed = await self.recall_service.remove_word_completely(postponed, remove_target.word_phrase)
        teacher_after_remove = await self.recall_service.load_current_recall_words(self.user_id)
        require(
            teacher_after_remove == [word.word_phrase for word in removed.daily_selection],
            "Teacher context drifted after remove",
        )

        existing_ids = [word.id for word in removed.daily_selection]
        inactive = next(fixture for fixture in self.fixtures if fixture.id not in existing_ids)
        await self.vocabulary_service.update_vocabulary_item(
            inactive.id,
            VocabularyUpdate(in_learn=False),
            self.user_id,
        )
        await self.db.commit()
        queue_before_reactivate = await self.recall_service.load_current_recall_words(self.user_id)
        await self.vocabulary_service.update_vocabulary_item(
            inactive.id,
            VocabularyUpdate(in_learn=True, priority_learn=VOCABULARY_PRIORITY_HIGH),
            self.user_id,
        )
        await self.db.commit()
        require(
            await self.recall_service.load_current_recall_words(self.user_id) == queue_before_reactivate,
            "reactivation rewrote current queue",
        )

        created_phrase = f"{self.fixture_prefix}created_consumer_word"
        queue_before_create = await self.recall_service.load_current_recall_words(self.user_id)
        created_results = await self.vocabulary_service.insert_or_prioritize_words(
            [
                PriorityWordSaveItem(
                    word_phrase=created_phrase,
                    translation="created translation",
                    example_phrase="Created example.",
                    priority_learn=VOCABULARY_PRIORITY_HIGH,
                )
            ],
            self.user_id,
        )
        require(created_results[0]["action"] == "created", "production vocabulary create did not create a row")
        created_id = int(created_results[0]["word_id"])
        cast(FixtureCandidateVocabularyService, self.vocabulary_service).fixture_ids.add(created_id)
        require(
            await self.recall_service.load_current_recall_words(self.user_id) == queue_before_create,
            "creating vocabulary rewrote current queue",
        )
        current = await self.recall_repository.get_recall_state(self.user_id)
        require(current is not None, "state disappeared before created-word bump")
        await self.configure_fixture_pool(set(), cooldown_ids={fixture.id for fixture in self.fixtures})
        created_selection = await self.recall_service.bump_words(current)
        require(
            [word.id for word in created_selection.daily_selection] == [created_id],
            "created eligible word was unavailable to the next bump",
        )
        require(await self.recall_service.remove_queue_item(self.user_id, created_id), "created queue cleanup failed")
        require(
            await self.vocabulary_service.hard_delete_item(created_id, self.user_id), "created fixture cleanup failed"
        )
        await self.db.commit()
        cast(FixtureCandidateVocabularyService, self.vocabulary_service).fixture_ids.discard(created_id)
        await self.reset()
        return (
            "queued edits reach Teacher/delivery; postpone/remove context, create/reactivate selection, "
            "and current-queue stability verified"
        )

    async def worker_lifecycle(self) -> str:
        """Exercise explicit best-effort batch and persisted-offset restart policy."""
        await self.reset(enabled=True)
        self.case_before = await self.evidence()
        user = await self.db.get(User, self.user_id, populate_existing=True)
        require(user is not None and user.telegram_username, "temporary username missing")
        username = user.telegram_username

        # Telegram update IDs define processing order even if an API response is
        # unexpectedly unordered. The offset acknowledges the whole batch after
        # per-update recovery; poison updates are not retried indefinitely.
        store = MemoryOffsetStore(600)
        telegram = RecordingTelegramCommandService(self.recall_service, store)
        telegram.pending_updates = [
            telegram_update(602, username, "/stop"),
            telegram_update(601, username, "/start"),
        ]
        await telegram.process_updates()
        ordered = await self.evidence()
        require(not ordered["recall_state"]["is_enabled"], "updates were not processed by ascending update ID")
        require(store.offset == 603, "unordered batch offset did not use max update ID plus one")

        with tempfile.TemporaryDirectory(prefix="runestone-recall-worker-") as directory:
            path = Path(directory) / "offset.txt"
            persistent_store = TelegramUpdateOffsetStore(str(path))
            first_worker = RecordingTelegramCommandService(self.recall_service, persistent_store)
            first_worker.pending_updates = [telegram_update(610, username, "/start")]
            await first_worker.process_updates()
            before_restart = await self.evidence()
            second_worker = RecordingTelegramCommandService(self.recall_service, TelegramUpdateOffsetStore(str(path)))
            require(second_worker.offset_store.get_update_offset() == 611, "worker restart lost persisted offset")
            require(await self.evidence() == before_restart, "worker restart changed persisted recall state")

        failing_store = FailingOffsetStore(700)
        first_attempt = RecordingTelegramCommandService(self.recall_service, failing_store)
        first_attempt.pending_updates = [telegram_update(701, username, "/stop")]
        await first_attempt.process_updates()
        once = await self.evidence()
        second_attempt = RecordingTelegramCommandService(self.recall_service, MemoryOffsetStore(700))
        second_attempt.pending_updates = [telegram_update(701, username, "/stop")]
        await second_attempt.process_updates()
        twice = await self.evidence()
        require(
            {
                "state": {
                    key: once["recall_state"][key] for key in ("telegram_chat_id", "is_enabled", "next_word_index")
                },
                "queue": once["queue"],
                "fixtures": once["fixtures"],
            }
            == {
                "state": {
                    key: twice["recall_state"][key] for key in ("telegram_chat_id", "is_enabled", "next_word_index")
                },
                "queue": twice["queue"],
                "fixtures": twice["fixtures"],
            },
            "duplicate /stop after offset failure changed consumer-visible state",
        )
        return "update ordering, batch acknowledgment, duplicate stop, and worker restart verified"

    async def delivery_races(self) -> str:
        """Serialize delivery with each recall mutation that shares its aggregate lock."""
        self.case_before = await self.evidence()
        fixture_ids = {fixture.id for fixture in self.fixtures}

        async def run_race(name: str, mutation) -> None:
            await self.reset(enabled=True, cursor=0)
            await self.db.rollback()
            entered_send = asyncio.Event()
            release_send = asyncio.Event()
            sent: list[int] = []

            async with SessionLocal() as delivery_db, SessionLocal() as mutation_db:
                delivery_service, _, _ = build_recall_service(delivery_db, fixture_ids)
                mutation_service, _, mutation_vocabulary = build_recall_service(mutation_db, fixture_ids)

                async def record(_chat_id: int, word: RecallQueueWord) -> bool:
                    sent.append(word.id)
                    entered_send.set()
                    await asyncio.wait_for(release_send.wait(), timeout=5)
                    return True

                delivery_task = asyncio.create_task(delivery_service.deliver_next_word(self.user_id, record))
                await asyncio.wait_for(entered_send.wait(), timeout=5)
                mutation_task = asyncio.create_task(mutation(mutation_service, mutation_vocabulary))
                await asyncio.sleep(0.05)
                require(not mutation_task.done(), f"{name} did not wait for the delivery aggregate lock")
                release_send.set()
                await asyncio.wait_for(asyncio.gather(delivery_task, mutation_task), timeout=10)
            require(len(sent) == 1, f"{name} race emitted {sent}")
            await self.evidence()

        async def stop(service: RecallService, _vocabulary: VocabularyService) -> None:
            await service.disable_for_user(self.user_id, chat_id=DEFAULT_CHAT_ID)

        async def start(service: RecallService, _vocabulary: VocabularyService) -> None:
            user = await service.user_service.get_user_by_id(self.user_id)
            require(user is not None and user.telegram_username, "start race username missing")
            await service.enable_for_username(user.telegram_username, DEFAULT_CHAT_ID + 1)

        async def bump(service: RecallService, _vocabulary: VocabularyService) -> None:
            state = await service.recall_repository.get_recall_state(self.user_id)
            require(state is not None, "bump race state missing")
            await service.bump_words(state)

        async def postpone(service: RecallService, _vocabulary: VocabularyService) -> None:
            state = await service.recall_repository.get_recall_state(self.user_id)
            require(state is not None, "postpone race state missing")
            await service.postpone_word(state, state.daily_selection[0].word_phrase)

        async def remove(service: RecallService, _vocabulary: VocabularyService) -> None:
            state = await service.recall_repository.get_recall_state(self.user_id)
            require(state is not None, "remove race state missing")
            await service.remove_word_completely(state, state.daily_selection[0].word_phrase)

        async def hard_delete(service: RecallService, vocabulary: VocabularyService) -> None:
            state = await service.recall_repository.get_recall_state(self.user_id)
            require(state is not None, "delete race state missing")
            target_id = state.daily_selection[0].id
            changed = await service.remove_queue_item(self.user_id, target_id)
            require(await vocabulary.hard_delete_item(target_id, self.user_id), "delete race target vanished")
            if changed:
                await service.refill_queue(self.user_id)
            await service.recall_repository.commit()

        async def web_soft_delete(service: RecallService, vocabulary: VocabularyService) -> None:
            state = await service.recall_repository.get_recall_state(self.user_id)
            require(state is not None, "soft-delete race state missing")
            target_id = state.daily_selection[0].id
            changed = await service.remove_queue_item(self.user_id, target_id)
            await vocabulary.update_vocabulary_item(
                target_id,
                VocabularyUpdate(in_learn=False),
                self.user_id,
            )
            if changed:
                await service.refill_queue(self.user_id)
            await service.recall_repository.commit()

        for name, mutation in (
            ("stop", stop),
            ("start", start),
            ("bump", bump),
            ("postpone", postpone),
            ("Telegram remove", remove),
            ("web soft delete", web_soft_delete),
            ("web hard delete", hard_delete),
        ):
            await run_race(name, mutation)
        return "delivery serialized with start/stop, bump, postpone, Telegram remove, and web soft/hard delete"

    async def rollback(self) -> str:
        await self.reset(cursor=0)
        before_rejected = await self.evidence()
        self.case_before = before_rejected

        async def reject(_chat_id: int, _word: RecallQueueWord) -> bool:
            return False

        result = await self.recall_service.deliver_next_word(self.user_id, reject)
        require(result is None, "rejected delivery unexpectedly returned a state")
        after_rejected = await self.evidence()
        require(after_rejected == before_rejected, "rejected delivery changed persisted state")

        state = await self.recall_repository.get_recall_state(self.user_id)
        require(state is not None, "state disappeared before missing-membership test")
        before_missing = await self.evidence()
        try:
            await self.recall_service.postpone_word(state, f"{self.fixture_prefix}not-in-queue")
        except WordNotInSelectionError:
            pass
        else:
            raise AssertionError("postponing a missing word did not raise WordNotInSelectionError")
        after_missing = await self.evidence()
        require(after_missing == before_missing, "missing-word postpone changed persisted state")

        before_exception = await self.evidence()

        async def explode(_chat_id: int, _word: RecallQueueWord) -> bool:
            raise RuntimeError("synthetic transport failure")

        try:
            await self.recall_service.deliver_next_word(self.user_id, explode)
        except RecallOperationError:
            pass
        else:
            raise AssertionError("transport exception did not become RecallOperationError")
        after_exception = await self.evidence()
        require(after_exception == before_exception, "transport exception changed persisted state")

        before_outer_rollback = await self.evidence()
        target_id = before_outer_rollback["queue"][0]["vocabulary_id"]
        changed = await self.recall_service.remove_queue_item(self.user_id, target_id)
        require(changed, "caller-owned rollback setup did not remove its target")
        await self.db.rollback()
        after_outer_rollback = await self.evidence()
        require(after_outer_rollback == before_outer_rollback, "caller-owned queue mutation did not roll back")
        return "rejected send, missing membership, transport exception, and outer mutation all rolled back"


async def restore_original_state(
    db: AsyncSession,
    original: OriginalState,
    fixture_prefix: str,
) -> None:
    """Restore user/recall fields exactly and delete only prefixed fixtures."""
    await db.rollback()
    await db.execute(delete(RecallQueueItemDB).where(RecallQueueItemDB.user_id == original.user_id))

    state = await db.get(RecallUserStateDB, original.user_id)
    if original.state_exists:
        if state is None:
            state = RecallUserStateDB(user_id=original.user_id)
            db.add(state)
        state.telegram_chat_id = original.telegram_chat_id
        state.is_enabled = original.is_enabled
        state.next_word_index = original.next_word_index
        state.created_at = original.state_created_at
        state.updated_at = original.state_updated_at
        await db.flush()
        for item in original.queue_items:
            db.add(
                RecallQueueItemDB(
                    id=item.id,
                    user_id=original.user_id,
                    vocabulary_id=item.vocabulary_id,
                    position=item.position,
                    created_at=item.created_at,
                )
            )
    elif state is not None:
        await db.delete(state)

    await db.execute(
        update(User)
        .where(User.id == original.user_id)
        .values(
            active=original.user_active,
            telegram_username=original.telegram_username,
            current_chat_id=original.current_chat_id,
            updated_at=original.user_updated_at,
        )
    )
    await db.execute(
        delete(Vocabulary).where(
            Vocabulary.user_id == original.user_id,
            Vocabulary.word_phrase.startswith(fixture_prefix, autoescape=True),
        )
    )
    await db.commit()


def write_recovery_file(
    path: Path,
    original: OriginalState,
    fixture_prefix: str,
    database_identity: dict[str, Any],
    nonfixture_fingerprint: dict[str, Any],
    other_recall_fingerprint: dict[str, Any],
    offset_file: dict[str, Any],
) -> None:
    payload = {
        "database_identity": database_identity,
        "original": asdict(original),
        "fixture_prefix": fixture_prefix,
        "nonfixture_vocabulary": nonfixture_fingerprint,
        "other_users_recall": other_recall_fingerprint,
        "offset_file": offset_file,
    }
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=json_value)


def write_private_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=json_value)


def print_results(results: list[CaseResult]) -> None:
    print("\nRecall integration results")
    print("=" * 100)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status:4}  {result.name:20}  {result.detail}")
    print("=" * 100)
    for result in results:
        print(f"\n[{result.name}] BEFORE")
        print(json.dumps(result.before, indent=2, sort_keys=True))
        print(f"[{result.name}] AFTER")
        print(json.dumps(result.after, indent=2, sort_keys=True))


def load_coverage_manifest() -> dict[str, Any]:
    manifest = json.loads(COVERAGE_MANIFEST_PATH.read_text(encoding="utf-8"))
    expected_ids = {
        f"{section}{index:02d}"
        for section, end in {
            "A": 7,
            "B": 9,
            "C": 11,
            "D": 9,
            "E": 6,
            "F": 4,
            "G": 5,
            "H": 3,
            "I": 2,
            "J": 6,
            "K": 5,
            "L": 6,
            "M": 5,
            "N": 5,
        }.items()
        for index in range(1, end + 1)
    }
    scenarios = manifest.get("scenarios", {})
    require(set(scenarios) == expected_ids, "coverage manifest does not contain exactly A01-I02")
    allowed_statuses = {"automated", "grouped", "manual-only", "unsupported"}
    for scenario_id, coverage in scenarios.items():
        require(coverage.get("status") in allowed_statuses, f"invalid coverage status for {scenario_id}")
        case = coverage.get("case")
        if case not in (None, "runner-finally") and not str(case).startswith("pytest:"):
            require(case in SUPPORTED_CASES, f"unknown executable case {case!r} for {scenario_id}")
        require(bool(coverage.get("reason")), f"coverage reason missing for {scenario_id}")
    return manifest


async def run(args: argparse.Namespace) -> int:
    manifest = load_coverage_manifest()
    if args.show_coverage:
        print(json.dumps(manifest, indent=2))
        return 0
    database_url = make_url(settings.database_url)
    if database_url.get_backend_name() != "postgresql":
        raise SystemExit(f"Refusing non-PostgreSQL database: {database_url.render_as_string(hide_password=True)}")
    if not args.apply or args.confirm_user_id != args.user_id:
        raise SystemExit(
            "Refusing to mutate the local database. Pass --apply and "
            f"--confirm-user-id {args.user_id} after reading integration_tests/recall/README.md."
        )
    expected_host = database_url.host or "local"
    if args.confirm_host != expected_host or args.confirm_database != database_url.database:
        raise SystemExit(
            "Database identity confirmation does not match configuration. Pass "
            f"--confirm-host {expected_host!r} --confirm-database {database_url.database!r}."
        )
    if settings.words_per_day <= 0:
        raise SystemExit(f"WORDS_PER_DAY must be positive, got {settings.words_per_day}")

    recovery_file = Path(RECOVERY_FILE_TEMPLATE.format(user_id=args.user_id))
    if recovery_file.exists():
        raise SystemExit(
            f"Recovery file {recovery_file} already exists. A prior run may have been interrupted; "
            "inspect and restore it before another run."
        )

    selected_cases = list(SUPPORTED_CASES) if "all" in args.cases else list(dict.fromkeys(args.cases))
    run_id = uuid4().hex[:12]
    fixture_prefix = f"__recall_it_{run_id}_"
    report_file = Path(args.report_file or f"/tmp/runestone-recall-integration-report-{run_id}.json")
    results: list[CaseResult] = []
    original: OriginalState | None = None
    database_identity: dict[str, Any] | None = None
    initial_nonfixture: dict[str, Any] | None = None
    initial_other_recall: dict[str, Any] | None = None
    initial_offset_file: dict[str, Any] | None = None
    fixture_catalog: list[dict[str, Any]] = []
    restoration_evidence: dict[str, Any] = {}
    lock_acquired = False
    unlock_verified = False
    recovery_written = False
    fatal_error: Exception | None = None

    async with engine.connect() as lock_connection:
        try:
            lock_result = await lock_connection.execute(
                text("SELECT pg_try_advisory_lock(:namespace, :user_id)"),
                {"namespace": ADVISORY_LOCK_NAMESPACE, "user_id": args.user_id},
            )
            lock_acquired = bool(lock_result.scalar_one())
            if not lock_acquired:
                raise RuntimeError(f"another recall integration run holds the lock for user {args.user_id}")

            async with SessionLocal() as db:
                try:
                    database_identity = await read_database_identity(db)
                    original = await read_original_state(db, args.user_id)
                    initial_nonfixture = await read_nonfixture_vocabulary_fingerprint(db, args.user_id)
                    initial_other_recall = await read_other_recall_fingerprint(db, args.user_id)
                    initial_offset_file = read_offset_file_snapshot()
                    write_recovery_file(
                        recovery_file,
                        original,
                        fixture_prefix,
                        database_identity,
                        initial_nonfixture,
                        initial_other_recall,
                        initial_offset_file,
                    )
                    recovery_written = True

                    temporary_username = f"recall_it_{uuid4().hex[:12]}"
                    await db.execute(
                        update(User)
                        .where(User.id == args.user_id)
                        .values(active=True, telegram_username=temporary_username)
                    )
                    await db.commit()

                    fixture_count = max(16, settings.words_per_day * 4)
                    fixtures = await create_fixtures(db, args.user_id, fixture_prefix, fixture_count)
                    fixture_catalog = [
                        {
                            "id": fixture.id,
                            "word_phrase": fixture.word_phrase,
                            "baseline_eligible": fixture.in_learn and fixture.id != fixtures[1].id,
                            "baseline_priority": fixture.priority_learn,
                            "has_example": fixture.example_phrase is not None,
                        }
                        for fixture in fixtures
                    ]
                    recall_service, recall_repository, vocabulary_service = build_recall_service(
                        db,
                        {fixture.id for fixture in fixtures},
                    )
                    workflow = RecallWorkflow(
                        db,
                        args.user_id,
                        fixture_prefix,
                        fixtures,
                        recall_service,
                        recall_repository,
                        vocabulary_service,
                    )

                    for case_name in selected_cases:
                        workflow.case_before = None
                        initial_evidence = await read_evidence(db, args.user_id, fixture_prefix)
                        try:
                            detail = await getattr(workflow, case_name.replace("-", "_"))()
                            after = await workflow.evidence()
                            before = workflow.case_before or initial_evidence
                            results.append(CaseResult(case_name, True, detail, before, after))
                        except Exception as exc:
                            failure_traceback = traceback.format_exc()
                            await db.rollback()
                            after = await read_evidence(db, args.user_id, fixture_prefix)
                            before = workflow.case_before or initial_evidence
                            results.append(
                                CaseResult(
                                    case_name,
                                    False,
                                    f"{type(exc).__name__}: {exc}",
                                    before,
                                    after,
                                    failure_traceback,
                                )
                            )
                            if args.fail_fast:
                                break
                except Exception as exc:
                    fatal_error = exc
                finally:
                    restore_error: Exception | None = None
                    if original is not None:
                        try:
                            await restore_original_state(db, original, fixture_prefix)
                            restored = await read_original_state(db, args.user_id)
                            final_nonfixture = await read_nonfixture_vocabulary_fingerprint(
                                db,
                                args.user_id,
                                fixture_prefix,
                            )
                            final_other_recall = await read_other_recall_fingerprint(db, args.user_id)
                            final_offset_file = read_offset_file_snapshot()
                            fixture_count_result = await db.execute(
                                select(Vocabulary.id).where(
                                    Vocabulary.user_id == args.user_id,
                                    Vocabulary.word_phrase.startswith(fixture_prefix, autoescape=True),
                                )
                            )
                            remaining_fixture_ids = list(fixture_count_result.scalars().all())
                            restoration_evidence = {
                                "original_state_matches": restored == original,
                                "nonfixture_vocabulary_matches": final_nonfixture == initial_nonfixture,
                                "other_users_recall_matches": final_other_recall == initial_other_recall,
                                "offset_file_matches": final_offset_file == initial_offset_file,
                                "remaining_fixture_ids": remaining_fixture_ids,
                                "restored_state": asdict(restored),
                                "nonfixture_vocabulary": final_nonfixture,
                                "other_users_recall": final_other_recall,
                                "offset_file": final_offset_file,
                            }
                            require(restored == original, "post-cleanup snapshot does not match original state")
                            require(final_nonfixture == initial_nonfixture, "non-fixture vocabulary changed")
                            require(final_other_recall == initial_other_recall, "another user's recall state changed")
                            require(final_offset_file == initial_offset_file, "configured offset file changed")
                            require(not remaining_fixture_ids, "fixture vocabulary remains after cleanup")
                            if recovery_written:
                                recovery_file.unlink(missing_ok=True)
                        except Exception as exc:
                            restore_error = exc
                    if restore_error is not None:
                        fatal_error = restore_error
                        print(f"CRITICAL: restoration failed: {restore_error}", file=sys.stderr)
                        print(f"Recovery snapshot retained at {recovery_file}", file=sys.stderr)
        except Exception as exc:
            fatal_error = exc
        finally:
            if lock_acquired:
                try:
                    unlock_result = await lock_connection.execute(
                        text("SELECT pg_advisory_unlock(:namespace, :user_id)"),
                        {"namespace": ADVISORY_LOCK_NAMESPACE, "user_id": args.user_id},
                    )
                    unlock_verified = bool(unlock_result.scalar_one())
                    if not unlock_verified and fatal_error is None:
                        fatal_error = RuntimeError("PostgreSQL advisory unlock returned false")
                except Exception as exc:
                    if fatal_error is None:
                        fatal_error = exc

    report_payload = {
        "run_id": run_id,
        "database_identity": database_identity,
        "user_id": args.user_id,
        "fixture_prefix": fixture_prefix,
        "fixture_catalog": fixture_catalog,
        "selected_cases": selected_cases,
        "settings": {
            "words_per_day": settings.words_per_day,
            "cooldown_days": settings.cooldown_days,
            "recall_start_hour": settings.recall_start_hour,
            "recall_end_hour": settings.recall_end_hour,
        },
        "initial_snapshot": {
            "user_and_recall": asdict(original) if original else None,
            "nonfixture_vocabulary": initial_nonfixture,
            "other_users_recall": initial_other_recall,
            "offset_file": initial_offset_file,
        },
        "lock": {"acquired": lock_acquired, "unlock_verified": unlock_verified},
        "coverage_manifest": manifest,
        "results": [
            {
                **asdict(result),
                "status": "pass" if result.passed else "fail",
                "scenario_ids": [
                    scenario_id
                    for scenario_id, coverage in manifest["scenarios"].items()
                    if coverage.get("case") == result.name
                ],
            }
            for result in results
        ],
        "restoration": restoration_evidence,
        "fatal_error": f"{type(fatal_error).__name__}: {fatal_error}" if fatal_error else None,
    }
    write_private_json(report_file, report_payload)

    print_results(results)
    print(f"\nMachine-readable report retained at {report_file}")
    if restoration_evidence:
        print(f"Restoration verified for user {args.user_id}; temporary fixtures were removed.")
    if fatal_error is not None:
        print(f"FATAL: {fatal_error}", file=sys.stderr)
        return 1
    return 0 if results and all(result.passed for result in results) else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Allow temporary database mutations")
    parser.add_argument("--user-id", type=int, default=DEFAULT_USER_ID, help="Local Runestone user ID (default: 5)")
    parser.add_argument(
        "--confirm-user-id",
        type=int,
        help="Must exactly match --user-id to acknowledge the selected account",
    )
    parser.add_argument("--confirm-host", help="Must match configured DATABASE_URL host (use 'local' for socket URLs)")
    parser.add_argument("--confirm-database", help="Must match configured DATABASE_URL database name")
    parser.add_argument(
        "--case",
        dest="cases",
        action="append",
        choices=("all", *SUPPORTED_CASES),
        default=[],
        help="Scenario to run; repeat as needed (default: all)",
    )
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed scenario")
    parser.add_argument("--report-file", help="Retained machine-readable JSON report path (default: /tmp)")
    parser.add_argument(
        "--show-coverage", action="store_true", help="Print A01-I02 coverage manifest without DB access"
    )
    args = parser.parse_args()
    if not args.cases:
        args.cases = ["all"]
    return args


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
