import uuid
from datetime import datetime

from pydantic import BaseModel


class ResumeJobAnalysisCreate(BaseModel):
    resume_id: uuid.UUID
    job_id: uuid.UUID


class JobAnalysisOut(BaseModel):
    id: uuid.UUID
    resume_id: uuid.UUID
    job_id: uuid.UUID
    overall_score: int
    keyword_score: int
    skills_score: int
    experience_score: int
    role_score: int
    education_score: int
    formatting_score: int
    matched_keywords: list[str] | None = None
    missing_keywords: list[str] | None = None
    recommendations: list[str] | None = None
    explanation: str | None = None
    provider: str
    model_used: str
    created_at: datetime

    model_config = {"from_attributes": True}
