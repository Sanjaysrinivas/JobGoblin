"""add activity event sequence

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-07-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: str | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEQUENCE = "activity_events_activity_sequence_seq"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SEQUENCE IF NOT EXISTS {_SEQUENCE}"))
    op.add_column("activity_events", sa.Column("activity_sequence", sa.BigInteger(), nullable=True))
    op.execute(
        sa.text(
            """
            WITH ordered AS (
                SELECT id, row_number() OVER (ORDER BY created_at, id) AS sequence_value
                FROM activity_events
            )
            UPDATE activity_events
            SET activity_sequence = ordered.sequence_value
            FROM ordered
            WHERE activity_events.id = ordered.id
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            SELECT setval(
                '{_SEQUENCE}',
                COALESCE((SELECT max(activity_sequence) FROM activity_events), 0) + 1,
                false
            )
            """
        )
    )
    op.alter_column(
        "activity_events",
        "activity_sequence",
        nullable=False,
        server_default=sa.text(f"nextval('{_SEQUENCE}'::regclass)"),
    )
    op.create_unique_constraint(
        "uq_activity_events_activity_sequence",
        "activity_events",
        ["activity_sequence"],
    )
    op.execute(sa.text(f"ALTER SEQUENCE {_SEQUENCE} OWNED BY activity_events.activity_sequence"))


def downgrade() -> None:
    op.drop_constraint(
        "uq_activity_events_activity_sequence",
        "activity_events",
        type_="unique",
    )
    op.drop_column("activity_events", "activity_sequence")
    op.execute(sa.text(f"DROP SEQUENCE IF EXISTS {_SEQUENCE}"))
