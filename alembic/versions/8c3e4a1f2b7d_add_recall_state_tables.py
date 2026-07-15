"""add recall state tables

Revision ID: 8c3e4a1f2b7d
Revises: 2f7c9d1a4b6e
Create Date: 2026-07-13 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c3e4a1f2b7d"
down_revision: Union[str, Sequence[str], None] = "2f7c9d1a4b6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_vocabulary_user_id_id",
        "vocabulary",
        ["user_id", "id"],
    )
    op.create_table(
        "recall_user_states",
        sa.Column("user_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("next_word_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.CheckConstraint("next_word_index >= 0", name="ck_recall_user_states_next_word_index_non_negative"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_recall_user_states_user_id_users",
        ),
    )
    op.create_table(
        "recall_queue_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("vocabulary_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("position >= 0", name="ck_recall_queue_items_position_non_negative"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["recall_user_states.user_id"],
            name="fk_recall_queue_items_user_id_recall_user_states",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "vocabulary_id"],
            ["vocabulary.user_id", "vocabulary.id"],
            name="fk_recall_queue_items_user_vocabulary_vocabulary",
        ),
        sa.UniqueConstraint("user_id", "position", name="uq_recall_queue_items_user_position"),
        sa.UniqueConstraint("user_id", "vocabulary_id", name="uq_recall_queue_items_user_vocabulary"),
    )
    op.create_index("ix_recall_queue_items_user_id", "recall_queue_items", ["user_id"])
    op.create_index("ix_recall_queue_items_vocabulary_id", "recall_queue_items", ["vocabulary_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_recall_queue_items_vocabulary_id", table_name="recall_queue_items")
    op.drop_index("ix_recall_queue_items_user_id", table_name="recall_queue_items")
    op.drop_table("recall_queue_items")
    op.drop_table("recall_user_states")
    op.drop_constraint("uq_vocabulary_user_id_id", "vocabulary", type_="unique")
