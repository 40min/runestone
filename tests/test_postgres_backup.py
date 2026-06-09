from __future__ import annotations

import os
import stat
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _build_script_env(tmp_path: Path, backup_dir: Path, retention_days: str = "7") -> dict[str, str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "pg_isready",
        "#!/bin/sh\nexit 0\n",
    )
    _write_executable(
        fake_bin / "pg_dump",
        """#!/bin/sh
file=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --file=*)
      file="${1#--file=}"
      shift
      continue
      ;;
    --file)
    file="$2"
    shift 2
    continue
      ;;
  esac
  shift
done
touch "$file"
exit 0
""",
    )
    _write_executable(
        fake_bin / "sleep",
        "#!/bin/sh\nexit 1\n",
    )

    return os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "POSTGRES_BACKUP_DIR": str(backup_dir),
        "POSTGRES_BACKUP_INTERVAL_SECONDS": "60",
        "POSTGRES_BACKUP_RETENTION_DAYS": retention_days,
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "secret",
        "POSTGRES_DB": "runestone",
    }


def test_backup_script_prunes_dumps_older_than_retention_window(tmp_path: Path) -> None:
    """Backups older than the configured retention window should be removed on the next cycle."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    old_dump = backup_dir / "runestone-old.dump"
    old_dump.write_text("stale backup")
    stale_time = datetime.now(UTC) - timedelta(days=7, minutes=1)
    os.utime(old_dump, (stale_time.timestamp(), stale_time.timestamp()))

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "postgres-backup.sh"
    env = _build_script_env(tmp_path, backup_dir)

    result = subprocess.run(
        ["/bin/sh", str(script_path)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert not old_dump.exists()
    assert any(path.name.startswith("runestone-") and path.suffix == ".dump" for path in backup_dir.iterdir())


def test_backup_script_rejects_invalid_retention_days(tmp_path: Path) -> None:
    """Invalid retention settings should fail fast before the backup loop starts."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "postgres-backup.sh"
    env = _build_script_env(tmp_path, backup_dir, retention_days="07")

    result = subprocess.run(
        ["/bin/sh", str(script_path)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "POSTGRES_BACKUP_RETENTION_DAYS must be a positive integer without leading zeros" in result.stdout
