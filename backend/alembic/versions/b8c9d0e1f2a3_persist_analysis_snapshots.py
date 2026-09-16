"""persist analysis score snapshots

Revision ID: b8c9d0e1f2a3
Revises: a5b6c7d8e9f0
Create Date: 2026-09-16 00:00:00.000000

Adds nullable snapshot metadata to job_analyses so every stored analysis can
reproduce its own explanation: the score breakdown at analysis time, hashes of
the job and resume inputs, and the exact resume version used. Existing rows
keep NULL and are treated as legacy results; nothing is backfilled.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a5b6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_analyses",
        sa.Column("score_breakdown", JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "job_analyses",
        sa.Column("job_text_hash", sa.String(), nullable=True),
    )
    op.add_column(
        "job_analyses",
        sa.Column("resume_version_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_job_analyses_resume_version_id",
        "job_analyses",
        "resume_versions",
        ["resume_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "job_analyses",
        sa.Column("resume_text_hash", sa.String(), nullable=True),
    )


def downgrade() -> None:
    # Drop only the snapshot metadata; analyses themselves are never deleted.
    op.drop_column("job_analyses", "resume_text_hash")
    op.drop_constraint("fk_job_analyses_resume_version_id", "job_analyses", type_="foreignkey")
    op.drop_column("job_analyses", "resume_version_id")
    op.drop_column("job_analyses", "job_text_hash")
    op.drop_column("job_analyses", "score_breakdown")
