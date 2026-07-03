"""Authenticated CRUD endpoints for jobs.

All reads and writes are scoped to the current user. Cross-user access returns
404 so job existence is not leaked.
"""

import copy
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import Job, JobAnalysis, Resume, ResumeVersion, User
from app.schemas.analysis import JobAnalysisOut
from app.schemas.job import JobCreate, JobOut, JobUpdate
from app.schemas.resume import ResumeVersionOut, TailoredResumeDraftCreate

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Job not found", "job_not_found")


def _get_owned_job(session: Session, user: User, job_id: uuid.UUID) -> Job:
    job = session.exec(select(Job).where(Job.id == job_id, Job.user_id == user.id)).first()
    if job is None:
        raise _not_found()
    return job


def _resume_not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Resume not found", "resume_not_found")


def _version_not_found() -> HTTPException:
    return _error(
        status.HTTP_404_NOT_FOUND,
        "Resume version not found",
        "resume_version_not_found",
    )


def _get_owned_resume(session: Session, user: User, resume_id: uuid.UUID) -> Resume:
    resume = session.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise _resume_not_found()
    return resume


def _get_source_version(
    session: Session,
    resume: Resume,
    source_version_id: uuid.UUID | None,
) -> ResumeVersion | None:
    if source_version_id is not None:
        version = session.get(ResumeVersion, source_version_id)
        if version is None or version.resume_id != resume.id:
            raise _version_not_found()
        return version
    return session.exec(
        select(ResumeVersion)
        .where(
            ResumeVersion.resume_id == resume.id,
            ResumeVersion.is_current == True,  # noqa: E712 - SQLAlchemy expression
        )
        .order_by(ResumeVersion.updated_at.desc())
    ).first()


def _validate_salary_range(salary_min: int | None, salary_max: int | None) -> None:
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "salary_min must be less than or equal to salary_max",
            "invalid_salary_range",
        )


@router.get("", response_model=list[JobOut])
def list_jobs(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[Job]:
    return list(
        session.exec(
            select(Job).where(Job.user_id == current_user.id).order_by(Job.created_at.desc())
        ).all()
    )


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Job:
    _validate_salary_range(payload.salary_min, payload.salary_max)
    job = Job(user_id=current_user.id, **payload.model_dump())
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.post(
    "/{job_id}/resume-drafts",
    response_model=ResumeVersionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_resume_draft(
    job_id: uuid.UUID,
    payload: TailoredResumeDraftCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> ResumeVersion:
    job = _get_owned_job(session, current_user, job_id)
    resume = _get_owned_resume(session, current_user, payload.resume_id)
    source = _get_source_version(session, resume, payload.source_version_id)
    source_title = source.title if source else resume.title
    source_text = source.extracted_text if source else resume.extracted_text
    source_json = copy.deepcopy(source.parsed_json if source else resume.parsed_json) or {}
    source_json["tailored_for"] = {
        "job_id": str(job.id),
        "title": job.title,
        "company_name": job.company_name,
    }
    draft = ResumeVersion(
        resume_id=resume.id,
        job_id=job.id,
        source_version_id=source.id if source else None,
        title=payload.title or f"{source_title} - {job.company_name} {job.title}",
        extracted_text=(source_text or "")
        + f"\n\nTailored focus: {job.title} at {job.company_name}.",
        parsed_json=source_json,
        is_current=False,
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft


@router.get("/{job_id}/resume-drafts", response_model=list[ResumeVersionOut])
def list_resume_drafts(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ResumeVersion]:
    job = _get_owned_job(session, current_user, job_id)
    return list(
        session.exec(
            select(ResumeVersion)
            .join(Resume, Resume.id == ResumeVersion.resume_id)
            .where(
                Resume.user_id == current_user.id,
                ResumeVersion.job_id == job.id,
            )
            .order_by(ResumeVersion.updated_at.desc())
        ).all()
    )


@router.get("/{job_id}/analysis", response_model=list[JobAnalysisOut])
def list_job_analyses(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[JobAnalysis]:
    _get_owned_job(session, current_user, job_id)
    return list(
        session.exec(
            select(JobAnalysis)
            .where(JobAnalysis.job_id == job_id, JobAnalysis.user_id == current_user.id)
            .order_by(JobAnalysis.created_at.desc())
        ).all()
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Job:
    return _get_owned_job(session, current_user, job_id)


@router.patch("/{job_id}", response_model=JobOut)
def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Job:
    job = _get_owned_job(session, current_user, job_id)
    updates = payload.model_dump(exclude_unset=True)
    _validate_salary_range(
        updates.get("salary_min", job.salary_min),
        updates.get("salary_max", job.salary_max),
    )
    for field, value in updates.items():
        setattr(job, field, value)

    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    job = _get_owned_job(session, current_user, job_id)
    session.delete(job)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
