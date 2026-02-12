"""make_user_timestamps_not_null

Revision ID: 9e2c7c3a4c21
Revises: 43dfd1b9f123
Create Date: 2026-02-12 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9e2c7c3a4c21"
down_revision: Union[str, Sequence[str], None] = "43dfd1b9f123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Backfill any legacy NULLs before enforcing NOT NULL.
    op.execute(sa.text("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
    op.execute(sa.text("UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("created_at", nullable=False)
        batch_op.alter_column("updated_at", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("created_at", nullable=True)
        batch_op.alter_column("updated_at", nullable=True)
