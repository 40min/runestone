"""add extra_info to vocabulary table

Revision ID: f7e03c56dd1a
Revises: b20791858459
Create Date: 2025-10-08 11:56:55.072383

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7e03c56dd1a"
down_revision: Union[str, Sequence[str], None] = "b20791858459"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Get connection and inspector to check existing structure
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check existing columns, indexes, and constraints
    columns = {col["name"] for col in inspector.get_columns("vocabulary")}
    indexes = {idx["name"] for idx in inspector.get_indexes("vocabulary")}
    constraints = {const["name"] for const in inspector.get_unique_constraints("vocabulary")}

    # Use batch mode for SQLite compatibility
    with op.batch_alter_table("vocabulary", schema=None) as batch_op:
        # Add extra_info column if it doesn't exist
        if "extra_info" not in columns:
            batch_op.add_column(sa.Column("extra_info", sa.Text(), nullable=True))

        # Add index on word_phrase if it doesn't exist
        if "ix_vocabulary_word_phrase" not in indexes:
            batch_op.create_index(batch_op.f("ix_vocabulary_word_phrase"), ["word_phrase"], unique=False)

        # Add unique constraint if it doesn't exist
        if "uq_user_word_phrase" not in constraints:
            batch_op.create_unique_constraint("uq_user_word_phrase", ["user_id", "word_phrase"])


def downgrade() -> None:
    """Downgrade schema."""
    # Get connection and inspector to check existing structure
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check existing columns, indexes, and constraints
    columns = {col["name"] for col in inspector.get_columns("vocabulary")}
    indexes = {idx["name"] for idx in inspector.get_indexes("vocabulary")}
    constraints = {const["name"] for const in inspector.get_unique_constraints("vocabulary")}

    # Use batch mode for SQLite compatibility
    with op.batch_alter_table("vocabulary", schema=None) as batch_op:
        # Drop constraint if it exists
        if "uq_user_word_phrase" in constraints:
            batch_op.drop_constraint("uq_user_word_phrase", type_="unique")

        # Drop index if it exists
        if "ix_vocabulary_word_phrase" in indexes:
            batch_op.drop_index(batch_op.f("ix_vocabulary_word_phrase"))

        # Drop column if it exists
        if "extra_info" in columns:
            batch_op.drop_column("extra_info")
