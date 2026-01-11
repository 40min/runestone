"""add_user_memory_fields

Revision ID: 8b16087d0580
Revises: d669959e47fc
Create Date: 2026-01-11 00:23:04.133991

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b16087d0580"
down_revision: Union[str, Sequence[str], None] = "d669959e47fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add agent memory fields to users table
    op.add_column("users", sa.Column("personal_info", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("areas_to_improve", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("knowledge_strengths", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove agent memory fields from users table
    op.drop_column("users", "knowledge_strengths")
    op.drop_column("users", "areas_to_improve")
    op.drop_column("users", "personal_info")
