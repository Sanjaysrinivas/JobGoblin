"""Review-only outreach draft endpoints.

These routes store local draft text and review state only. They do not send
email, open mail clients, post to LinkedIn, or perform any external outreach.
"""

import re
import uuid
from typing import Annotated, Literal
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import ActivityEvent, Contact, Job, OutreachMessage, User
from app.models.enums import OutreachChannel, OutreachStatus
from app.schemas.outreach import (
    OutreachCreate,
    OutreachEmailExportOut,
    OutreachGenerate,
    OutreachOut,
    OutreachUpdate,
)

router = APIRouter(prefix="/outreach", tags=["outreach"])

EmailExportAction = Literal["export", "copy", "open", "download"]
_EMAIL_EXPORT_EVENTS: dict[str, str] = {
    "export": "outreach_email_exported",
    "copy": "outreach_email_copied",
    "open": "outreach_email_opened",
    "download": "outreach_email_downloaded",
}


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


def _export_filename(outreach: OutreachMessage) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", outreach.message_type).strip("-").lower()
    return f"outreach-{stem or 'draft'}-{outreach.id}.txt"


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


def _first_name(contact: Contact | None) -> str:
    return contact.name.split()[0] if contact and contact.name.strip() else "there"


def _job_label(job: Job | None) -> str:
    return f"{job.title} at {job.company_name}" if job else "the opportunity"


def _outreach_content(
    message_type: str,
    user: User,
    job: Job | None,
    contact: Contact | None,
    notes: str | None,
) -> str:
    role = _job_label(job)
    company = (
        job.company_name
        if job
        else contact.company
        if contact and contact.company
        else "your team"
    )
    greeting = f"Hi {_first_name(contact)},"
    note = f"\n\nA detail I want to include: {notes}" if notes else ""
    signoff = f"\n\nBest,\n{user.display_name}"
    if message_type == "referral":
        body = (
            f"I noticed {role} and think it could be a strong fit. If you are comfortable, "
            "would you be open to referring me or pointing me to the right person?"
        )
    elif message_type == "thank_you":
        body = (
            f"Thank you for taking the time to speak with me about {role}. I appreciated "
            f"learning more about {company} and wanted to reiterate my interest."
        )
    elif message_type == "status_check":
        body = (
            f"I wanted to check in on the status of {role}. I remain interested and would "
            "appreciate any update you can share on timing or next steps."
        )
    else:
        body = (
            f"I wanted to follow up on {role}. I am still interested and would be glad "
            "to share anything else that would help with the process."
        )
    return f"{greeting}\n\n{body}{note}{signoff}"


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


@router.post("/generate", response_model=OutreachOut, status_code=status.HTTP_201_CREATED)
def generate_outreach(
    payload: OutreachGenerate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> OutreachOut:
    job = _get_owned_job(session, current_user, payload.job_id)
    contact = _get_owned_contact(session, current_user, payload.contact_id)
    content = _outreach_content(payload.message_type, current_user, job, contact, payload.notes)
    outreach = OutreachMessage(
        user_id=current_user.id,
        job_id=job.id if job else None,
        contact_id=contact.id if contact else None,
        channel=payload.channel,
        message_type=payload.message_type,
        content=content,
        status=OutreachStatus.draft,
    )
    session.add(outreach)
    session.flush()
    _add_activity(
        session,
        current_user,
        outreach,
        "outreach_generated",
        f"Generated {payload.message_type} outreach draft",
        {"status": outreach.status.value, "channel": outreach.channel.value},
    )
    session.commit()
    session.refresh(outreach)
    return _serialize(outreach, job, contact)


@router.post("/{outreach_id}/email-export", response_model=OutreachEmailExportOut)
def export_outreach_email(
    outreach_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    action: Annotated[EmailExportAction, Query()] = "export",
) -> OutreachEmailExportOut:
    outreach, job, contact = _get_owned_outreach(session, current_user, outreach_id)
    if outreach.channel != OutreachChannel.email:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Only email outreach drafts can be exported.",
            "not_email_outreach",
        )
    subject = f"{job.title} at {job.company_name}" if job else outreach.message_type
    to = contact.email if contact else None
    body = outreach.content
    query = urlencode({"subject": subject, "body": body}, quote_via=quote)
    mailto_url = f"mailto:{quote(to or '')}?{query}"
    text = f"To: {to or ''}\nSubject: {subject}\n\n{body}"
    _add_activity(
        session,
        current_user,
        outreach,
        _EMAIL_EXPORT_EVENTS[action],
        "Prepared email outreach draft for manual use",
        {"channel": outreach.channel.value, "action": action},
    )
    session.commit()
    return OutreachEmailExportOut(
        to=to,
        subject=subject,
        body=body,
        mailto_url=mailto_url,
        text=text,
        filename=_export_filename(outreach),
    )


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
