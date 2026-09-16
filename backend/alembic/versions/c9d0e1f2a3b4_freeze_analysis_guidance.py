"""freeze analysis guidance

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-16 00:00:00.000000

Persist the complete user-facing guidance and a hash of every resume input
used by scoring. Existing rows remain valid historical analyses and are not
backfilled from mutable current data.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_analyses",
        sa.Column("guidance_snapshot", JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "job_analyses",
        sa.Column("resume_evidence_hash", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("job_analyses", "resume_evidence_hash")
    op.drop_column("job_analyses", "guidance_snapshot")
