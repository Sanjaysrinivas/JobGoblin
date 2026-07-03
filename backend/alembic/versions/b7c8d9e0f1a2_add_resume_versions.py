"""add resume versions

Revision ID: b7c8d9e0f1a2
Revises: a8b9c0d1e2f3
Create Date: 2026-07-03 00:00:00.000000

"""
from collections.abc import Sequence
import uuid

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "a8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resume_versions",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resume_id", sa.Uuid(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("extracted_text", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("parsed_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_resume_versions_resume_id"),
        "resume_versions",
        ["resume_id"],
        unique=False,
    )

    bind = op.get_bind()
    versions = sa.table(
        "resume_versions",
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("id", sa.Uuid()),
        sa.column("resume_id", sa.Uuid()),
        sa.column("title", sqlmodel.sql.sqltypes.AutoString()),
        sa.column("extracted_text", sqlmodel.sql.sqltypes.AutoString()),
        sa.column("parsed_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("is_current", sa.Boolean()),
    )
    resumes = bind.execute(
        sa.text(
            """
            SELECT id, title, extracted_text, parsed_json, created_at, updated_at
            FROM resumes
            """
        )
    )
    rows = [
        {
            "created_at": resume["created_at"],
            "updated_at": resume["updated_at"],
            "id": uuid.uuid4(),
            "resume_id": resume["id"],
            "title": resume["title"],
            "extracted_text": resume["extracted_text"],
            "parsed_json": resume["parsed_json"],
            "is_current": True,
        }
        for resume in resumes.mappings()
    ]
    if rows:
        bind.execute(versions.insert(), rows)


def downgrade() -> None:
    op.drop_index(op.f("ix_resume_versions_resume_id"), table_name="resume_versions")
    op.drop_table("resume_versions")
