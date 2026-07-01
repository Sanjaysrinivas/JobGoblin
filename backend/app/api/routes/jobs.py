"""Authenticated CRUD endpoints for jobs.

All reads and writes are scoped to the current user. Cross-user access returns
404 so job existence is not leaked.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import Job, User
from app.schemas.job import JobCreate, JobOut, JobUpdate

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Job not found", "job_not_found")


def _get_owned_job(session: Session, user: User, job_id: uuid.UUID) -> Job:
    job = session.exec(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    ).first()
    if job is None:
        raise _not_found()
    return job


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
            select(Job)
            .where(Job.user_id == current_user.id)
            .order_by(Job.created_at.desc())
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
