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

    # Create users table if it doesn't exist
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

    # Create default user if it doesn't exist
    # Check if user with id=1 exists
    result = conn.execute(sa.text("SELECT COUNT(*) FROM users WHERE id = 1"))
    user_count = result.scalar()

    if user_count == 0:
        # Insert default user
        conn.execute(
            sa.text(
                """
                INSERT INTO users (id, email, hashed_password, name, surname, timezone, pages_recognised_count)
                VALUES (1, 'user1@example.com',
                        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeE8e0zqjzKj1Q9K',
                        '40min', NULL, 'UTC', 0)
            """
            )
        )

    # Add user_id column to vocabulary table if it doesn't exist
    if "user_id" not in vocabulary_columns:
        with op.batch_alter_table("vocabulary", schema=None) as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=False, server_default="1"))

    # Update all vocabulary rows to have user_id = 1
    op.execute(sa.text("UPDATE vocabulary SET user_id = 1 WHERE user_id IS NULL OR user_id = 0"))

    # Add foreign key constraint if it doesn't exist
    existing_constraints = {const["name"] for const in inspector.get_foreign_keys("vocabulary")}
    if "fk_vocabulary_user_id" not in existing_constraints:
        with op.batch_alter_table("vocabulary", schema=None) as batch_op:
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

    # Remove user_id column and add it back as nullable
    if "user_id" in vocabulary_columns:
        with op.batch_alter_table("vocabulary", schema=None) as batch_op:
            batch_op.drop_column("user_id")
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))

    # Drop users table
    op.drop_table("users")
