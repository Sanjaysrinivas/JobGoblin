"""enforce resume flags and saved-job identity

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-08-26 00:00:00.000000
"""

import hashlib
import re
from collections.abc import Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import sqlalchemy as sa
from alembic import op

revision: str = "a5b6c7d8e9f0"
down_revision: str | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"[\w+#.-]+", value.casefold()))


def _canonical_url(value: str) -> str:
    raw = value.strip()
    try:
        parsed = urlsplit(raw)
        port_value = parsed.port
    except ValueError:
        return _normalized(raw)
    if not parsed.hostname:
        return _normalized(raw)
    host = (parsed.hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    port = f":{port_value}" if port_value else ""
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_")
            and key.casefold() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}
        )
    )
    return urlunsplit(
        ((parsed.scheme or "https").casefold(), f"{host}{port}", parsed.path.rstrip("/"), query, "")
    )


def _job_key(source_url: str | None, company: str, title: str, location: str | None) -> str:
    identity = (
        f"url:{_canonical_url(source_url)}"
        if source_url
        else "|".join(
            ["fields", _normalized(company), _normalized(title), _normalized(location or "")]
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE applications
            SET applied_at = COALESCE(applied_at, updated_at, created_at)
            WHERE applied_at IS NULL
              AND status IN (
                'applied', 'contacted_recruiter', 'referred', 'phone_screen',
                'technical_interview', 'final_interview', 'offer', 'rejected'
              )
            """
        )
    )
    op.execute(
        sa.text("""
        WITH ranked AS (
            SELECT id, row_number() OVER (
                PARTITION BY user_id ORDER BY updated_at DESC, created_at DESC, id DESC
            ) AS rn FROM resumes WHERE is_default
        )
        UPDATE resumes SET is_default = false FROM ranked
        WHERE resumes.id = ranked.id AND ranked.rn > 1
    """)
    )
    op.execute(
        sa.text("""
        WITH ranked AS (
            SELECT id, row_number() OVER (
                PARTITION BY resume_id ORDER BY updated_at DESC, created_at DESC, id DESC
            ) AS rn FROM resume_versions WHERE is_current
        )
        UPDATE resume_versions SET is_current = false FROM ranked
        WHERE resume_versions.id = ranked.id AND ranked.rn > 1
    """)
    )
    op.create_index(
        "uq_resumes_user_default",
        "resumes",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.create_index(
        "uq_resume_versions_resume_current",
        "resume_versions",
        ["resume_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    op.add_column("jobs", sa.Column("dedupe_key", sa.String(length=64), nullable=True))
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, user_id, source_url, company_name, title, location FROM jobs ORDER BY created_at, id"
        )
    ).mappings()
    seen: set[tuple[object, str]] = set()
    for row in rows:
        key = _job_key(row["source_url"], row["company_name"], row["title"], row["location"])
        identity = (row["user_id"], key)
        if identity in seen:
            key = hashlib.sha256(f"{key}|legacy|{row['id']}".encode("utf-8")).hexdigest()
        seen.add(identity)
        connection.execute(
            sa.text("UPDATE jobs SET dedupe_key = :key WHERE id = :id"),
            {"key": key, "id": row["id"]},
        )
    op.create_unique_constraint("uq_jobs_user_dedupe", "jobs", ["user_id", "dedupe_key"])


def downgrade() -> None:
    op.drop_constraint("uq_jobs_user_dedupe", "jobs", type_="unique")
    op.drop_column("jobs", "dedupe_key")
    op.drop_index("uq_resume_versions_resume_current", table_name="resume_versions")
    op.drop_index("uq_resumes_user_default", table_name="resumes")
