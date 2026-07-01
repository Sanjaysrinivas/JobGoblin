import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import JobSource, Priority, WorkMode


class JobBase(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    work_mode: WorkMode = WorkMode.unknown
    source: JobSource = JobSource.other
    source_url: str | None = Field(default=None, max_length=2048)
    description: str = Field(min_length=1)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    priority: Priority = Priority.medium

    @field_validator(
        "company_name",
        "title",
        "location",
        "source_url",
        "description",
        "currency",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("company_name", "title", "description")
    @classmethod
    def reject_blank_required_strings(cls, value: str) -> str:
        if not value:
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    work_mode: WorkMode | None = None
    source: JobSource | None = None
    source_url: str | None = Field(default=None, max_length=2048)
    description: str | None = Field(default=None, min_length=1)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    priority: Priority | None = None

    @field_validator(
        "company_name",
        "title",
        "location",
        "source_url",
        "description",
        "currency",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("company_name", "title", "description")
    @classmethod
    def reject_blank_required_strings(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class JobOut(BaseModel):
    id: uuid.UUID
    company_name: str
    title: str
    location: str | None = None
    work_mode: WorkMode
    source: JobSource
    source_url: str | None = None
    description: str
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    priority: Priority
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
