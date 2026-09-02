#!/usr/bin/env python3
"""Create and remove guarded browser fixtures for the recall schedule gate."""

import argparse
import asyncio
import json
import secrets
import stat
import sys
from pathlib import Path
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from runestone.config import settings
from runestone.db.models import RecallUserStateDB, User
from runestone.db.recall_repository import RecallRepository
from runestone.db.user_repository import UserRepository
from runestone.recall.service import RecallService
from runestone.services.auth_service import AuthService
from runestone.services.user_service import UserService
from runestone.services.vocabulary_service import VocabularyService

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
MANIFEST_NAME = "fixture-manifest.json"
CREDENTIALS_NAME = "fixture-credentials.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def require_safe_database_url(database_url: str) -> None:
    url = make_url(database_url)
    require(url.get_backend_name() == "postgresql", "refusing non-PostgreSQL database")
    require(url.host in LOCAL_HOSTS, "refusing non-loopback database host")
    require(
        url.database is not None and url.database.endswith("_test"),
        "refusing database name without _test suffix",
    )


def write_private_json(path: Path, payload: object) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n"
    path.write_bytes(encoded)
    path.chmod(0o600)


def read_private_manifest(path: Path) -> dict[str, Any]:
    require(path.name == MANIFEST_NAME, "cleanup manifest must be fixture-manifest.json")
    mode = stat.S_IMODE(path.stat().st_mode)
    require(mode & 0o077 == 0, "cleanup manifest must not be group/world readable")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), "cleanup manifest is invalid")
    database_url = payload.get("database_url")
    require(isinstance(database_url, str), "cleanup manifest omits database URL")
    require_safe_database_url(database_url)
    return payload


def build_recall_service(session: AsyncSession) -> RecallService:
    """Compose the production recall service around this fixture transaction."""
    return RecallService(
        RecallRepository(session),
        Mock(spec=VocabularyService),
        UserService(UserRepository(session)),
        settings,
    )


async def snapshot_before_create(session: AsyncSession, email: str) -> dict[str, object]:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    require(user is None, "fixture email unexpectedly already exists")
    return {"email": email, "user": None, "recall_state": None}


async def create_fixture_accounts(database_url: str, output_dir: Path) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    run_id = uuid4().hex
    configured_email = f"recall-schedule-configured-{run_id}@example.test"
    chatless_email = f"recall-schedule-chatless-{run_id}@example.test"
    configured_password = secrets.token_urlsafe(32)
    chatless_password = secrets.token_urlsafe(32)
    manifest_path = output_dir / MANIFEST_NAME
    credentials_path = output_dir / CREDENTIALS_NAME
    fixture_records: list[dict[str, object]] = []
    manifest: dict[str, object] = {
        "version": 1,
        "database_url": database_url,
        "run_id": run_id,
        "fixtures": fixture_records,
    }
    write_private_json(manifest_path, manifest)
    try:
        async with session_factory() as session:
            snapshots = [
                await snapshot_before_create(session, configured_email),
                await snapshot_before_create(session, chatless_email),
            ]
            auth_service = AuthService(UserRepository(session), settings)
            configured = await auth_service.register_user(configured_email, configured_password)
            fixture_records.append({**snapshots[0], "user_id": configured.id})
            write_private_json(manifest_path, manifest)
            chatless = await auth_service.register_user(chatless_email, chatless_password)
            fixture_records.append({**snapshots[1], "user_id": chatless.id})
            write_private_json(manifest_path, manifest)
            configured.telegram_username = f"recallconfigured{run_id[:12]}"
            chatless.telegram_username = f"recallchatless{run_id[:12]}"
            configured.active = True
            chatless.active = True
            await session.commit()

            recall_service = build_recall_service(session)
            enabled = await recall_service.enable_for_username(configured.telegram_username, 9_001_001)
            require(enabled.state is not None, "configured fixture was not linked through RecallService")
            await recall_service.disable_for_user(chatless.id)
            await session.commit()
            write_private_json(
                credentials_path,
                {
                    "configured": {"email": configured_email, "password": configured_password},
                    "chatless": {"email": chatless_email, "password": chatless_password},
                },
            )
    except BaseException:
        if manifest["fixtures"]:
            await cleanup_manifest(manifest)
        raise
    finally:
        await engine.dispose()


async def cleanup_manifest(manifest: dict[str, Any]) -> None:
    database_url = manifest["database_url"]
    fixtures = manifest.get("fixtures")
    require(isinstance(fixtures, list) and fixtures, "cleanup manifest contains no fixtures")
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as session:
            for fixture in fixtures:
                require(isinstance(fixture, dict), "cleanup fixture is invalid")
                user_id = fixture.get("user_id")
                email = fixture.get("email")
                require(isinstance(user_id, int) and isinstance(email, str), "cleanup fixture identity is invalid")
                require(email.endswith("@example.test") and "recall-schedule-" in email, "refusing non-fixture user")
                user = (
                    await session.execute(select(User).where(User.id == user_id, User.email == email))
                ).scalar_one_or_none()
                if user is None:
                    continue
                await session.execute(delete(RecallUserStateDB).where(RecallUserStateDB.user_id == user_id))
                await session.delete(user)
            await session.commit()
    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", help="loopback PostgreSQL test database")
    parser.add_argument("--output-dir", type=Path, help="private evidence directory for a new fixture")
    parser.add_argument("--cleanup-manifest", type=Path, help="remove only the fixture recorded in this manifest")
    args = parser.parse_args()
    creating = args.database_url is not None or args.output_dir is not None
    require(
        creating != (args.cleanup_manifest is not None),
        "provide creation arguments or --cleanup-manifest, not both",
    )
    if creating:
        require(
            args.database_url is not None and args.output_dir is not None,
            "--database-url and --output-dir are required together",
        )
    return args


async def main() -> int:
    args = parse_args()
    if args.cleanup_manifest is not None:
        manifest = read_private_manifest(args.cleanup_manifest)
        await cleanup_manifest(manifest)
        print("PASS browser fixture cleanup")
        return 0
    require_safe_database_url(args.database_url)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    output_dir.chmod(0o700)
    await create_fixture_accounts(args.database_url, output_dir)
    print(f"PASS browser fixtures prepared; evidence={output_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL browser fixture: {exc}", file=sys.stderr)
        raise SystemExit(1)
