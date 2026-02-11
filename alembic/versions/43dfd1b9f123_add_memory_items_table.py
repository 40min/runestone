"""add_memory_items_table

Revision ID: 43dfd1b9f123
Revises: 3f4a5e6b7c8d
Create Date: 2026-02-09 11:31:42.141556

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "43dfd1b9f123"
down_revision: Union[str, Sequence[str], None] = "3f4a5e6b7c8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create memory_items table
    op.create_table(
        "memory_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_memory_items_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_items")),
        sa.UniqueConstraint("user_id", "category", "key", name=op.f("uq_memory_items_user_category_key")),
    )

    # Create indexes for efficient queries
    op.create_index(
        op.f("ix_memory_items_user_id_category_status"),
        "memory_items",
        ["user_id", "category", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_items_user_id_updated_at"),
        "memory_items",
        ["user_id", "updated_at"],
        unique=False,
    )

    # Add memory_migrated flag to users table
    op.add_column("users", sa.Column("memory_migrated", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove memory_migrated flag from users table
    op.drop_column("users", "memory_migrated")

    # Drop indexes
    op.drop_index(op.f("ix_memory_items_user_id_updated_at"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_user_id_category_status"), table_name="memory_items")

    # Drop memory_items table
    op.drop_table("memory_items")
