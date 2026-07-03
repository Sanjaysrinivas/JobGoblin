from sqlmodel import Session, select

from app.models import Resume, ResumeVersion


def current_resume_content(session: Session, resume: Resume) -> tuple[str, dict | None]:
    version = session.exec(
        select(ResumeVersion)
        .where(
            ResumeVersion.resume_id == resume.id,
            ResumeVersion.is_current
        )
        .order_by(ResumeVersion.updated_at.desc())
    ).first()
    if version is not None:
        return version.extracted_text or "", version.parsed_json
    return resume.extracted_text or "", resume.parsed_json