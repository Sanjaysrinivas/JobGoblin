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
    application_readiness,
    fit_label,
    keyword_checklist,
    provider_metadata,
    readiness_steps,
    rewrite_suggestions,
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


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _has_snapshot(analysis: JobAnalysis) -> bool:
    """A grounded result must carry the metadata that reproduces its score."""
    return (
        analysis.model_used == ANALYSIS_VERSION and isinstance(analysis.score_breakdown, list)
    )


def _inputs_changed(session: Session, analysis: JobAnalysis) -> bool:
    """True when the job or resume content drifted from the analyzed inputs."""
    if not _has_snapshot(analysis) or analysis.job_text_hash is None:
        return False
    job = session.get(Job, analysis.job_id)
    resume = session.get(Resume, analysis.resume_id)
    if job is None or resume is None:
        return False
    current_job_hash = analysis_input_hash(job.title, job.description or "")
    resume_text, _ = current_resume_content(session, resume)
    current_resume_hash = analysis_input_hash(resume_text)
    resume_changed = (
        analysis.resume_text_hash is not None
        and current_resume_hash != analysis.resume_text_hash
    )
    return current_job_hash != analysis.job_text_hash or resume_changed


def analysis_response(session: Session, analysis: JobAnalysis) -> dict:
    job = session.get(Job, analysis.job_id)
    resume = session.get(Resume, analysis.resume_id)
    resume_text = ""
    parsed_resume = None
    if resume is not None:
        resume_text, parsed_resume = current_resume_content(session, resume)
    checklist = keyword_checklist(
        resume_text,
        parsed_resume,
        job.title if job else "",
        job.description if job else "",
    )
    # Serialize only what was stored at analysis time; never recompute policy
    # for a historical result (F2). Legacy rows have no persisted breakdown.
    score_breakdown = analysis.score_breakdown if _has_snapshot(analysis) else None
    missing = _string_list(analysis.missing_keywords)
    matched = _string_list(analysis.matched_keywords)
    return {
        **JobAnalysisOut.model_validate(analysis).model_dump(),
        "fit_label": fit_label(analysis.overall_score),
        "application_readiness": application_readiness(analysis.overall_score, missing),
        "readiness_steps": readiness_steps(analysis.overall_score, checklist),
        "keyword_checklist": checklist,
        "rewrite_suggestions": rewrite_suggestions(checklist, matched, missing),
        "score_breakdown": score_breakdown,
        "is_legacy": not _has_snapshot(analysis),
        "inputs_changed": _inputs_changed(session, analysis),
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
        job_text_hash=analysis_input_hash(job.title, job.description or ""),
        resume_version_id=version.id if version else None,
        resume_text_hash=analysis_input_hash(resume_text),
        provider=provider_name,
        model_used=model_used,
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis_response(session, analysis)


@router.get("/{analysis_id}", response_model=JobAnalysisOut)
def get_analysis(
    analysis_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return analysis_response(session, _get_owned_analysis(session, current_user, analysis_id))
