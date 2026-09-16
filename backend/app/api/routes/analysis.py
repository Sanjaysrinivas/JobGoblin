"""Resume-to-job analysis endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import Job, JobAnalysis, Resume, User
from app.schemas.analysis import JobAnalysisOut, ResumeJobAnalysisCreate
from app.services.job_analysis import (
    ANALYSIS_VERSION,
    analysis_input_hash,
    analyze_resume_for_job,
    provider_metadata,
    resume_evidence_hash,
)
from app.services.resume_context import current_resume_content, current_resume_version

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


def _has_snapshot(analysis: JobAnalysis) -> bool:
    """A grounded result must carry the metadata that reproduces its score."""
    return (
        analysis.model_used == ANALYSIS_VERSION
        and isinstance(analysis.score_breakdown, list)
        and isinstance(analysis.guidance_snapshot, dict)
        and analysis.job_text_hash is not None
        and analysis.resume_evidence_hash is not None
    )


def _inputs_changed(session: Session, analysis: JobAnalysis, user_id: uuid.UUID) -> bool:
    """True when the job or resume content drifted from the analyzed inputs."""
    if not _has_snapshot(analysis):
        return False
    job = session.exec(
        select(Job).where(Job.id == analysis.job_id, Job.user_id == user_id)
    ).first()
    resume = session.exec(
        select(Resume).where(Resume.id == analysis.resume_id, Resume.user_id == user_id)
    ).first()
    if job is None or resume is None:
        return False
    current_job_hash = analysis_input_hash(job.title, job.description or "")
    resume_text, parsed_resume = current_resume_content(session, resume)
    current_resume_hash = resume_evidence_hash(resume_text, parsed_resume)
    version = current_resume_version(session, resume)
    current_version_id = version.id if version is not None else None
    version_changed = current_version_id != analysis.resume_version_id
    resume_changed = current_resume_hash != analysis.resume_evidence_hash or version_changed
    return current_job_hash != analysis.job_text_hash or resume_changed


def analysis_response(session: Session, analysis: JobAnalysis, user_id: uuid.UUID) -> dict:
    has_snapshot = _has_snapshot(analysis)
    guidance = analysis.guidance_snapshot if has_snapshot else {}
    return {
        **JobAnalysisOut.model_validate(analysis).model_dump(),
        "fit_label": guidance.get("fit_label"),
        "application_readiness": guidance.get("application_readiness"),
        "readiness_steps": guidance.get("readiness_steps"),
        "keyword_checklist": guidance.get("keyword_checklist"),
        "rewrite_suggestions": guidance.get("rewrite_suggestions"),
        "score_breakdown": analysis.score_breakdown if has_snapshot else None,
        "is_legacy": not has_snapshot,
        "inputs_changed": _inputs_changed(session, analysis, user_id),
    }


@router.post(
    "/resume-job",
    response_model=JobAnalysisOut,
    status_code=status.HTTP_201_CREATED,
)
def create_resume_job_analysis(
    payload: ResumeJobAnalysisCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    resume, job = _get_owned_resume_and_job(session, current_user, payload)
    version = current_resume_version(session, resume)
    resume_text, parsed_resume = current_resume_content(session, resume)
    if not resume_text.strip() and not parsed_resume:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "Resume has no extracted text or parsed content to analyze.",
            "no_extracted_text",
        )

    result = analyze_resume_for_job(
        resume,
        job,
        resume_text=resume_text,
        parsed_resume=parsed_resume,
    )
    provider_name, model_used = provider_metadata()

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
        score_breakdown=result.score_breakdown,
        guidance_snapshot=result.guidance_snapshot,
        job_text_hash=analysis_input_hash(job.title, job.description or ""),
        resume_version_id=version.id if version else None,
        resume_text_hash=analysis_input_hash(resume_text),
        resume_evidence_hash=resume_evidence_hash(resume_text, parsed_resume),
        provider=provider_name,
        model_used=model_used,
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis_response(session, analysis, current_user.id)


@router.get("/{analysis_id}", response_model=JobAnalysisOut)
def get_analysis(
    analysis_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return analysis_response(
        session,
        _get_owned_analysis(session, current_user, analysis_id),
        current_user.id,
    )
