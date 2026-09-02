#!/usr/bin/env python3
"""Verify isolated container startup evidence for the recall schedule change."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import make_url

from runestone.config import settings

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = Path(__file__).with_name("recall_schedule.compose.yaml")
EVIDENCE_ROOT = Path("/tmp/runestone-recall-schedule-containers")
ZONE_PROBE = (
    "import tzdata; from zoneinfo import TZPATH, ZoneInfo; "
    "assert TZPATH == (); "
    "[ZoneInfo(name) for name in ('UTC', 'Europe/Helsinki', 'America/New_York')]; "
    "print('tzdata-zoneinfo-ok')"
)
SECRET_PATTERN = re.compile(
    r"(?i)(postgresql(?:\+asyncpg)?://[^:\s]+:)([^@\s]+)(@)|"
    r"((?:api[_-]?key|token|password|secret|authorization)\s*[=:]\s*)([^\s,]+)"
)


def require(condition: bool, message: str) -> None:
    """Fail with a concise evidence-contract violation."""
    if not condition:
        raise AssertionError(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", settings.database_url),
        help="local PostgreSQL configuration to safety-check before Docker is used",
    )
    return parser.parse_args()


def require_safe_database_url(database_url: str | None) -> None:
    """Reject a configured database that is not explicitly local PostgreSQL."""
    require(
        database_url is not None,
        "DATABASE_URL or --database-url is required for the local safety check",
    )
    url = make_url(database_url)
    require(url.get_backend_name() == "postgresql", "refusing non-PostgreSQL database configuration")
    require(url.host in LOCAL_HOSTS, "refusing non-local database host")


def run(command: list[str], *, timeout: float = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a Docker command without a shell or inherited Compose project state."""
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def compose_command(project: str, *arguments: str) -> list[str]:
    return ["docker", "compose", "--project-name", project, "--file", str(COMPOSE_FILE), *arguments]


def redact(value: str) -> str:
    """Keep test logs useful without preserving credentials or bearer values."""
    return SECRET_PATTERN.sub(
        lambda match: (
            f"{match.group(1)}<redacted>{match.group(3)}" if match.group(1) else f"{match.group(4)}<redacted>"
        ),
        value,
    )


def write_evidence(path: Path, value: str) -> None:
    path.write_text(redact(value), encoding="utf-8")
    path.chmod(0o600)


def write_checksums(evidence_dir: Path) -> str:
    checksums: dict[str, str] = {}
    for path in sorted(evidence_dir.iterdir()):
        if path.name == "sha256sums.json" or not path.is_file():
            continue
        checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    checksum_path = evidence_dir / "sha256sums.json"
    checksum_path.write_text(json.dumps(checksums, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksum_path.chmod(0o600)
    return hashlib.sha256(checksum_path.read_bytes()).hexdigest()


def image_id(project: str, service: str) -> str:
    result = run(
        [
            "docker",
            "image",
            "ls",
            "--quiet",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--filter",
            f"label=com.docker.compose.service={service}",
        ]
    )
    result_id = result.stdout.strip()
    require(result_id, f"no image built for {service}")
    return result_id


def assert_image_command(project: str, service: str, *, migrates: bool) -> None:
    command = json.loads(
        run(["docker", "image", "inspect", image_id(project, service), "--format", "{{json .Config.Cmd}}"]).stdout
    )
    rendered = " ".join(command or [])
    has_migration = "alembic upgrade head" in rendered
    require(has_migration is migrates, f"{service} migration command contract differs")


def assert_isolated_compose(project: str) -> None:
    """Reject a verifier Compose file that has acquired host bind mounts."""
    rendered = json.loads(run(compose_command(project, "config", "--format", "json")).stdout)
    for service_name, service in rendered["services"].items():
        for mount in service.get("volumes", []):
            if mount.get("type") == "bind":
                raise AssertionError(f"{service_name} has a forbidden host bind mount")
    postgres_mounts = rendered["services"]["postgres"].get("volumes", [])
    require(
        len(postgres_mounts) == 1 and postgres_mounts[0].get("type") == "volume",
        "postgres must use exactly one ephemeral named volume",
    )
    for service_name in ("backend", "recall"):
        require(
            not rendered["services"][service_name].get("volumes", []),
            f"{service_name} must not mount host state",
        )


def container_id(project: str, service: str) -> str:
    result_id = run(compose_command(project, "ps", "--quiet", service)).stdout.strip()
    require(result_id, f"no running container for {service}")
    return result_id


def assert_container_timezone(project: str, service: str) -> None:
    container = container_id(project, service)
    environment = json.loads(run(["docker", "inspect", container, "--format", "{{json .Config.Env}}"]).stdout)
    require("PYTHONTZPATH=" in environment, f"{service} does not set PYTHONTZPATH to empty")
    probe = run(compose_command(project, "exec", "--no-TTY", service, "python", "-c", ZONE_PROBE))
    require("tzdata-zoneinfo-ok" in probe.stdout, f"{service} cannot resolve tzdata zones with empty TZPATH")


def await_backend_health(project: str, deadline: float) -> None:
    while time.monotonic() < deadline:
        inspection = json.loads(
            run(
                ["docker", "inspect", container_id(project, "backend"), "--format", "{{json .State.Health.Status}}"]
            ).stdout
        )
        if inspection == "healthy":
            return
        time.sleep(2)
    raise AssertionError("backend did not become healthy within 120 seconds")


def await_recall_start(project: str, deadline: float) -> str:
    while time.monotonic() < deadline:
        logs = run(compose_command(project, "logs", "--no-color"), check=False).stdout
        if "Starting Runestone Telegram Bot Worker" in logs:
            return logs
        time.sleep(1)
    raise AssertionError("Recall did not start within 120 seconds")


def main() -> int:
    args = parse_args()
    require_safe_database_url(args.database_url)
    require(COMPOSE_FILE.is_file(), "isolated Compose file is missing")
    project = f"runestone_recall_schedule_{uuid4().hex[:12]}"
    evidence_dir = EVIDENCE_ROOT / uuid4().hex
    evidence_dir.mkdir(parents=True, mode=0o700)
    evidence_dir.chmod(0o700)
    stack_started = False
    failure: BaseException | None = None
    try:
        run(compose_command(project, "config", "--quiet"))
        assert_isolated_compose(project)
        run(compose_command(project, "build", "backend", "recall"), timeout=1200)
        assert_image_command(project, "backend", migrates=True)
        assert_image_command(project, "recall", migrates=False)
        run(compose_command(project, "up", "--detach", "postgres", "backend", "recall"), timeout=120)
        stack_started = True
        deadline = time.monotonic() + 120
        await_backend_health(project, deadline)
        assert_container_timezone(project, "backend")
        assert_container_timezone(project, "recall")
        logs = await_recall_start(project, deadline)
        # The backend cannot reach FastAPI startup until its CMD's preceding
        # ``alembic upgrade head`` succeeds, so this is migration-success
        # evidence rather than merely observing Alembic begin the upgrade.
        backend_migration = logs.find("Application startup complete.")
        recall_start = logs.find("Starting Runestone Telegram Bot Worker")
        require(backend_migration >= 0, "backend migration-success log is absent")
        require(
            recall_start >= 0 and backend_migration < recall_start,
            "Recall started before backend migration evidence",
        )
        write_evidence(evidence_dir / "compose-ps.txt", run(compose_command(project, "ps")).stdout)
        write_evidence(evidence_dir / "container-logs.txt", logs)
        write_evidence(evidence_dir / "report.json", json.dumps({"project": project, "status": "passed"}, indent=2))
    except BaseException as exc:
        failure = exc
        write_evidence(evidence_dir / "failure.txt", f"{type(exc).__name__}: {exc}\n")
        raise
    finally:
        if stack_started:
            write_evidence(
                evidence_dir / "compose-ps-final.txt",
                run(compose_command(project, "ps"), check=False).stdout,
            )
            write_evidence(
                evidence_dir / "container-logs-final.txt",
                run(compose_command(project, "logs", "--no-color"), check=False).stdout,
            )
        down = run(compose_command(project, "down", "--volumes", "--remove-orphans"), timeout=120, check=False)
        write_evidence(evidence_dir / "compose-down.txt", down.stdout + down.stderr)
        checksum = write_checksums(evidence_dir)
        if failure is None and down.returncode != 0:
            raise RuntimeError(f"isolated Compose cleanup failed; evidence={evidence_dir}")
    print(f"PASS isolated recall container startup; evidence={evidence_dir}; checksum={checksum}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, subprocess.SubprocessError, OSError, ValueError) as exc:
        print(f"FAIL isolated recall container startup: {exc}", file=sys.stderr)
        raise SystemExit(1)
