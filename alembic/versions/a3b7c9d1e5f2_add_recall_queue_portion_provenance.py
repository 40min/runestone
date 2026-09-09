"""add recall queue portion provenance and default vocabulary priority 5

Revision ID: a3b7c9d1e5f2
Revises: d4f8a2c7e1b9
Create Date: 2026-09-09 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a3b7c9d1e5f2"
down_revision: Union[str, Sequence[str], None] = "d4f8a2c7e1b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VOCABULARY_PRIORITY_DEFAULT = 5
VOCABULARY_PRIORITY_LEGACY_DEFAULT = 9


def upgrade() -> None:
    """Add queue portion provenance and switch the vocabulary default priority to 5."""
    bind = op.get_bind()
    bind.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
    bind.execute(sa.text("SET LOCAL statement_timeout = '60s'"))

    # Historical provenance cannot be reconstructed reliably from priority,
    # learning counters, or deployment-specific settings; backfill as regular.
    op.add_column(
        "recall_queue_items",
        sa.Column("is_unstudied_extra", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.alter_column(
        "vocabulary",
        "priority_learn",
        existing_type=sa.Integer(),
        server_default=str(VOCABULARY_PRIORITY_DEFAULT),
    )


def downgrade() -> None:
    """Restore the legacy default priority and drop the provenance flag."""
    op.alter_column(
        "vocabulary",
        "priority_learn",
        existing_type=sa.Integer(),
        server_default=str(VOCABULARY_PRIORITY_LEGACY_DEFAULT),
    )
    op.drop_column("recall_queue_items", "is_unstudied_extra")
