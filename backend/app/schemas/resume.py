"""Request/response models for the resume endpoints (design.md §4.2).

The ``ParsedResume`` shape mirrors ``frontend/lib/types.ts`` and the schema in
``app.services.resume_parser``.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


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


class ResumeUpdate(BaseModel):
    """All fields optional — only provided ones are applied (PATCH semantics)."""

    title: str | None = None
    extracted_text: str | None = None
    is_default: bool | None = None
