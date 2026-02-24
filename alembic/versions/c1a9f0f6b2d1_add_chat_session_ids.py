"""add chat session ids

Revision ID: c1a9f0f6b2d1
Revises: 9e2c7c3a4c21
Create Date: 2026-02-24 00:00:00.000000

"""

from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a9f0f6b2d1"
down_revision: Union[str, Sequence[str], None] = "9e2c7c3a4c21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("current_chat_id", sa.String(), nullable=True))

    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.add_column(sa.Column("chat_id", sa.String(), nullable=True))
        batch_op.create_index(batch_op.f("ix_chat_messages_chat_id"), ["chat_id"], unique=False)

    connection = op.get_bind()

    user_ids_with_messages = connection.execute(sa.text("SELECT DISTINCT user_id FROM chat_messages")).fetchall()
    for row in user_ids_with_messages:
        user_id = row[0]
        chat_id = str(uuid4())
        connection.execute(
            sa.text("UPDATE chat_messages SET chat_id = :chat_id WHERE user_id = :user_id"),
            {"chat_id": chat_id, "user_id": user_id},
        )
        connection.execute(
            sa.text("UPDATE users SET current_chat_id = :chat_id WHERE id = :user_id"),
            {"chat_id": chat_id, "user_id": user_id},
        )

    user_ids_missing_chat_id = connection.execute(
        sa.text("SELECT id FROM users WHERE current_chat_id IS NULL")
    ).fetchall()
    for row in user_ids_missing_chat_id:
        connection.execute(
            sa.text("UPDATE users SET current_chat_id = :chat_id WHERE id = :user_id"),
            {"chat_id": str(uuid4()), "user_id": row[0]},
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("current_chat_id", existing_type=sa.String(), nullable=False)

    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.alter_column("chat_id", existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_chat_messages_chat_id"))
        batch_op.drop_column("chat_id")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("current_chat_id")
