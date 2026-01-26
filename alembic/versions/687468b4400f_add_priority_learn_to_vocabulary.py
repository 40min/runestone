"""add_priority_learn_to_vocabulary

Revision ID: 687468b4400f
Revises: 4ed3a3332b2a
Create Date: 2026-01-26 11:59:02.215963

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "687468b4400f"
down_revision: Union[str, Sequence[str], None] = "4ed3a3332b2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("vocabulary", sa.Column("priority_learn", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("vocabulary", "priority_learn")
