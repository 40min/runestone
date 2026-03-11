"""replace_memory_migrated_with_active

Revision ID: 7f40b49ad9b2
Revises: f74ea7611812
Create Date: 2026-03-10 13:56:40.329098

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f40b49ad9b2"
down_revision: Union[str, Sequence[str], None] = "f74ea7611812"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.execute("UPDATE users SET active = true")
    op.drop_column("users", "memory_migrated")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "memory_migrated", sa.BOOLEAN(), server_default=sa.text("false"), autoincrement=False, nullable=False
        ),
    )
    op.drop_column("users", "active")
