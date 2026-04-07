"""convert vocabulary priority_learn to numeric 0..9

Revision ID: b4e7a0312f4f
Revises: 0d9c6a2b7f41
Create Date: 2026-04-07 11:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4e7a0312f4f"
down_revision: Union[str, Sequence[str], None] = "0d9c6a2b7f41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VOCABULARY_PRIORITY_HIGH = 0
VOCABULARY_PRIORITY_LEGACY_TRUE_BACKFILL = 5
VOCABULARY_PRIORITY_LOW = 9


def upgrade() -> None:
    """Convert boolean priority_learn to numeric 0..9."""
    op.execute("ALTER TABLE vocabulary ALTER COLUMN priority_learn DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE vocabulary
        ALTER COLUMN priority_learn TYPE INTEGER
        USING CASE
            WHEN priority_learn THEN %(legacy_true_backfill)s
            ELSE %(low_priority)s
        END
        """
        % {
            "legacy_true_backfill": VOCABULARY_PRIORITY_LEGACY_TRUE_BACKFILL,
            "low_priority": VOCABULARY_PRIORITY_LOW,
        }
    )
    op.execute(f"UPDATE vocabulary SET priority_learn = COALESCE(priority_learn, {VOCABULARY_PRIORITY_LOW})")
    op.alter_column(
        "vocabulary",
        "priority_learn",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=str(VOCABULARY_PRIORITY_LOW),
    )
    op.create_check_constraint(
        "ck_vocabulary_priority_learn_range",
        "vocabulary",
        f"priority_learn >= {VOCABULARY_PRIORITY_HIGH} AND priority_learn <= {VOCABULARY_PRIORITY_LOW}",
    )


def downgrade() -> None:
    """Convert numeric priority_learn back to boolean."""
    op.drop_constraint("ck_vocabulary_priority_learn_range", "vocabulary", type_="check")
    op.execute("ALTER TABLE vocabulary ALTER COLUMN priority_learn DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE vocabulary
        ALTER COLUMN priority_learn TYPE BOOLEAN
        USING CASE WHEN priority_learn < %(low_priority)s THEN TRUE ELSE FALSE END
        """
        % {"low_priority": VOCABULARY_PRIORITY_LOW}
    )
    op.alter_column(
        "vocabulary",
        "priority_learn",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
