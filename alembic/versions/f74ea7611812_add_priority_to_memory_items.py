"""add_priority_to_memory_items

Revision ID: f74ea7611812
Revises: c1a9f0f6b2d1
Create Date: 2026-03-04 15:28:44.744819

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f74ea7611812"
down_revision: Union[str, Sequence[str], None] = "c1a9f0f6b2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add priority column to memory_items (nullable integer 0-9, area_to_improve only)."""
    op.add_column("memory_items", sa.Column("priority", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove priority column from memory_items."""
    op.drop_column("memory_items", "priority")
