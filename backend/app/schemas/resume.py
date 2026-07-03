"""Request/response models for the resume endpoints (design.md section 4.2).

The ``ParsedResume`` shape mirrors ``frontend/lib/types.ts`` and the schema in
``app.services.resume_parser``.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ParsedExperience(BaseModel):
    company: str
    role: str
    start: str | None = None
    end: str | None = None
    highlights: list[str] = []


class ParsedEducation(BaseModel):
    institution: str
    credential: str
    year: str | None = None


class ParsedResume(BaseModel):
    summary: str | None = None
    skills: list[str] = []
    experience: list[ParsedExperience] = []
    education: list[ParsedEducation] = []
    projects: list[str] = []
    certifications: list[str] = []


class ResumeOut(BaseModel):
    id: uuid.UUID
    current_version_id: uuid.UUID | None = None
    current_version: "ResumeVersionOut | None"
    version_count: int
    title: str
    original_filename: str
    content_type: str
    file_size: int
    extracted_text: str | None = None
    parsed_json: dict | None = None
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class _OptionalTitle(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=255)


class ResumeUpdate(_OptionalTitle):
    """All fields optional; only provided ones are applied (PATCH semantics)."""

    extracted_text: str | None = Field(default=None, max_length=200_000)
    is_default: bool | None = None


class ResumeVersionOut(BaseModel):
    id: uuid.UUID
    resume_id: uuid.UUID
    job_id: uuid.UUID | None = None
    source_version_id: uuid.UUID | None = None
    title: str
    extracted_text: str | None = None
    parsed_json: dict | None = None
    is_current: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeVersionCreate(_OptionalTitle):
    source_version_id: uuid.UUID | None = None
    extracted_text: str | None = Field(default=None, max_length=200_000)
    parsed_json: dict | None = None


class ResumeVersionUpdate(_OptionalTitle):
    extracted_text: str | None = Field(default=None, max_length=200_000)
    parsed_json: dict | None = None


class TailoredResumeDraftCreate(_OptionalTitle):
    resume_id: uuid.UUID
    source_version_id: uuid.UUID | None = None
