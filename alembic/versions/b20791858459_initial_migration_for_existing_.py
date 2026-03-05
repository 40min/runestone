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
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # Fresh database path (e.g. new Postgres): bootstrap the base vocabulary table.
    # Existing database path: keep original behavior and only add missing columns.
    if "vocabulary" not in existing_tables:
        table_args = [
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "word_phrase", name="uq_user_word_phrase"),
        ]
        # Fresh databases can reach this migration before the users table migration.
        # Add the FK only when the users table already exists.
        if "users" in existing_tables:
            table_args.append(sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_vocabulary_user_id"))

        op.create_table(
            "vocabulary",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False, server_default=None),
            sa.Column("word_phrase", sa.Text(), nullable=False),
            sa.Column("translation", sa.Text(), nullable=False),
            sa.Column("example_phrase", sa.Text(), nullable=True),
            sa.Column("extra_info", sa.Text(), nullable=True, server_default=None),
            sa.Column("in_learn", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_learned", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")
            ),
            sa.Column("learned_times", sa.Integer(), nullable=False, server_default="0"),
            *table_args,
        )
        op.create_index("ix_vocabulary_word_phrase", "vocabulary", ["word_phrase"])
        return

    columns = {col["name"] for col in inspector.get_columns("vocabulary")}
    if "learned_times" not in columns:
        op.add_column("vocabulary", sa.Column("learned_times", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "vocabulary" not in existing_tables:
        return

    columns = {col["name"] for col in inspector.get_columns("vocabulary")}
    if "learned_times" in columns:
        op.drop_column("vocabulary", "learned_times")
