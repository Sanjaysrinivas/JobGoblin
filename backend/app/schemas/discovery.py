"""Schemas for job discovery preferences, runs, and results."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.models.enums import DiscoveryResultStatus, DiscoveryRunStatus, JobSource, WorkMode


class JobSearchPreferencesPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    target_countries: list[str] = Field(default_factory=list, max_length=20)
    target_locations: list[str] = Field(default_factory=list, max_length=50)
    desired_titles: list[str] = Field(default_factory=list, max_length=50)
    seniority: str | None = Field(default=None, max_length=120)
    industries: list[str] = Field(default_factory=list, max_length=50)
    required_keywords: list[str] = Field(default_factory=list, max_length=100)
    optional_keywords: list[str] = Field(default_factory=list, max_length=100)
    excluded_keywords: list[str] = Field(default_factory=list, max_length=100)
    visa_sponsorship_required: bool = False
    blocked_companies: list[str] = Field(default_factory=list, max_length=100)
    work_mode: WorkMode = WorkMode.unknown

    @field_validator(
        "target_countries",
        "target_locations",
        "desired_titles",
        "industries",
        "required_keywords",
        "optional_keywords",
        "excluded_keywords",
        "blocked_companies",
        mode="before",
    )
    @classmethod
    def _clean_list(cls, value, info: ValidationInfo):
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        cleaned = []
        seen = set()
        for item in value:
            if not isinstance(item, str):
                cleaned.append(item)
                continue
            text = item.strip()
            if info.field_name == "target_countries":
                text = text.lower()
                if len(text) != 2:
                    continue
            key = text.lower()
            if text and key not in seen:
                cleaned.append(text)
                seen.add(key)
        return cleaned


class JobSearchPreferencesOut(JobSearchPreferencesPayload):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobSearchRunCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    country: str | None = Field(default=None, min_length=2, max_length=2)
    location: str | None = Field(default=None, max_length=255)
    query: str | None = Field(default=None, max_length=500)
    provider: str | None = Field(default=None, max_length=80)
    results_per_page: int = Field(default=10, ge=1, le=25)

    @field_validator("country")
    @classmethod
    def _country_lower(cls, value: str | None) -> str | None:
        return value.lower() if value else value


class JobSearchRunOut(BaseModel):
    id: uuid.UUID
    provider: str
    status: DiscoveryRunStatus
    country: str
    location: str | None
    query: str
    preferences_snapshot: dict
    result_count: int
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobSearchResultOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    provider: str
    source: JobSource
    source_url: str | None
    title: str
    company_name: str
    location: str | None
    work_mode: WorkMode
    description: str
    posted_at: datetime | None
    fit_score: int
    fit_reason: str | None
    status: DiscoveryResultStatus
    saved_job_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobSearchResultUpdate(BaseModel):
    status: DiscoveryResultStatus
