"""add resume drafts and interview prep

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-07-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("resume_versions", sa.Column("job_id", sa.Uuid(), nullable=True))
    op.add_column("resume_versions", sa.Column("source_version_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_resume_versions_job_id"), "resume_versions", ["job_id"])
    op.create_foreign_key(
        "fk_resume_versions_job_id_jobs",
        "resume_versions",
        "jobs",
        ["job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_resume_versions_source_version_id_resume_versions",
        "resume_versions",
        "resume_versions",
        ["source_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "interview_preps",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=True),
        sa.Column("resume_id", sa.Uuid(), nullable=True),
        sa.Column("resume_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "reviewed", "ready", "archived", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("model_used", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resume_version_id"], ["resume_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_interview_preps_job_id"), "interview_preps", ["job_id"])
    op.create_index(op.f("ix_interview_preps_user_id"), "interview_preps", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_interview_preps_user_id"), table_name="interview_preps")
    op.drop_index(op.f("ix_interview_preps_job_id"), table_name="interview_preps")
    op.drop_table("interview_preps")
    op.drop_constraint(
        "fk_resume_versions_source_version_id_resume_versions",
        "resume_versions",
        type_="foreignkey",
    )
    op.drop_constraint("fk_resume_versions_job_id_jobs", "resume_versions", type_="foreignkey")
    op.drop_index(op.f("ix_resume_versions_job_id"), table_name="resume_versions")
    op.drop_column("resume_versions", "source_version_id")
    op.drop_column("resume_versions", "job_id")
