import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import CoverLetterStatus, CoverLetterTone


class CoverLetterCreate(BaseModel):
    job_id: uuid.UUID
    resume_id: uuid.UUID
    tone: CoverLetterTone = CoverLetterTone.professional


class CoverLetterUpdate(BaseModel):
    content: str | None = Field(default=None, max_length=20000)
    tone: CoverLetterTone | None = None
    status: CoverLetterStatus | None = None

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class CoverLetterOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    resume_id: uuid.UUID
    tone: CoverLetterTone
    content: str
    status: CoverLetterStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
