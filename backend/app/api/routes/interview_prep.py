import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import (
    ActivityEvent,
    Application,
    InterviewPrep,
    Job,
    Profile,
    Resume,
    ResumeVersion,
    User,
)
from app.models.enums import InterviewPrepStatus
from app.schemas.interview_prep import InterviewPrepCreate, InterviewPrepOut, InterviewPrepUpdate
from app.services.interview_prep import generate_interview_questions

router = APIRouter(prefix="/interview-prep", tags=["interview-prep"])


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _prep_not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Interview prep not found", "interview_prep_not_found")


def _get_owned_job(session: Session, user: User, job_id: uuid.UUID) -> Job:
    job = session.exec(select(Job).where(Job.id == job_id, Job.user_id == user.id)).first()
    if job is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Job not found", "job_not_found")
    return job


def _get_owned_application(
    session: Session,
    user: User,
    application_id: uuid.UUID | None,
) -> Application | None:
    if application_id is None:
        return None
    application = session.exec(
        select(Application).where(Application.id == application_id, Application.user_id == user.id)
    ).first()
    if application is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Application not found", "application_not_found")
    return application


def _get_owned_resume(session: Session, user: User, resume_id: uuid.UUID | None) -> Resume | None:
    if resume_id is None:
        return None
    resume = session.exec(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id)
    ).first()
    if resume is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Resume not found", "resume_not_found")
    return resume


def _get_owned_version(
    session: Session,
    user: User,
    resume: Resume | None,
    version_id: uuid.UUID | None,
) -> tuple[Resume | None, ResumeVersion | None]:
    if version_id is None:
        return resume, None
    row = session.exec(
        select(ResumeVersion, Resume)
        .join(Resume, Resume.id == ResumeVersion.resume_id)
        .where(ResumeVersion.id == version_id, Resume.user_id == user.id)
    ).first()
    if row is None:
        raise _error(
            status.HTTP_404_NOT_FOUND,
            "Resume version not found",
            "resume_version_not_found",
        )
    version, version_resume = row
    if resume is not None and version.resume_id != resume.id:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Resume version must belong to the selected resume",
            "resume_version_mismatch",
        )
    return version_resume, version


def _get_owned_prep(session: Session, user: User, prep_id: uuid.UUID) -> InterviewPrep:
    prep = session.exec(
        select(InterviewPrep).where(InterviewPrep.id == prep_id, InterviewPrep.user_id == user.id)
    ).first()
    if prep is None:
        raise _prep_not_found()
    return prep


def _add_activity(
    session: Session,
    user: User,
    prep: InterviewPrep,
    event_type: str,
    description: str,
    metadata: dict | None = None,
) -> None:
    session.add(
        ActivityEvent(
            user_id=user.id,
            entity_type="interview_prep",
            entity_id=prep.id,
            event_type=event_type,
            description=description,
            event_metadata=metadata,
        )
    )


@router.get("", response_model=list[InterviewPrepOut])
def list_interview_preps(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    job_id: Annotated[uuid.UUID | None, Query()] = None,
    application_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[InterviewPrep]:
    if job_id is not None:
        _get_owned_job(session, current_user, job_id)
    if application_id is not None:
        _get_owned_application(session, current_user, application_id)

    query = select(InterviewPrep).where(InterviewPrep.user_id == current_user.id)
    if job_id is not None:
        query = query.where(InterviewPrep.job_id == job_id)
    if application_id is not None:
        query = query.where(InterviewPrep.application_id == application_id)
    return list(session.exec(query.order_by(InterviewPrep.updated_at.desc())).all())


@router.post("", response_model=InterviewPrepOut, status_code=status.HTTP_201_CREATED)
def create_interview_prep(
    payload: InterviewPrepCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> InterviewPrep:
    job = _get_owned_job(session, current_user, payload.job_id)
    application = _get_owned_application(session, current_user, payload.application_id)
    if application is not None and application.job_id != job.id:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Application must belong to the selected job",
            "application_job_mismatch",
        )
    resume = _get_owned_resume(
        session, current_user, payload.resume_id or (application.resume_id if application else None)
    )
    resume, version = _get_owned_version(session, current_user, resume, payload.resume_version_id)
    profile = session.exec(select(Profile).where(Profile.user_id == current_user.id)).first()
    prep = InterviewPrep(
        user_id=current_user.id,
        job_id=job.id,
        application_id=application.id if application else None,
        resume_id=resume.id if resume else None,
        resume_version_id=version.id if version else None,
        questions=generate_interview_questions(
            job,
            resume,
            version,
            profile,
            application.notes if application else None,
            payload.notes,
        ),
        notes=payload.notes,
        provider="mock",
        model_used="deterministic",
    )
    session.add(prep)
    session.flush()
    _add_activity(
        session,
        current_user,
        prep,
        "interview_prep_created",
        f"Created interview prep for {job.title} at {job.company_name}",
        {"status": prep.status.value},
    )
    session.commit()
    session.refresh(prep)
    return prep


@router.get("/{prep_id}", response_model=InterviewPrepOut)
def get_interview_prep(
    prep_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> InterviewPrep:
    return _get_owned_prep(session, current_user, prep_id)


@router.patch("/{prep_id}", response_model=InterviewPrepOut)
def update_interview_prep(
    prep_id: uuid.UUID,
    payload: InterviewPrepUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> InterviewPrep:
    prep = _get_owned_prep(session, current_user, prep_id)
    updates = payload.model_dump(exclude_unset=True)
    old_status: InterviewPrepStatus = prep.status
    old_notes = prep.notes
    if "questions" in updates and updates["questions"] is not None:
        updates["questions"] = [question.model_dump() for question in payload.questions or []]
    for field, value in updates.items():
        setattr(prep, field, value)
    if "status" in updates and prep.status != old_status:
        _add_activity(
            session,
            current_user,
            prep,
            "interview_prep_status_changed",
            f"Moved interview prep to {prep.status.value}",
            {"from": old_status.value, "to": prep.status.value},
        )
    if "notes" in updates and prep.notes != old_notes:
        _add_activity(
            session,
            current_user,
            prep,
            "interview_prep_notes_updated",
            "Updated interview prep notes",
        )
    session.add(prep)
    session.commit()
    session.refresh(prep)
    return prep
