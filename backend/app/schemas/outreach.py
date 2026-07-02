import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import OutreachChannel, OutreachStatus


class OutreachBase(BaseModel):
    job_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    channel: OutreachChannel = OutreachChannel.email
    message_type: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=10000)
    status: OutreachStatus = OutreachStatus.draft

    @field_validator("message_type", "content", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("message_type", "content")
    @classmethod
    def reject_blank_strings(cls, value: str) -> str:
        if not value:
            raise ValueError("Value cannot be blank")
        return value


class OutreachCreate(OutreachBase):
    pass


class OutreachUpdate(BaseModel):
    job_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    channel: OutreachChannel | None = None
    message_type: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    status: OutreachStatus | None = None

    @field_validator("message_type", "content", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("message_type", "content")
    @classmethod
    def reject_blank_strings(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Value cannot be null")
        if not value:
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("channel")
    @classmethod
    def reject_null_channel(cls, value: OutreachChannel | None) -> OutreachChannel | None:
        if value is None:
            raise ValueError("Channel cannot be null")
        return value

    @field_validator("status")
    @classmethod
    def reject_null_status(cls, value: OutreachStatus | None) -> OutreachStatus | None:
        if value is None:
            raise ValueError("Status cannot be null")
        return value


class OutreachJobOut(BaseModel):
    id: uuid.UUID
    company_name: str
    title: str
    location: str | None = None


class OutreachContactOut(BaseModel):
    id: uuid.UUID
    name: str
    company: str | None = None
    role: str | None = None
    email: str | None = None
    linkedin_url: str | None = None


class OutreachOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    channel: OutreachChannel
    message_type: str
    content: str
    status: OutreachStatus
    created_at: datetime
    updated_at: datetime
    job: OutreachJobOut | None = None
    contact: OutreachContactOut | None = None

    model_config = {"from_attributes": True}