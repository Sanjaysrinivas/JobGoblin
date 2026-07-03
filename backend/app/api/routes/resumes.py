"""Resume endpoints (design.md section 4.2).

Every query is scoped to ``get_current_user``; rows owned by another user return
404 (not 403) so existence is never leaked. Upload stores immutable source facts
on ``resumes`` and creates an editable current ``resume_versions`` row.
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.core.storage import get_storage
from app.models import Resume, ResumeVersion, User
from app.schemas.resume import (
    ResumeOut,
    ResumeUpdate,
    ResumeVersionCreate,
    ResumeVersionOut,
    ResumeVersionUpdate,
)
from app.services.ai_provider import get_ai_provider
from app.services.document_extractor import (
    SUPPORTED_CONTENT_TYPES,
    ExtractionError,
    UnsupportedDocumentError,
    extract_text,
)
from app.services.pdf_export import render_resume_pdf
from app.services.resume_parser import parse_resume

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resumes", tags=["resumes"])

settings = get_settings()

# Map content type -> file extension for opaque storage keys. Only PDF/DOCX are
# supported (legacy .doc is not; python-docx cannot read it).
_EXT_BY_TYPE = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Resume not found", "resume_not_found")


def _version_not_found() -> HTTPException:
    return _error(
        status.HTTP_404_NOT_FOUND,
        "Resume version not found",
        "resume_version_not_found",
    )


def _pdf_filename(title: str | None) -> str:
    safe_title = (title or "resume").replace('"', "").replace("\n", "").replace("\r", "")
    return f"{safe_title or 'resume'}.pdf"


def _get_owned_resume(session: Session, user: User, resume_id: uuid.UUID) -> Resume:
    resume = session.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise _not_found()
    return resume


def _get_owned_version(
    session: Session, resume: Resume, version_id: uuid.UUID
) -> ResumeVersion:
    version = session.get(ResumeVersion, version_id)
    if version is None or version.resume_id != resume.id:
        raise _version_not_found()
    return version


def _get_current_version(session: Session, resume: Resume) -> ResumeVersion | None:
    return session.exec(
        select(ResumeVersion)
        .where(
            ResumeVersion.resume_id == resume.id,
            ResumeVersion.is_current == True,  # noqa: E712 - SQLAlchemy expression
        )
        .order_by(ResumeVersion.updated_at.desc())
    ).first()


def _current_version_or_source(session: Session, resume: Resume) -> ResumeVersion:
    version = _get_current_version(session, resume)
    if version is not None:
        return version

    version = ResumeVersion(
        resume_id=resume.id,
        title=resume.title,
        extracted_text=resume.extracted_text,
        parsed_json=resume.parsed_json,
        is_current=True,
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


def _resume_payload(
    session: Session, resume: Resume, version: ResumeVersion | None = None
) -> dict:
    current = version or _get_current_version(session, resume)
    version_count = session.exec(
        select(func.count()).select_from(ResumeVersion).where(ResumeVersion.resume_id == resume.id)
    ).one()
    return {
        "id": resume.id,
        "current_version_id": current.id if current else None,
        "current_version": current,
        "version_count": version_count,
        "title": current.title if current else resume.title,
        "original_filename": resume.original_filename,
        "content_type": resume.content_type,
        "file_size": resume.file_size,
        "extracted_text": current.extracted_text if current else resume.extracted_text,
        "parsed_json": current.parsed_json if current else resume.parsed_json,
        "is_default": resume.is_default,
        "created_at": resume.created_at,
        "updated_at": resume.updated_at,
    }


def _clear_other_defaults(session: Session, user_id: uuid.UUID, keep_id: uuid.UUID) -> None:
    """Enforce one default resume per user."""
    others = session.exec(
        select(Resume).where(
            Resume.user_id == user_id,
            Resume.is_default == True,  # noqa: E712 - SQLAlchemy expression
            Resume.id != keep_id,
        )
    ).all()
    for other in others:
        other.is_default = False
        session.add(other)


def _clear_current_versions(session: Session, resume_id: uuid.UUID, keep_id: uuid.UUID) -> None:
    versions = session.exec(
        select(ResumeVersion).where(
            ResumeVersion.resume_id == resume_id,
            ResumeVersion.is_current == True,  # noqa: E712 - SQLAlchemy expression
            ResumeVersion.id != keep_id,
        )
    ).all()
    for version in versions:
        version.is_current = False
        session.add(version)


@router.post("/upload", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File()],
) -> dict:
    content_type = file.content_type or ""
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise _error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only PDF and DOCX files are supported.",
            "unsupported_type",
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024

    declared = file.size if file.size is not None else None
    if declared is not None and declared > max_bytes:
        raise _error(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"File exceeds the {settings.max_upload_mb} MB limit.",
            "file_too_large",
        )

    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise _error(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"File exceeds the {settings.max_upload_mb} MB limit.",
            "file_too_large",
        )
    if not data:
        raise _error(status.HTTP_400_BAD_REQUEST, "Empty file.", "empty_file")

    try:
        text = extract_text(data, content_type)
    except UnsupportedDocumentError as exc:
        raise _error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc), "unsupported_type"
        ) from exc
    except ExtractionError as exc:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc), "unprocessable_file"
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

    if text:
        try:
            resume.parsed_json = await parse_resume(text, get_ai_provider())
        except Exception:
            logger.warning("Inline resume parse failed; saving without parsed_json")
            resume.parsed_json = None

    version = ResumeVersion(
        resume_id=resume.id,
        title=resume.title,
        extracted_text=resume.extracted_text,
        parsed_json=resume.parsed_json,
        is_current=True,
    )
    session.add(resume)
    session.add(version)
    session.commit()
    session.refresh(resume)
    session.refresh(version)
    return _resume_payload(session, resume, version)


@router.get("", response_model=list[ResumeOut])
def list_resumes(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict]:
    resumes = session.exec(
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
    ).all()
    return [_resume_payload(session, resume) for resume in resumes]


@router.get("/{resume_id}/versions", response_model=list[ResumeVersionOut])
def list_resume_versions(
    resume_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ResumeVersion]:
    resume = _get_owned_resume(session, current_user, resume_id)
    return list(
        session.exec(
            select(ResumeVersion)
            .where(ResumeVersion.resume_id == resume.id)
            .order_by(ResumeVersion.is_current.desc(), ResumeVersion.updated_at.desc())
        ).all()
    )


@router.post(
    "/{resume_id}/versions",
    response_model=ResumeVersionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_resume_version(
    resume_id: uuid.UUID,
    payload: ResumeVersionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> ResumeVersion:
    resume = _get_owned_resume(session, current_user, resume_id)
    source = (
        _get_owned_version(session, resume, payload.source_version_id)
        if payload.source_version_id
        else _current_version_or_source(session, resume)
    )
    fields = payload.model_fields_set
    version = ResumeVersion(
        resume_id=resume.id,
        title=payload.title if payload.title is not None else f"{source.title} Copy",
        extracted_text=(
            payload.extracted_text if "extracted_text" in fields else source.extracted_text
        ),
        parsed_json=payload.parsed_json if "parsed_json" in fields else source.parsed_json,
        is_current=False,
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


@router.patch("/{resume_id}/versions/{version_id}", response_model=ResumeVersionOut)
def update_resume_version(
    resume_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: ResumeVersionUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> ResumeVersion:
    resume = _get_owned_resume(session, current_user, resume_id)
    version = _get_owned_version(session, resume, version_id)
    fields = payload.model_fields_set

    if payload.title is not None:
        version.title = payload.title
    if "extracted_text" in fields:
        version.extracted_text = payload.extracted_text
    if "parsed_json" in fields:
        version.parsed_json = payload.parsed_json

    session.add(version)
    session.commit()
    session.refresh(version)
    return version


@router.post("/{resume_id}/versions/{version_id}/make-current", response_model=ResumeVersionOut)
def make_resume_version_current(
    resume_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> ResumeVersion:
    resume = _get_owned_resume(session, current_user, resume_id)
    version = _get_owned_version(session, resume, version_id)
    _clear_current_versions(session, resume.id, version.id)
    version.is_current = True
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


@router.delete("/{resume_id}/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume_version(
    resume_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    resume = _get_owned_resume(session, current_user, resume_id)
    version = _get_owned_version(session, resume, version_id)
    version_count = session.exec(
        select(func.count()).select_from(ResumeVersion).where(ResumeVersion.resume_id == resume.id)
    ).one()
    if version_count <= 1:
        raise _error(
            status.HTTP_409_CONFLICT,
            "Cannot delete the last resume version.",
            "last_resume_version",
        )

    if version.is_current:
        replacement = session.exec(
            select(ResumeVersion)
            .where(ResumeVersion.resume_id == resume.id, ResumeVersion.id != version.id)
            .order_by(ResumeVersion.updated_at.desc())
        ).first()
        if replacement is not None:
            replacement.is_current = True
            session.add(replacement)

    session.delete(version)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(
    resume_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    resume = _get_owned_resume(session, current_user, resume_id)
    return _resume_payload(session, resume)


@router.patch("/{resume_id}", response_model=ResumeOut)
def update_resume(
    resume_id: uuid.UUID,
    payload: ResumeUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    resume = _get_owned_resume(session, current_user, resume_id)
    version = None

    if payload.title is not None or payload.extracted_text is not None:
        version = _current_version_or_source(session, resume)
        if payload.title is not None:
            version.title = payload.title
        if payload.extracted_text is not None:
            version.extracted_text = payload.extracted_text
        session.add(version)

    if payload.is_default is not None:
        resume.is_default = payload.is_default
        if payload.is_default:
            _clear_other_defaults(session, current_user.id, resume.id)
        session.add(resume)

    session.commit()
    session.refresh(resume)
    if version is not None:
        session.refresh(version)
    return _resume_payload(session, resume, version)


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
    try:
        await get_storage().delete(file_key)
    except Exception:
        logger.warning("Failed to delete stored file for resume %s", resume_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{resume_id}/parse", response_model=ResumeOut)
async def reparse_resume(
    resume_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    resume = _get_owned_resume(session, current_user, resume_id)
    version = _current_version_or_source(session, resume)
    if not version.extracted_text:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "No extracted text to parse.",
            "no_extracted_text",
        )
    version.parsed_json = await parse_resume(version.extracted_text, get_ai_provider())
    session.add(version)
    session.commit()
    session.refresh(resume)
    session.refresh(version)
    return _resume_payload(session, resume, version)



@router.get("/{resume_id}/versions/{version_id}/export.pdf")
def export_resume_version_pdf(
    resume_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    resume = _get_owned_resume(session, current_user, resume_id)
    version = _get_owned_version(session, resume, version_id)
    pdf_bytes = render_resume_pdf(version.title, version.parsed_json)
    filename = _pdf_filename(version.title)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )

@router.get("/{resume_id}/export.pdf")
def export_resume_pdf(
    resume_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    resume = _get_owned_resume(session, current_user, resume_id)
    version = _get_current_version(session, resume)
    title = version.title if version else resume.title
    parsed_json = version.parsed_json if version else resume.parsed_json
    pdf_bytes = render_resume_pdf(title, parsed_json)
    filename = _pdf_filename(title)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
