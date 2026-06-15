"""add_personal_info_summary_to_users

Revision ID: 1c2d3e4f5a6b
Revises: 5a2f0e8d9c31
Create Date: 2026-06-11 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1c2d3e4f5a6b"
down_revision: Union[str, Sequence[str], None] = "5a2f0e8d9c31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("personal_info_summary", sa.Text(), nullable=True))
    op.drop_constraint("uq_memory_items_user_category_key", "memory_items", type_="unique")
    op.create_index(
        "ix_memory_items_user_area_key_unique",
        "memory_items",
        ["user_id", "category", "key"],
        unique=True,
        postgresql_where=sa.text("category = 'area_to_improve'"),
        sqlite_where=sa.text("category = 'area_to_improve'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_memory_items_user_area_key_unique", table_name="memory_items")
    op.execute(
        """
        DELETE FROM memory_items
        WHERE id IN (
            SELECT id
            FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY user_id, category, key
                        ORDER BY updated_at DESC, id DESC
                    ) AS row_num
                FROM memory_items
                WHERE category = 'personal_info'
            ) duplicate_rows
            WHERE row_num > 1
        )
        """
    )
    op.create_unique_constraint(
        "uq_memory_items_user_category_key",
        "memory_items",
        ["user_id", "category", "key"],
    )
    op.drop_column("users", "personal_info_summary")
