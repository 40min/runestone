"""add telegram_username to users

Revision ID: 6b7c2e1a9d4f
Revises: 2b8fd9c1a4e6
Create Date: 2026-04-20 10:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b7c2e1a9d4f"
down_revision: Union[str, Sequence[str], None] = "2b8fd9c1a4e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("telegram_username", sa.String(), nullable=True))
        batch_op.create_index("ix_users_telegram_username", ["telegram_username"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_telegram_username")
        batch_op.drop_column("telegram_username")
