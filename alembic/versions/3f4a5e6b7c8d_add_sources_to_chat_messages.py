"""add sources to chat messages

Revision ID: 3f4a5e6b7c8d
Revises: d669959e47fc
Create Date: 2026-02-05 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f4a5e6b7c8d"
down_revision: Union[str, Sequence[str], None] = "687468b4400f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sources", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.drop_column("sources")
