"""drop_legacy_user_memory_columns

Revision ID: a91c2d4e5f60
Revises: c8a5f4d7e2b1
Create Date: 2026-04-29 12:05:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a91c2d4e5f60"
down_revision: Union[str, Sequence[str], None] = "c8a5f4d7e2b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop deprecated memory columns from users."""
    op.drop_column("users", "knowledge_strengths")
    op.drop_column("users", "areas_to_improve")
    op.drop_column("users", "personal_info")


def downgrade() -> None:
    """Recreate legacy user-memory columns."""
    op.add_column("users", sa.Column("personal_info", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("areas_to_improve", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("knowledge_strengths", sa.Text(), nullable=True))
