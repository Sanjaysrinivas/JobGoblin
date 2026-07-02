"""Schemas for the private user profile builder."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProfileExperience(BaseModel):
    company: str = ""
    role: str = ""
    start: str | None = None
    end: str | None = None
    highlights: list[str] = Field(default_factory=list)


class ProfileEducation(BaseModel):
    institution: str = ""
    credential: str = ""
    year: str | None = None


class ProfileBase(BaseModel):
    full_name: str | None = None
    headline: str | None = None
    location: str | None = None
    website_url: str | None = None
    linkedin_url: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ProfileExperience] = Field(default_factory=list)
    education: list[ProfileEducation] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class ProfileUpdate(ProfileBase):
    """Full profile replacement used by the builder save action."""


class ProfileSeedRequest(BaseModel):
    resume_id: uuid.UUID


class ProfileOut(ProfileBase):
    id: uuid.UUID
    source_resume_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}