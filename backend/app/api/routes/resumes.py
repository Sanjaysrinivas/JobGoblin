"""Resume endpoints (design.md §4.2).

Every query is scoped to ``get_current_user``; rows owned by another user return
404 (not 403) so existence is never leaked. Upload validates content type and
size, stores the original via the storage layer, extracts text, persists the
``Resume`` row, then runs an inline AI section parse.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.core.storage import get_storage
from app.models import Resume, User
from app.schemas.resume import ResumeOut, ResumeUpdate
from app.services.ai_provider import get_ai_provider
from app.services.document_extractor import (
    SUPPORTED_CONTENT_TYPES,
    UnsupportedDocumentError,
    extract_text,
)
from app.services.pdf_export import render_resume_pdf
from app.services.resume_parser import parse_resume

router = APIRouter(prefix="/resumes", tags=["resumes"])

settings = get_settings()

# Map content type -> file extension for opaque storage keys.
_EXT_BY_TYPE = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
}


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Resume not found", "resume_not_found")


def _get_owned_resume(session: Session, user: User, resume_id: uuid.UUID) -> Resume:
    resume = session.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise _not_found()
    return resume


def _clear_other_defaults(session: Session, user_id: uuid.UUID, keep_id: uuid.UUID) -> None:
    """Enforce one default resume per user."""
    others = session.exec(
        select(Resume).where(
            Resume.user_id == user_id,
            Resume.is_default == True,  # noqa: E712 — SQLAlchemy needs ==, not `is`
            Resume.id != keep_id,
        )
    ).all()
    for other in others:
        other.is_default = False
        session.add(other)


@router.post("/upload", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File()],
) -> Resume:
    content_type = file.content_type or ""
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise _error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only PDF and DOCX files are supported.",
            "unsupported_type",
        )

    data = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise _error(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"File exceeds the {settings.max_upload_mb} MB limit.",
            "file_too_large",
        )
    if not data:
        raise _error(status.HTTP_400_BAD_REQUEST, "Empty file.", "empty_file")

    # Extract text up front so a corrupt/unreadable file fails before we persist.
    try:
        text = extract_text(data, content_type)
    except UnsupportedDocumentError as exc:
        raise _error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc), "unsupported_type"
        ) from exc

    ext = _EXT_BY_TYPE.get(content_type, "")
    key = f"{current_user.id}/{uuid.uuid4()}{ext}"
    await get_storage().save(key, data, content_type)

    filename = file.filename or "resume"
    resume = Resume(
        user_id=current_user.id,
        title=filename.rsplit(".", 1)[0] or "Resume",
        original_filename=filename,
        file_key=key,
        content_type=content_type,
        file_size=len(data),
        extracted_text=text,
    )

    # Inline AI parse (MockProvider in tests; Ollama in production).
    if text:
        resume.parsed_json = await parse_resume(text, get_ai_provider())

    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeOut])
def list_resumes(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[Resume]:
    return list(
        session.exec(
            select(Resume)
            .where(Resume.user_id == current_user.id)
            .order_by(Resume.created_at.desc())
        ).all()
    )


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(
    resume_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Resume:
    return _get_owned_resume(session, current_user, resume_id)


@router.patch("/{resume_id}", response_model=ResumeOut)
def update_resume(
    resume_id: uuid.UUID,
    payload: ResumeUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Resume:
    resume = _get_owned_resume(session, current_user, resume_id)

    if payload.title is not None:
        resume.title = payload.title
    if payload.extracted_text is not None:
        resume.extracted_text = payload.extracted_text
    if payload.is_default is not None:
        resume.is_default = payload.is_default
        if payload.is_default:
            _clear_other_defaults(session, current_user.id, resume.id)

    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    resume = _get_owned_resume(session, current_user, resume_id)
    file_key = resume.file_key
    session.delete(resume)
    session.commit()
    # Remove the stored blob after the row is gone (idempotent on missing files).
    await get_storage().delete(file_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{resume_id}/parse", response_model=ResumeOut)
async def reparse_resume(
    resume_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Resume:
    resume = _get_owned_resume(session, current_user, resume_id)
    if not resume.extracted_text:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "No extracted text to parse.",
            "no_extracted_text",
        )
    resume.parsed_json = await parse_resume(resume.extracted_text, get_ai_provider())
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


@router.get("/{resume_id}/export.pdf")
def export_resume_pdf(
    resume_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    resume = _get_owned_resume(session, current_user, resume_id)
    pdf_bytes = render_resume_pdf(resume.title, resume.parsed_json)
    filename = f"{resume.title or 'resume'}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
