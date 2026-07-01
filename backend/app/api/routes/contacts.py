"""Authenticated CRUD endpoints for contacts.

All contact access is scoped to the current user. Linked jobs must also belong
to the current user so cross-user object existence is not leaked.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import Contact, Job, User
from app.schemas.contact import ContactCreate, ContactOut, ContactUpdate

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Contact not found", "contact_not_found")


def _job_not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Job not found", "job_not_found")


def _get_owned_contact(session: Session, user: User, contact_id: uuid.UUID) -> Contact:
    contact = session.exec(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == user.id)
    ).first()
    if contact is None:
        raise _not_found()
    return contact


def _validate_owned_job(session: Session, user: User, job_id: uuid.UUID | None) -> None:
    if job_id is None:
        return
    job = session.exec(select(Job.id).where(Job.id == job_id, Job.user_id == user.id)).first()
    if job is None:
        raise _job_not_found()


@router.get("", response_model=list[ContactOut])
def list_contacts(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[Contact]:
    return list(
        session.exec(
            select(Contact)
            .where(Contact.user_id == current_user.id)
            .order_by(Contact.created_at.desc())
        ).all()
    )


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Contact:
    _validate_owned_job(session, current_user, payload.job_id)
    contact = Contact(user_id=current_user.id, **payload.model_dump())
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(
    contact_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Contact:
    return _get_owned_contact(session, current_user, contact_id)


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: uuid.UUID,
    payload: ContactUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Contact:
    contact = _get_owned_contact(session, current_user, contact_id)
    updates = payload.model_dump(exclude_unset=True)
    if "job_id" in updates:
        _validate_owned_job(session, current_user, updates["job_id"])

    for field, value in updates.items():
        setattr(contact, field, value)

    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    contact = _get_owned_contact(session, current_user, contact_id)
    session.delete(contact)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
