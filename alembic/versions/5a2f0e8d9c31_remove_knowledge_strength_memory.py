"""remove_knowledge_strength_memory

Revision ID: 5a2f0e8d9c31
Revises: a91c2d4e5f60
Create Date: 2026-04-30 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5a2f0e8d9c31"
down_revision: Union[str, Sequence[str], None] = "a91c2d4e5f60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Delete memory rows for the removed knowledge_strength category."""
    op.execute(sa.text("DELETE FROM memory_items WHERE category = 'knowledge_strength'"))


def downgrade() -> None:
    """No-op: deleted knowledge_strength memory rows cannot be restored."""
    pass
