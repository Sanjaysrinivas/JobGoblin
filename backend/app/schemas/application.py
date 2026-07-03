import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ApplicationStatus
from app.schemas.contact import ContactOut
from app.schemas.cover_letter import CoverLetterOut
from app.schemas.job import JobOut
from app.schemas.outreach import OutreachOut


class ApplicationBase(BaseModel):
    resume_id: uuid.UUID | None = None
    cover_letter_id: uuid.UUID | None = None
    status: ApplicationStatus = ApplicationStatus.saved
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class ApplicationCreate(ApplicationBase):
    job_id: uuid.UUID


class ApplicationUpdate(BaseModel):
    resume_id: uuid.UUID | None = None
    cover_letter_id: uuid.UUID | None = None
    status: ApplicationStatus | None = None
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class ApplicationJobOut(BaseModel):
    id: uuid.UUID
    company_name: str
    title: str
    location: str | None = None


class ApplicationFollowUpActivityOut(BaseModel):
    event_type: str
    description: str | None = None
    created_at: datetime


class ApplicationOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    resume_id: uuid.UUID | None = None
    cover_letter_id: uuid.UUID | None = None
    status: ApplicationStatus
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    job: ApplicationJobOut

    model_config = {"from_attributes": True}


class ApplicationFollowUpOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    status: ApplicationStatus
    follow_up_at: datetime
    notes: str | None = None
    updated_at: datetime
    due: bool
    job: ApplicationJobOut
    latest_activity: ApplicationFollowUpActivityOut | None = None


class ApplicationWorkflowResumeVersionOut(BaseModel):
    id: uuid.UUID
    title: str
    source_version_id: uuid.UUID | None = None
    updated_at: datetime


class ApplicationWorkflowResumeOut(BaseModel):
    id: uuid.UUID
    title: str
    current_version_id: uuid.UUID | None = None
    current_version_title: str | None = None
    tailored_draft: ApplicationWorkflowResumeVersionOut | None = None


class ApplicationWorkflowActivityOut(BaseModel):
    entity_type: str
    entity_id: uuid.UUID
    event_type: str
    description: str | None = None
    created_at: datetime


class ApplicationWorkflowNextActionOut(BaseModel):
    label: str
    due_at: datetime | None = None
    due: bool = False


class ApplicationWorkflowOut(BaseModel):
    application: ApplicationOut
    job: JobOut
    next_action: ApplicationWorkflowNextActionOut
    linked_resume: ApplicationWorkflowResumeOut | None = None
    linked_cover_letter: CoverLetterOut | None = None
    cover_letters: list[CoverLetterOut]
    contacts: list[ContactOut]
    outreach_drafts: list[OutreachOut]
    recent_activity: list[ApplicationWorkflowActivityOut]
