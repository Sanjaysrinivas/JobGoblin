"""Authenticated cover-letter draft endpoints.

These endpoints only create and manage local editable drafts. They never send
email, submit applications, or perform external actions.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import ActivityEvent, CoverLetter, Job, Resume, User
from app.models.enums import CoverLetterStatus
from app.schemas.cover_letter import CoverLetterCreate, CoverLetterOut, CoverLetterUpdate
from app.services.ai_provider import get_ai_provider
from app.services.cover_letters import generate_cover_letter

router = APIRouter(prefix="/cover-letters", tags=["cover-letters"])


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _cover_letter_not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Cover letter not found", "cover_letter_not_found")


def _get_owned_job(session: Session, user: User, job_id: uuid.UUID) -> Job:
    job = session.exec(select(Job).where(Job.id == job_id, Job.user_id == user.id)).first()
    if job is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Job not found", "job_not_found")
    return job


def _get_owned_resume(session: Session, user: User, resume_id: uuid.UUID) -> Resume:
    resume = session.exec(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id)
    ).first()
    if resume is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Resume not found", "resume_not_found")
    return resume


def _get_owned_cover_letter(
    session: Session,
    user: User,
    cover_letter_id: uuid.UUID,
) -> CoverLetter:
    cover_letter = session.exec(
        select(CoverLetter).where(
            CoverLetter.id == cover_letter_id,
            CoverLetter.user_id == user.id,
        )
    ).first()
    if cover_letter is None:
        raise _cover_letter_not_found()
    return cover_letter


def _add_activity(
    session: Session,
    user: User,
    cover_letter: CoverLetter,
    event_type: str,
    description: str,
    metadata: dict | None = None,
) -> None:
    session.add(
        ActivityEvent(
            user_id=user.id,
            entity_type="cover_letter",
            entity_id=cover_letter.id,
            event_type=event_type,
            description=description,
            event_metadata=metadata,
        )
    )


@router.get("", response_model=list[CoverLetterOut])
def list_cover_letters(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    job_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[CoverLetter]:
    query = select(CoverLetter).where(CoverLetter.user_id == current_user.id)
    if job_id is not None:
        _get_owned_job(session, current_user, job_id)
        query = query.where(CoverLetter.job_id == job_id)
    return list(session.exec(query.order_by(CoverLetter.updated_at.desc())).all())


@router.post("", response_model=CoverLetterOut, status_code=status.HTTP_201_CREATED)
async def create_cover_letter(
    payload: CoverLetterCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> CoverLetter:
    job = _get_owned_job(session, current_user, payload.job_id)
    resume = _get_owned_resume(session, current_user, payload.resume_id)
    if not (resume.extracted_text or "").strip() and not resume.parsed_json:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "Resume has no extracted text to draft from.",
            "no_resume_content",
        )

    content = await generate_cover_letter(resume, job, payload.tone, get_ai_provider())
    if not content:
        raise _error(
            status.HTTP_502_BAD_GATEWAY,
            "Cover letter provider returned an empty draft.",
            "empty_cover_letter",
        )

    cover_letter = CoverLetter(
        user_id=current_user.id,
        job_id=job.id,
        resume_id=resume.id,
        tone=payload.tone,
        status=CoverLetterStatus.draft,
        content=content,
    )
    session.add(cover_letter)
    session.flush()
    _add_activity(
        session,
        current_user,
        cover_letter,
        "cover_letter_created",
        f"Created a cover letter draft for {job.title} at {job.company_name}",
        {"tone": payload.tone.value, "status": CoverLetterStatus.draft.value},
    )
    session.commit()
    session.refresh(cover_letter)
    return cover_letter


@router.get("/{cover_letter_id}", response_model=CoverLetterOut)
def get_cover_letter(
    cover_letter_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> CoverLetter:
    return _get_owned_cover_letter(session, current_user, cover_letter_id)


@router.patch("/{cover_letter_id}", response_model=CoverLetterOut)
def update_cover_letter(
    cover_letter_id: uuid.UUID,
    payload: CoverLetterUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> CoverLetter:
    cover_letter = _get_owned_cover_letter(session, current_user, cover_letter_id)
    updates = payload.model_dump(exclude_unset=True)

    if updates.get("content") is None and "content" in updates:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Content cannot be blank",
            "invalid_cover_letter_content",
        )
    if updates.get("tone") is None and "tone" in updates:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Tone cannot be null",
            "invalid_cover_letter_tone",
        )
    if updates.get("status") is None and "status" in updates:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Status cannot be null",
            "invalid_cover_letter_status",
        )

    old_status = cover_letter.status
    for field, value in updates.items():
        setattr(cover_letter, field, value)

    if "status" in updates and cover_letter.status != old_status:
        _add_activity(
            session,
            current_user,
            cover_letter,
            "cover_letter_status_changed",
            f"Moved cover letter to {cover_letter.status.value}",
            {"from": old_status.value, "to": cover_letter.status.value},
        )

    session.add(cover_letter)
    session.commit()
    session.refresh(cover_letter)
    return cover_letter
