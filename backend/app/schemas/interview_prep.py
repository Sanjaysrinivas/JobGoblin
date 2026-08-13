import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import InterviewPrepStatus


class InterviewPrepQuestion(BaseModel):
    question: str = Field(min_length=1)
    category: str = Field(min_length=1)
    why: str = Field(min_length=1)
    answer_outline: str = Field(min_length=1)
    evidence: list[str] = []


class InterviewPrepCreate(BaseModel):
    job_id: uuid.UUID
    application_id: uuid.UUID | None = None
    resume_id: uuid.UUID | None = None
    resume_version_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class InterviewPrepUpdate(BaseModel):
    status: InterviewPrepStatus | None = None
    notes: str | None = Field(default=None, max_length=10000)
    questions: list[InterviewPrepQuestion] | None = None

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("status")
    @classmethod
    def reject_null_status(cls, value: InterviewPrepStatus | None) -> InterviewPrepStatus | None:
        if value is None:
            raise ValueError("Status cannot be null")
        return value

    @field_validator("questions")
    @classmethod
    def reject_null_questions(
        cls, value: list[InterviewPrepQuestion] | None
    ) -> list[InterviewPrepQuestion] | None:
        if value is None:
            raise ValueError("Questions cannot be null")
        return value


class InterviewPrepOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    application_id: uuid.UUID | None = None
    resume_id: uuid.UUID | None = None
    resume_version_id: uuid.UUID | None = None
    status: InterviewPrepStatus
    questions: list[InterviewPrepQuestion]
    notes: str | None = None
    provider: str
    model_used: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
