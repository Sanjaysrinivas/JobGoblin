import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.enums import (
    ApplicationStatus,
    CoverLetterStatus,
    CoverLetterTone,
    JobSource,
    OutreachChannel,
    OutreachStatus,
    Priority,
    WorkMode,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _enum(enum_cls: type) -> SAEnum:
    """Enum stored as VARCHAR + CHECK (native_enum=False) — keeps create_all /
    migrations idempotent and avoids managing PostgreSQL ENUM types."""
    return SAEnum(enum_cls, native_enum=False, length=40)


# Timestamps are stored WITH TIME ZONE to match the tz-aware UTC values produced
# by _utcnow(); naive columns would silently drop the offset.
class _UUIDMixin(SQLModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class _TimeMixin(SQLModel):
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True), nullable=False
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"onupdate": _utcnow},
        nullable=False,
    )


class User(_UUIDMixin, _TimeMixin, table=True):
    __tablename__ = "users"

    email: str = Field(unique=True, index=True)
    password_hash: str
    display_name: str
    is_admin: bool = Field(default=False)


class InviteToken(_UUIDMixin, table=True):
    __tablename__ = "invite_tokens"

    token: str = Field(unique=True, index=True)
    created_by: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    used_by: uuid.UUID | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True), nullable=False
    )


class Resume(_UUIDMixin, _TimeMixin, table=True):
    __tablename__ = "resumes"

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    title: str
    original_filename: str
    file_key: str
    content_type: str
    file_size: int
    extracted_text: str | None = None
    parsed_json: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    is_default: bool = Field(default=False)


class Job(_UUIDMixin, _TimeMixin, table=True):
    __tablename__ = "jobs"

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    company_name: str
    title: str
    location: str | None = None
    work_mode: WorkMode = Field(default=WorkMode.unknown, sa_type=_enum(WorkMode))
    source: JobSource = Field(default=JobSource.other, sa_type=_enum(JobSource))
    source_url: str | None = None
    description: str
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    priority: Priority = Field(default=Priority.medium, sa_type=_enum(Priority))


class JobAnalysis(_UUIDMixin, table=True):
    __tablename__ = "job_analyses"

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    resume_id: uuid.UUID = Field(foreign_key="resumes.id", ondelete="CASCADE")
    job_id: uuid.UUID = Field(foreign_key="jobs.id", ondelete="CASCADE")
    overall_score: int
    keyword_score: int
    skills_score: int
    experience_score: int
    role_score: int
    education_score: int
    formatting_score: int
    matched_keywords: list | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    missing_keywords: list | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    recommendations: list | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    explanation: str | None = None
    provider: str
    model_used: str
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True), nullable=False
    )


class CoverLetter(_UUIDMixin, _TimeMixin, table=True):
    __tablename__ = "cover_letters"

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    job_id: uuid.UUID = Field(foreign_key="jobs.id", ondelete="CASCADE")
    resume_id: uuid.UUID = Field(foreign_key="resumes.id", ondelete="CASCADE")
    content: str
    tone: CoverLetterTone = Field(sa_type=_enum(CoverLetterTone))
    status: CoverLetterStatus = Field(
        default=CoverLetterStatus.draft, sa_type=_enum(CoverLetterStatus)
    )


class Application(_UUIDMixin, _TimeMixin, table=True):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_application_user_job"),)

    # No standalone index on user_id: the (user_id, job_id) unique index above
    # already serves user_id-prefixed queries.
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    job_id: uuid.UUID = Field(foreign_key="jobs.id", ondelete="CASCADE")
    resume_id: uuid.UUID | None = Field(default=None, foreign_key="resumes.id", ondelete="SET NULL")
    cover_letter_id: uuid.UUID | None = Field(
        default=None, foreign_key="cover_letters.id", ondelete="SET NULL"
    )
    status: ApplicationStatus = Field(
        default=ApplicationStatus.saved, sa_type=_enum(ApplicationStatus)
    )
    applied_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    follow_up_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    notes: str | None = None


class Contact(_UUIDMixin, _TimeMixin, table=True):
    __tablename__ = "contacts"

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    job_id: uuid.UUID | None = Field(default=None, foreign_key="jobs.id", ondelete="SET NULL")
    name: str
    company: str | None = None
    role: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    notes: str | None = None
    contacted: bool = Field(default=False)


class OutreachMessage(_UUIDMixin, _TimeMixin, table=True):
    __tablename__ = "outreach_messages"

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    job_id: uuid.UUID | None = Field(default=None, foreign_key="jobs.id", ondelete="SET NULL")
    contact_id: uuid.UUID | None = Field(
        default=None, foreign_key="contacts.id", ondelete="SET NULL"
    )
    channel: OutreachChannel = Field(sa_type=_enum(OutreachChannel))
    message_type: str
    content: str
    status: OutreachStatus = Field(default=OutreachStatus.draft, sa_type=_enum(OutreachStatus))


class ActivityEvent(_UUIDMixin, table=True):
    __tablename__ = "activity_events"
    __table_args__ = (Index("ix_activity_events_entity", "entity_type", "entity_id"),)

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    entity_type: str
    entity_id: uuid.UUID
    event_type: str
    description: str | None = None
    # 'metadata' is reserved on SQLModel/SQLAlchemy classes, so map a differently
    # named attribute onto the 'metadata' column.
    event_metadata: dict | None = Field(
        default=None, sa_column=Column("metadata", JSONB, nullable=True)
    )
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True), nullable=False
    )
