"""Resume-to-job analysis endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import Job, JobAnalysis, Resume, User
from app.schemas.analysis import JobAnalysisOut, ResumeJobAnalysisCreate
from app.services.ai_provider import get_ai_provider
from app.services.job_analysis import analyze_resume_for_job, provider_metadata
from app.services.resume_context import current_resume_content

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _target_not_found() -> HTTPException:
    return _error(
        status.HTTP_404_NOT_FOUND,
        "Resume or job not found",
        "analysis_target_not_found",
    )


def _analysis_not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Analysis not found", "analysis_not_found")


def _get_owned_resume_and_job(
    session: Session,
    user: User,
    payload: ResumeJobAnalysisCreate,
) -> tuple[Resume, Job]:
    resume = session.exec(
        select(Resume).where(Resume.id == payload.resume_id, Resume.user_id == user.id)
    ).first()
    job = session.exec(
        select(Job).where(Job.id == payload.job_id, Job.user_id == user.id)
    ).first()
    if resume is None or job is None:
        raise _target_not_found()
    return resume, job


def _get_owned_analysis(session: Session, user: User, analysis_id: uuid.UUID) -> JobAnalysis:
    analysis = session.exec(
        select(JobAnalysis).where(JobAnalysis.id == analysis_id, JobAnalysis.user_id == user.id)
    ).first()
    if analysis is None:
        raise _analysis_not_found()
    return analysis


@router.post(
    "/resume-job",
    response_model=JobAnalysisOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_resume_job_analysis(
    payload: ResumeJobAnalysisCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JobAnalysis:
    resume, job = _get_owned_resume_and_job(session, current_user, payload)
    resume_text, parsed_resume = current_resume_content(session, resume)
    if not resume_text.strip() and not parsed_resume:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "Resume has no extracted text or parsed content to analyze.",
            "no_extracted_text",
        )

    provider = get_ai_provider()
    result = await analyze_resume_for_job(
        resume,
        job,
        provider,
        resume_text=resume_text,
        parsed_resume=parsed_resume,
    )
    provider_name, model_used = provider_metadata(provider)

    analysis = JobAnalysis(
        user_id=current_user.id,
        resume_id=resume.id,
        job_id=job.id,
        overall_score=result.overall_score,
        keyword_score=result.keyword_score,
        skills_score=result.skills_score,
        experience_score=result.experience_score,
        role_score=result.role_score,
        education_score=result.education_score,
        formatting_score=result.formatting_score,
        matched_keywords=result.matched_keywords,
        missing_keywords=result.missing_keywords,
        recommendations=result.recommendations,
        explanation=result.explanation,
        provider=provider_name,
        model_used=model_used,
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis


@router.get("/{analysis_id}", response_model=JobAnalysisOut)
def get_analysis(
    analysis_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JobAnalysis:
    return _get_owned_analysis(session, current_user, analysis_id)
