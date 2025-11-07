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
    # Get connection and inspector to check existing structure
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check existing tables and columns
    existing_tables = set(inspector.get_table_names())
    vocabulary_columns = {col["name"] for col in inspector.get_columns("vocabulary")}

    # Create users table only if it doesn't exist
    if "users" not in existing_tables:
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

    # Add user_id column to vocabulary table in a robust way
    with op.batch_alter_table("vocabulary", schema=None) as batch_op:
        # Check if user_id_temp already exists (from partial migration)
        if "user_id_temp" not in vocabulary_columns:
            batch_op.add_column(sa.Column("user_id_temp", sa.Integer(), nullable=True))

        # Populate user_id_temp with default user ID
        op.execute("UPDATE vocabulary SET user_id_temp = 1 WHERE user_id_temp IS NULL")

        # Only drop user_id if it exists (it shouldn't exist in initial state)
        if "user_id" in vocabulary_columns:
            batch_op.drop_column("user_id")

        # Add the proper user_id column
        if "user_id" not in vocabulary_columns:
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=False))

        # Copy data from temp column to user_id
        op.execute("UPDATE vocabulary SET user_id = user_id_temp")

        # Drop temp column
        batch_op.drop_column("user_id_temp")

        # Check if foreign key constraint already exists
        existing_constraints = {const["name"] for const in inspector.get_foreign_keys("vocabulary")}
        if "fk_vocabulary_user_id" not in existing_constraints:
            batch_op.create_foreign_key("fk_vocabulary_user_id", "users", ["user_id"], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    # Get connection and inspector to check existing structure
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check existing constraints
    constraints = {const["name"] for const in inspector.get_foreign_keys("vocabulary")}

    # Remove foreign key constraint if it exists
    if "fk_vocabulary_user_id" in constraints:
        op.drop_constraint("fk_vocabulary_user_id", "vocabulary", type_="foreignkey")

    # Check existing columns
    vocabulary_columns = {col["name"] for col in inspector.get_columns("vocabulary")}

    # Convert back to nullable integer without foreign key using batch mode
    with op.batch_alter_table("vocabulary", schema=None) as batch_op:
        # Only add temp column if it doesn't exist
        if "user_id_old" not in vocabulary_columns:
            batch_op.add_column(sa.Column("user_id_old", sa.Integer(), nullable=True))

        # Copy current user_id to temp column
        op.execute("UPDATE vocabulary SET user_id_old = user_id")

        # Drop current user_id column if it exists
        if "user_id" in vocabulary_columns:
            batch_op.drop_column("user_id")

        # Add new user_id column as nullable
        if "user_id" not in vocabulary_columns:
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=False))

        # Copy data back
        op.execute("UPDATE vocabulary SET user_id = user_id_old WHERE user_id_old IS NOT NULL")
        op.execute("UPDATE vocabulary SET user_id = 1 WHERE user_id IS NULL")

        # Drop temp column
        batch_op.drop_column("user_id_old")

    # Drop users table
    op.drop_table("users")
