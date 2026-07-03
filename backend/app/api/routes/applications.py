"""Authenticated application tracking endpoints.

This module records workflow state only. It does not send mail, submit
applications, or perform any external action.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import text
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import (
    ActivityEvent,
    Application,
    Contact,
    CoverLetter,
    Job,
    OutreachMessage,
    Resume,
    ResumeVersion,
    User,
)
from app.models.enums import ApplicationStatus
from app.schemas.application import (
    ApplicationCreate,
    ApplicationFollowUpActivityOut,
    ApplicationFollowUpOut,
    ApplicationOut,
    ApplicationUpdate,
    ApplicationWorkflowActivityOut,
    ApplicationWorkflowNextActionOut,
    ApplicationWorkflowOut,
    ApplicationWorkflowResumeOut,
    ApplicationWorkflowResumeVersionOut,
)

router = APIRouter(prefix="/applications", tags=["applications"])

_TERMINAL_STATUSES = (
    ApplicationStatus.offer,
    ApplicationStatus.rejected,
    ApplicationStatus.withdrawn,
    ApplicationStatus.archived,
)


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _application_not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Application not found", "application_not_found")


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _datetime_changed(left: datetime | None, right: datetime | None) -> bool:
    return _as_utc(left) != _as_utc(right)


def _datetime_metadata(value: datetime | None) -> str | None:
    normalized = _as_utc(value)
    return normalized.isoformat() if normalized is not None else None


def _normalize_application_datetimes(data: dict) -> dict:
    for field in ("applied_at", "follow_up_at"):
        if field in data:
            data[field] = _as_utc(data[field])
    return data


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


def _workflow_resume(
    session: Session,
    user: User,
    resume_id: uuid.UUID | None,
    job_id: uuid.UUID,
) -> ApplicationWorkflowResumeOut | None:
    if resume_id is None:
        return None
    resume = session.exec(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id)
    ).first()
    if resume is None:
        return None
    current_query = select(ResumeVersion).where(ResumeVersion.resume_id == resume.id)
    current = session.exec(
        current_query.order_by(ResumeVersion.is_current.desc(), ResumeVersion.updated_at.desc())
    ).first()
    tailored_draft = session.exec(
        select(ResumeVersion)
        .where(ResumeVersion.resume_id == resume.id, ResumeVersion.job_id == job_id)
        .order_by(ResumeVersion.updated_at.desc())
    ).first()
    return ApplicationWorkflowResumeOut(
        id=resume.id,
        title=current.title if current else resume.title,
        current_version_id=current.id if current else None,
        current_version_title=current.title if current else None,
        tailored_draft=(
            ApplicationWorkflowResumeVersionOut(
                id=tailored_draft.id,
                title=tailored_draft.title,
                source_version_id=tailored_draft.source_version_id,
                updated_at=_as_utc(tailored_draft.updated_at),
            )
            if tailored_draft
            else None
        ),
    )


def _workflow_next_action(application: Application) -> ApplicationWorkflowNextActionOut:
    follow_up_at = _as_utc(application.follow_up_at)
    if follow_up_at is not None:
        return ApplicationWorkflowNextActionOut(
            label="Follow up",
            due_at=follow_up_at,
            due=follow_up_at <= datetime.now(UTC),
        )
    if application.status in _TERMINAL_STATUSES:
        return ApplicationWorkflowNextActionOut(label="Application closed")
    labels = {
        ApplicationStatus.saved: "Review saved job",
        ApplicationStatus.interested: "Tailor resume",
        ApplicationStatus.resume_tailored: "Create or attach cover letter",
        ApplicationStatus.cover_letter_created: "Apply or set follow-up",
        ApplicationStatus.applied: "Set follow-up date",
        ApplicationStatus.contacted_recruiter: "Watch for reply",
        ApplicationStatus.referred: "Watch for referral update",
        ApplicationStatus.phone_screen: "Prepare for screen",
        ApplicationStatus.technical_interview: "Prepare for technical interview",
        ApplicationStatus.final_interview: "Prepare for final interview",
    }
    return ApplicationWorkflowNextActionOut(label=labels.get(application.status, "Set next step"))


def _workflow_activity(event: ActivityEvent) -> ApplicationWorkflowActivityOut:
    return ApplicationWorkflowActivityOut(
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        event_type=event.event_type,
        description=event.description,
        created_at=_as_utc(event.created_at),
    )


def _serialize(application: Application, job: Job) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        job_id=application.job_id,
        resume_id=application.resume_id,
        cover_letter_id=application.cover_letter_id,
        status=application.status,
        applied_at=_as_utc(application.applied_at),
        follow_up_at=_as_utc(application.follow_up_at),
        notes=application.notes,
        created_at=_as_utc(application.created_at),
        updated_at=_as_utc(application.updated_at),
        job={
            "id": job.id,
            "company_name": job.company_name,
            "title": job.title,
            "location": job.location,
        },
    )


def _serialize_follow_up(
    application: Application,
    job: Job,
    latest_activity: ApplicationFollowUpActivityOut | None,
    now: datetime,
) -> ApplicationFollowUpOut:
    follow_up_at = _as_utc(application.follow_up_at)
    if follow_up_at is None:
        raise ValueError("Follow-up reminders require follow_up_at")
    now = _as_utc(now)
    if now is None:
        raise ValueError("Follow-up due checks require now")
    return ApplicationFollowUpOut(
        id=application.id,
        job_id=application.job_id,
        status=application.status,
        follow_up_at=follow_up_at,
        notes=application.notes,
        updated_at=_as_utc(application.updated_at),
        due=follow_up_at <= now,
        job={
            "id": job.id,
            "company_name": job.company_name,
            "title": job.title,
            "location": job.location,
        },
        latest_activity=latest_activity,
    )


def _latest_activity_by_application(
    session: Session,
    user: User,
    application_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ApplicationFollowUpActivityOut]:
    if not application_ids:
        return {}
    events = session.exec(
        select(ActivityEvent)
        .where(
            ActivityEvent.user_id == user.id,
            ActivityEvent.entity_type == "application",
            ActivityEvent.entity_id.in_(application_ids),
        )
        .order_by(ActivityEvent.created_at.desc(), text("ctid DESC"))
    ).all()
    latest: dict[uuid.UUID, ApplicationFollowUpActivityOut] = {}
    for event in events:
        if event.entity_id in latest:
            continue
        latest[event.entity_id] = ApplicationFollowUpActivityOut(
            event_type=event.event_type,
            description=event.description,
            created_at=_as_utc(event.created_at),
        )
    return latest


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


@router.get("/follow-ups", response_model=list[ApplicationFollowUpOut])
def list_follow_ups(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    days: Annotated[int, Query(ge=0, le=90)] = 14,
) -> list[ApplicationFollowUpOut]:
    now = datetime.now(UTC)
    horizon = now + timedelta(days=days)
    rows = session.exec(
        select(Application, Job)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.user_id == current_user.id,
            Job.user_id == current_user.id,
            Application.follow_up_at.is_not(None),
            Application.follow_up_at <= horizon,
            Application.status.notin_(_TERMINAL_STATUSES),
        )
        .order_by(Application.follow_up_at.asc(), Application.updated_at.desc())
    ).all()
    application_ids = [application.id for application, _job in rows]
    latest_activity = _latest_activity_by_application(session, current_user, application_ids)
    return [
        _serialize_follow_up(
            application,
            job,
            latest_activity.get(application.id),
            now,
        )
        for application, job in rows
    ]


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

    application = Application(
        user_id=current_user.id,
        **_normalize_application_datetimes(payload.model_dump()),
    )
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


@router.get("/{application_id}/workflow", response_model=ApplicationWorkflowOut)
def get_application_workflow(
    application_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> ApplicationWorkflowOut:
    application, job = _get_owned_application(session, current_user, application_id)
    cover_letters = list(
        session.exec(
            select(CoverLetter)
            .where(CoverLetter.user_id == current_user.id, CoverLetter.job_id == job.id)
            .order_by(CoverLetter.updated_at.desc())
        ).all()
    )
    contacts = list(
        session.exec(
            select(Contact)
            .where(Contact.user_id == current_user.id, Contact.job_id == job.id)
            .order_by(Contact.updated_at.desc())
        ).all()
    )
    contact_ids = [contact.id for contact in contacts]
    outreach_filter = OutreachMessage.job_id == job.id
    if contact_ids:
        outreach_filter = outreach_filter | OutreachMessage.contact_id.in_(contact_ids)
    outreach_drafts = list(
        session.exec(
            select(OutreachMessage)
            .where(OutreachMessage.user_id == current_user.id, outreach_filter)
            .order_by(OutreachMessage.updated_at.desc())
        ).all()
    )
    entity_ids = [application.id, job.id]
    entity_ids.extend(letter.id for letter in cover_letters)
    entity_ids.extend(contact.id for contact in contacts)
    entity_ids.extend(outreach.id for outreach in outreach_drafts)
    events = session.exec(
        select(ActivityEvent)
        .where(ActivityEvent.user_id == current_user.id, ActivityEvent.entity_id.in_(entity_ids))
        .order_by(ActivityEvent.created_at.desc())
        .limit(20)
    ).all()
    linked_cover_letter = None
    if application.cover_letter_id is not None:
        linked_cover_letter = session.exec(
            select(CoverLetter).where(
                CoverLetter.id == application.cover_letter_id,
                CoverLetter.user_id == current_user.id,
                CoverLetter.job_id == job.id,
            )
        ).first()
    return ApplicationWorkflowOut(
        application=_serialize(application, job),
        job=job,
        next_action=_workflow_next_action(application),
        linked_resume=_workflow_resume(session, current_user, application.resume_id, job.id),
        linked_cover_letter=linked_cover_letter,
        cover_letters=cover_letters,
        contacts=contacts,
        outreach_drafts=outreach_drafts,
        recent_activity=[_workflow_activity(event) for event in events],
    )


@router.patch("/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: uuid.UUID,
    payload: ApplicationUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> ApplicationOut:
    application, job = _get_owned_application(session, current_user, application_id)
    updates = _normalize_application_datetimes(payload.model_dump(exclude_unset=True))
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
    old_follow_up_at = _as_utc(application.follow_up_at)
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

    if "follow_up_at" in updates and _datetime_changed(application.follow_up_at, old_follow_up_at):
        _add_activity(
            session,
            current_user,
            application,
            "application_follow_up_changed",
            f"Updated follow-up for {job.title} at {job.company_name}",
            {
                "from": _datetime_metadata(old_follow_up_at),
                "to": _datetime_metadata(application.follow_up_at),
            },
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
