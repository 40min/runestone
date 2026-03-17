"""add agent side effects table

Revision ID: 0d9c6a2b7f41
Revises: 7f40b49ad9b2
Create Date: 2026-03-16 13:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0d9c6a2b7f41"
down_revision: Union[str, Sequence[str], None] = "7f40b49ad9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "agent_side_effects" not in tables:
        op.create_table(
            "agent_side_effects",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("chat_id", sa.String(), nullable=False),
            sa.Column("specialist_name", sa.String(length=100), nullable=False),
            sa.Column("phase", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("info_for_teacher", sa.Text(), nullable=False),
            sa.Column("artifacts_json", sa.Text(), nullable=True),
            sa.Column("routing_reason", sa.Text(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_agent_side_effects_user_chat_created", "agent_side_effects", ["user_id", "chat_id", "created_at"]
        )
        op.create_index("ix_agent_side_effects_user_chat_phase", "agent_side_effects", ["user_id", "chat_id", "phase"])
        op.create_index(op.f("ix_agent_side_effects_id"), "agent_side_effects", ["id"], unique=False)
        op.create_index(op.f("ix_agent_side_effects_user_id"), "agent_side_effects", ["user_id"], unique=False)
        op.create_index(op.f("ix_agent_side_effects_chat_id"), "agent_side_effects", ["chat_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    indexes = (
        {idx["name"] for idx in inspector.get_indexes("agent_side_effects")}
        if "agent_side_effects" in tables
        else set()
    )

    if "agent_side_effects" in tables:
        for index_name in [
            "ix_agent_side_effects_chat_id",
            "ix_agent_side_effects_user_id",
            "ix_agent_side_effects_id",
            "ix_agent_side_effects_user_chat_phase",
            "ix_agent_side_effects_user_chat_created",
        ]:
            if index_name in indexes:
                op.drop_index(index_name, table_name="agent_side_effects")
        op.drop_table("agent_side_effects")
