"""Initial migration for existing vocabulary table

Revision ID: b20791858459
Revises:
Create Date: 2025-10-08 11:01:40.889993

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b20791858459"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add the learned_times column to existing vocabulary table
    op.add_column("vocabulary", sa.Column("learned_times", sa.Integer(), server_default="0", nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the learned_times column from vocabulary table
    op.drop_column("vocabulary", "learned_times")
    # ### end Alembic commands ###
