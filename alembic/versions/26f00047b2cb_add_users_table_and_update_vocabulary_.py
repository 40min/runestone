"""Add users table and update vocabulary with foreign key

Revision ID: 26f00047b2cb
Revises: f7e03c56dd1a
Create Date: 2025-11-04 08:59:15.183266

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "26f00047b2cb"
down_revision: Union[str, Sequence[str], None] = "f7e03c56dd1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("surname", sa.String(), nullable=True),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column("pages_recognised_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    # Add foreign key constraint to vocabulary table
    op.add_column("vocabulary", sa.Column("user_id_temp", sa.Integer(), nullable=True))
    op.execute("UPDATE vocabulary SET user_id_temp = 1 WHERE user_id_temp IS NULL OR user_id_temp = 0")
    op.drop_column("vocabulary", "user_id")
    op.add_column("vocabulary", sa.Column("user_id", sa.Integer(), nullable=False))
    op.execute("UPDATE vocabulary SET user_id = user_id_temp")
    op.drop_column("vocabulary", "user_id_temp")
    op.create_foreign_key("fk_vocabulary_user_id", "vocabulary", "users", ["user_id"], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove foreign key constraint
    op.drop_constraint("fk_vocabulary_user_id", "vocabulary", type_="foreignkey")

    # Convert back to nullable integer without foreign key
    op.add_column("vocabulary", sa.Column("user_id_old", sa.Integer(), nullable=True))
    op.execute("UPDATE vocabulary SET user_id_old = user_id")
    op.drop_column("vocabulary", "user_id")
    op.add_column("vocabulary", sa.Column("user_id", sa.Integer(), nullable=False))
    op.execute("UPDATE vocabulary SET user_id = user_id_old WHERE user_id_old IS NOT NULL")
    op.execute("UPDATE vocabulary SET user_id = 1 WHERE user_id IS NULL")
    op.drop_column("vocabulary", "user_id_old")

    # Drop users table
    op.drop_table("users")
