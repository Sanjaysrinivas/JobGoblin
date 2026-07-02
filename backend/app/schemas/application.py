import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ApplicationStatus


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
