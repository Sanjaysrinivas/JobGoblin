"""Schemas for the private user profile builder."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

ShortText = Annotated[str, Field(min_length=1, max_length=255)]
LongText = Annotated[str, Field(min_length=1, max_length=1000)]


class ProfileExperience(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company: str = Field(default="", max_length=255)
    role: str = Field(default="", max_length=255)
    start: str | None = Field(default=None, max_length=64)
    end: str | None = Field(default=None, max_length=64)
    highlights: list[LongText] = Field(default_factory=list, max_length=20)


class ProfileEducation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    institution: str = Field(default="", max_length=255)
    credential: str = Field(default="", max_length=255)
    year: str | None = Field(default=None, max_length=64)


class ProfileBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = Field(default=None, max_length=255)
    headline: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    website_url: str | None = Field(default=None, max_length=2048)
    linkedin_url: str | None = Field(default=None, max_length=2048)
    summary: str | None = Field(default=None, max_length=5000)
    skills: list[ShortText] = Field(default_factory=list, max_length=100)
    experience: list[ProfileExperience] = Field(default_factory=list, max_length=50)
    education: list[ProfileEducation] = Field(default_factory=list, max_length=50)
    projects: list[ShortText] = Field(default_factory=list, max_length=50)
    certifications: list[ShortText] = Field(default_factory=list, max_length=50)


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
