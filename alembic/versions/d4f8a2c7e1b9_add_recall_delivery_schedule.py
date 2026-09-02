"""add recall delivery schedule

Revision ID: d4f8a2c7e1b9
Revises: 8c3e4a1f2b7d
Create Date: 2026-09-01 00:00:00.000000

"""

import logging
from typing import Sequence, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sqlalchemy as sa

from alembic import op

revision: str = "d4f8a2c7e1b9"
down_revision: Union[str, Sequence[str], None] = "8c3e4a1f2b7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")


def _normalized_timezone(value: object) -> str:
    if not isinstance(value, str):
        return "UTC"
    normalized = value.strip()
    if normalized != "UTC" and "/" not in normalized:
        return "UTC"
    try:
        ZoneInfo(normalized)
    except (ValueError, ZoneInfoNotFoundError):
        return "UTC"
    return normalized


def upgrade() -> None:
    """Add per-user hours and repair legacy timezone preferences."""
    bind = op.get_bind()
    bind.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
    bind.execute(sa.text("SET LOCAL statement_timeout = '60s'"))

    op.add_column(
        "recall_user_states",
        sa.Column("recall_start_hour", sa.Integer(), nullable=False, server_default="9"),
    )
    op.add_column(
        "recall_user_states",
        sa.Column("recall_end_hour", sa.Integer(), nullable=False, server_default="22"),
    )

    rows = bind.execute(sa.text("SELECT id, timezone FROM users ORDER BY id")).all()
    replacements = [
        {"user_id": user_id, "timezone": normalized}
        for user_id, timezone_value in rows
        if (normalized := _normalized_timezone(timezone_value)) != timezone_value
    ]
    if replacements:
        bind.execute(
            sa.text("UPDATE users SET timezone = :timezone WHERE id = :user_id"),
            replacements,
        )
    logger.info("Normalized %s user timezone rows", len(replacements))

    op.create_check_constraint(
        "ck_recall_user_states_start_hour_range",
        "recall_user_states",
        "recall_start_hour >= 0 AND recall_start_hour <= 23",
    )
    op.create_check_constraint(
        "ck_recall_user_states_end_hour_range",
        "recall_user_states",
        "recall_end_hour >= 0 AND recall_end_hour <= 23",
    )
    op.create_check_constraint(
        "ck_recall_user_states_hours_unequal",
        "recall_user_states",
        "recall_start_hour <> recall_end_hour",
    )


def downgrade() -> None:
    """Remove schedule schema without restoring normalized timezone strings."""
    op.drop_constraint(
        "ck_recall_user_states_hours_unequal",
        "recall_user_states",
        type_="check",
    )
    op.drop_constraint(
        "ck_recall_user_states_end_hour_range",
        "recall_user_states",
        type_="check",
    )
    op.drop_constraint(
        "ck_recall_user_states_start_hour_range",
        "recall_user_states",
        type_="check",
    )
    op.drop_column("recall_user_states", "recall_end_hour")
    op.drop_column("recall_user_states", "recall_start_hour")
