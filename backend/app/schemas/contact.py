import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ContactBase(BaseModel):
    job_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    linkedin_url: str | None = Field(default=None, max_length=2048)
    notes: str | None = None
    contacted: bool = False

    @field_validator("name", "company", "role", "email", "linkedin_url", "notes", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("company", "role", "email", "linkedin_url", "notes")
    @classmethod
    def empty_optional_strings_to_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if not value:
            raise ValueError("Value cannot be blank")
        return value


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    job_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    linkedin_url: str | None = Field(default=None, max_length=2048)
    notes: str | None = None
    contacted: bool | None = None

    @field_validator("name", "company", "role", "email", "linkedin_url", "notes", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("company", "role", "email", "linkedin_url", "notes")
    @classmethod
    def empty_optional_strings_to_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("Value cannot be blank")
        return value


class ContactOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID | None = None
    name: str
    company: str | None = None
    role: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    notes: str | None = None
    contacted: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
