"""add job discovery

Revision ID: c1d2e3f4a5b6
Revises: b7c8d9e0f1a2
Create Date: 2026-07-03 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_search_preferences",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_countries", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("target_locations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("desired_titles", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("seniority", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("industries", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("required_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("optional_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("excluded_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("visa_sponsorship_required", sa.Boolean(), nullable=False),
        sa.Column("blocked_companies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "work_mode",
            sa.Enum("onsite", "remote", "hybrid", "unknown", native_enum=False, length=40),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_job_search_preferences_user_id"),
    )
    op.create_table(
        "job_search_runs",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "completed", "failed", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("country", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("location", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("query", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("preferences_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_job_search_runs_user_id"), "job_search_runs", ["user_id"], unique=False
    )
    op.create_table(
        "job_search_results",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "linkedin",
                "company_site",
                "indeed",
                "referral",
                "recruiter",
                "other",
                native_enum=False,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("source_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("canonical_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("company_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("location", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "work_mode",
            sa.Enum("onsite", "remote", "hybrid", "unknown", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dedupe_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("fit_score", sa.Integer(), nullable=False),
        sa.Column("fit_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("new", "saved", "dismissed", "blocked", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("saved_job_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["job_search_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["saved_job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_job_search_results_run_id"), "job_search_results", ["run_id"], unique=False
    )
    op.create_index(
        op.f("ix_job_search_results_user_id"), "job_search_results", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_job_search_results_user_id"), table_name="job_search_results")
    op.drop_index(op.f("ix_job_search_results_run_id"), table_name="job_search_results")
    op.drop_table("job_search_results")
    op.drop_index(op.f("ix_job_search_runs_user_id"), table_name="job_search_runs")
    op.drop_table("job_search_runs")
    op.drop_table("job_search_preferences")
