"""Review-only outreach draft endpoints.

These routes store local draft text and review state only. They do not send
email, open mail clients, post to LinkedIn, or perform any external outreach.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import ActivityEvent, Contact, Job, OutreachMessage, User
from app.models.enums import OutreachStatus
from app.schemas.outreach import OutreachCreate, OutreachOut, OutreachUpdate

router = APIRouter(prefix="/outreach", tags=["outreach"])


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Outreach draft not found", "outreach_not_found")


def _get_owned_job(session: Session, user: User, job_id: uuid.UUID | None) -> Job | None:
    if job_id is None:
        return None
    job = session.exec(select(Job).where(Job.id == job_id, Job.user_id == user.id)).first()
    if job is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Job not found", "job_not_found")
    return job


def _get_owned_contact(
    session: Session, user: User, contact_id: uuid.UUID | None
) -> Contact | None:
    if contact_id is None:
        return None
    contact = session.exec(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == user.id)
    ).first()
    if contact is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Contact not found", "contact_not_found")
    return contact


def _get_owned_outreach(
    session: Session, user: User, outreach_id: uuid.UUID
) -> tuple[OutreachMessage, Job | None, Contact | None]:
    row = session.exec(
        select(OutreachMessage, Job, Contact)
        .join(Job, Job.id == OutreachMessage.job_id, isouter=True)
        .join(Contact, Contact.id == OutreachMessage.contact_id, isouter=True)
        .where(OutreachMessage.id == outreach_id, OutreachMessage.user_id == user.id)
    ).first()
    if row is None:
        raise _not_found()
    outreach, job, contact = row
    if job is not None and job.user_id != user.id:
        raise _not_found()
    if contact is not None and contact.user_id != user.id:
        raise _not_found()
    return outreach, job, contact


def _serialize(
    outreach: OutreachMessage, job: Job | None = None, contact: Contact | None = None
) -> OutreachOut:
    return OutreachOut(
        id=outreach.id,
        job_id=outreach.job_id,
        contact_id=outreach.contact_id,
        channel=outreach.channel,
        message_type=outreach.message_type,
        content=outreach.content,
        status=outreach.status,
        created_at=outreach.created_at,
        updated_at=outreach.updated_at,
        job=(
            {
                "id": job.id,
                "company_name": job.company_name,
                "title": job.title,
                "location": job.location,
            }
            if job is not None
            else None
        ),
        contact=(
            {
                "id": contact.id,
                "name": contact.name,
                "company": contact.company,
                "role": contact.role,
                "email": contact.email,
                "linkedin_url": contact.linkedin_url,
            }
            if contact is not None
            else None
        ),
    )


def _add_activity(
    session: Session,
    user: User,
    outreach: OutreachMessage,
    event_type: str,
    description: str,
    metadata: dict | None = None,
) -> None:
    session.add(
        ActivityEvent(
            user_id=user.id,
            entity_type="outreach",
            entity_id=outreach.id,
            event_type=event_type,
            description=description,
            event_metadata=metadata,
        )
    )


@router.get("", response_model=list[OutreachOut])
def list_outreach(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[OutreachOut]:
    rows = session.exec(
        select(OutreachMessage, Job, Contact)
        .join(Job, Job.id == OutreachMessage.job_id, isouter=True)
        .join(Contact, Contact.id == OutreachMessage.contact_id, isouter=True)
        .where(OutreachMessage.user_id == current_user.id)
        .order_by(OutreachMessage.updated_at.desc())
    ).all()
    return [
        _serialize(
            outreach,
            job if job and job.user_id == current_user.id else None,
            contact if contact and contact.user_id == current_user.id else None,
        )
        for outreach, job, contact in rows
    ]


@router.post("", response_model=OutreachOut, status_code=status.HTTP_201_CREATED)
def create_outreach(
    payload: OutreachCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> OutreachOut:
    job = _get_owned_job(session, current_user, payload.job_id)
    contact = _get_owned_contact(session, current_user, payload.contact_id)
    outreach = OutreachMessage(user_id=current_user.id, **payload.model_dump())
    session.add(outreach)
    session.flush()
    _add_activity(
        session,
        current_user,
        outreach,
        "outreach_created",
        f"Created {outreach.channel.value} outreach draft",
        {"status": outreach.status.value, "channel": outreach.channel.value},
    )
    session.commit()
    session.refresh(outreach)
    return _serialize(outreach, job, contact)


@router.get("/{outreach_id}", response_model=OutreachOut)
def get_outreach(
    outreach_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> OutreachOut:
    outreach, job, contact = _get_owned_outreach(session, current_user, outreach_id)
    return _serialize(outreach, job, contact)


@router.patch("/{outreach_id}", response_model=OutreachOut)
def update_outreach(
    outreach_id: uuid.UUID,
    payload: OutreachUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> OutreachOut:
    outreach, _job, _contact = _get_owned_outreach(session, current_user, outreach_id)
    updates = payload.model_dump(exclude_unset=True)

    job = _get_owned_job(
        session, current_user, updates["job_id"] if "job_id" in updates else outreach.job_id
    )
    contact = _get_owned_contact(
        session,
        current_user,
        updates["contact_id"] if "contact_id" in updates else outreach.contact_id,
    )

    old_status: OutreachStatus = outreach.status
    for field, value in updates.items():
        setattr(outreach, field, value)

    if "status" in updates and outreach.status != old_status:
        event_type = (
            "outreach_copied"
            if outreach.status == OutreachStatus.copied
            else "outreach_status_changed"
        )
        _add_activity(
            session,
            current_user,
            outreach,
            event_type,
            f"Moved outreach draft to {outreach.status.value}",
            {"from": old_status.value, "to": outreach.status.value},
        )

    session.add(outreach)
    session.commit()
    session.refresh(outreach)
    return _serialize(outreach, job, contact)


@router.delete("/{outreach_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_outreach(
    outreach_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    outreach, _job, _contact = _get_owned_outreach(session, current_user, outreach_id)
    session.delete(outreach)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)