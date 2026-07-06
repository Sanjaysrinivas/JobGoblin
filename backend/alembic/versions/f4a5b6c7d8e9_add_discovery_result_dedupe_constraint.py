"""add discovery result dedupe constraint

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-07-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f4a5b6c7d8e9"
down_revision: str | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "uq_job_search_results_user_dedupe"


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY user_id, dedupe_key
                        ORDER BY CASE WHEN status = 'saved' THEN 0 ELSE 1 END, created_at DESC, id DESC
                    ) AS row_number
                FROM job_search_results
            )
            DELETE FROM job_search_results
            USING ranked
            WHERE job_search_results.id = ranked.id
              AND ranked.row_number > 1
            """
        )
    )
    op.create_unique_constraint(
        _CONSTRAINT,
        "job_search_results",
        ["user_id", "dedupe_key"],
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "job_search_results", type_="unique")
