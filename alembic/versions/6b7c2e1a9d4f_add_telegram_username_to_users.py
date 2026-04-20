"""add telegram_username to users

Revision ID: 6b7c2e1a9d4f
Revises: 2b8fd9c1a4e6
Create Date: 2026-04-20 10:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "6b7c2e1a9d4f"
down_revision: Union[str, Sequence[str], None] = "2b8fd9c1a4e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("telegram_username", sa.String(), nullable=True))
    with context.get_context().autocommit_block():
        op.create_index(
            "ix_users_telegram_username",
            "users",
            ["telegram_username"],
            unique=True,
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with context.get_context().autocommit_block():
        op.drop_index("ix_users_telegram_username", table_name="users", postgresql_concurrently=True)
    op.drop_column("users", "telegram_username")
