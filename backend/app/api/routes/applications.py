"""Authenticated application tracking endpoints.

This module records workflow state only. It does not send mail, submit
applications, or perform any external action.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import ActivityEvent, Application, CoverLetter, Job, Resume, User
from app.models.enums import ApplicationStatus
from app.schemas.application import ApplicationCreate, ApplicationOut, ApplicationUpdate

router = APIRouter(prefix="/applications", tags=["applications"])


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _application_not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Application not found", "application_not_found")


def _get_owned_job(session: Session, user: User, job_id: uuid.UUID) -> Job:
    job = session.exec(select(Job).where(Job.id == job_id, Job.user_id == user.id)).first()
    if job is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Job not found", "job_not_found")
    return job


def _get_owned_application(
    session: Session, user: User, application_id: uuid.UUID
) -> tuple[Application, Job]:
    row = session.exec(
        select(Application, Job)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Application.user_id == user.id,
            Job.user_id == user.id,
        )
    ).first()
    if row is None:
        raise _application_not_found()
    application, job = row
    return application, job


def _validate_resume_reference(session: Session, user: User, resume_id: uuid.UUID | None) -> None:
    if resume_id is None:
        return
    resume = session.exec(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id)
    ).first()
    if resume is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Resume not found", "resume_not_found")


def _validate_cover_letter_reference(
    session: Session,
    user: User,
    cover_letter_id: uuid.UUID | None,
    job_id: uuid.UUID,
) -> None:
    if cover_letter_id is None:
        return
    cover_letter = session.exec(
        select(CoverLetter).where(
            CoverLetter.id == cover_letter_id,
            CoverLetter.user_id == user.id,
        )
    ).first()
    if cover_letter is None:
        raise _error(
            status.HTTP_404_NOT_FOUND,
            "Cover letter not found",
            "cover_letter_not_found",
        )
    if cover_letter.job_id != job_id:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Cover letter must belong to the application's job",
            "cover_letter_job_mismatch",
        )


def _serialize(application: Application, job: Job) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        job_id=application.job_id,
        resume_id=application.resume_id,
        cover_letter_id=application.cover_letter_id,
        status=application.status,
        applied_at=application.applied_at,
        follow_up_at=application.follow_up_at,
        notes=application.notes,
        created_at=application.created_at,
        updated_at=application.updated_at,
        job={
            "id": job.id,
            "company_name": job.company_name,
            "title": job.title,
            "location": job.location,
        },
    )


def _add_activity(
    session: Session,
    user: User,
    application: Application,
    event_type: str,
    description: str,
    metadata: dict | None = None,
) -> None:
    session.add(
        ActivityEvent(
            user_id=user.id,
            entity_type="application",
            entity_id=application.id,
            event_type=event_type,
            description=description,
            event_metadata=metadata,
        )
    )


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ApplicationOut]:
    rows = session.exec(
        select(Application, Job)
        .join(Job, Job.id == Application.job_id)
        .where(Application.user_id == current_user.id, Job.user_id == current_user.id)
        .order_by(Application.updated_at.desc())
    ).all()
    return [_serialize(application, job) for application, job in rows]


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> ApplicationOut:
    job = _get_owned_job(session, current_user, payload.job_id)
    _validate_resume_reference(session, current_user, payload.resume_id)
    _validate_cover_letter_reference(session, current_user, payload.cover_letter_id, payload.job_id)

    existing = session.exec(
        select(Application).where(
            Application.user_id == current_user.id,
            Application.job_id == payload.job_id,
        )
    ).first()
    if existing is not None:
        raise _error(
            status.HTTP_409_CONFLICT,
            "An application already exists for this job",
            "application_exists",
        )

    application = Application(user_id=current_user.id, **payload.model_dump())
    session.add(application)
    session.flush()
    _add_activity(
        session,
        current_user,
        application,
        "application_created",
        f"Started tracking {job.title} at {job.company_name}",
        {"status": application.status.value},
    )
    session.commit()
    session.refresh(application)
    return _serialize(application, job)


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(
    application_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> ApplicationOut:
    application, job = _get_owned_application(session, current_user, application_id)
    return _serialize(application, job)


@router.patch("/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: uuid.UUID,
    payload: ApplicationUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> ApplicationOut:
    application, job = _get_owned_application(session, current_user, application_id)
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("status") is None and "status" in updates:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Status cannot be null",
            "invalid_application_status",
        )

    _validate_resume_reference(session, current_user, updates.get("resume_id"))
    _validate_cover_letter_reference(
        session, current_user, updates.get("cover_letter_id"), application.job_id
    )

    old_status: ApplicationStatus = application.status
    for field, value in updates.items():
        setattr(application, field, value)

    if "status" in updates and application.status != old_status:
        _add_activity(
            session,
            current_user,
            application,
            "application_status_changed",
            f"Moved {job.title} at {job.company_name} to {application.status.value}",
            {"from": old_status.value, "to": application.status.value},
        )

    session.add(application)
    session.commit()
    session.refresh(application)
    return _serialize(application, job)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    application, _job = _get_owned_application(session, current_user, application_id)
    session.delete(application)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
