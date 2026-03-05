"""sync_postgres_id_sequences

Revision ID: e5d9d2f11a77
Revises: c1a9f0f6b2d1
Create Date: 2026-03-05 10:05:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5d9d2f11a77"
down_revision: Union[str, Sequence[str], None] = "c1a9f0f6b2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sync_table_id_sequence(conn, table: str) -> None:
    seq_name = conn.execute(sa.text("SELECT pg_get_serial_sequence(:tbl, 'id')"), {"tbl": f"public.{table}"}).scalar()
    if not seq_name:
        return

    max_id = conn.execute(sa.text(f'SELECT COALESCE(MAX(id), 0) FROM "{table}"')).scalar() or 0
    conn.execute(sa.text("SELECT setval(:seq, :next_id, false)"), {"seq": seq_name, "next_id": int(max_id) + 1})


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    for table in ("users", "vocabulary", "chat_messages", "chat_summaries", "memory_items"):
        if table in existing_tables:
            _sync_table_id_sequence(conn, table)


def downgrade() -> None:
    """Downgrade schema."""
    # No-op: sequence synchronization is data-repair only.
    pass
