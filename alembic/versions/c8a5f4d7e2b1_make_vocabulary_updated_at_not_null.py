"""make vocabulary updated_at not null

Revision ID: c8a5f4d7e2b1
Revises: 6b7c2e1a9d4f
Create Date: 2026-04-29 11:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8a5f4d7e2b1"
down_revision: Union[str, Sequence[str], None] = "6b7c2e1a9d4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sa.text("UPDATE vocabulary SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))

    with op.batch_alter_table("vocabulary", schema=None) as batch_op:
        batch_op.alter_column("updated_at", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("vocabulary", schema=None) as batch_op:
        batch_op.alter_column("updated_at", nullable=True)
