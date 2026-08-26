"""Shared application-state invariants used by material and tracker routes."""

import uuid
from datetime import UTC, datetime

from sqlmodel import Session, select

from app.models import ActivityEvent, Application
from app.models.enums import ApplicationStatus

SUBMITTED_STATUSES = {
    ApplicationStatus.applied,
    ApplicationStatus.contacted_recruiter,
    ApplicationStatus.referred,
    ApplicationStatus.phone_screen,
    ApplicationStatus.technical_interview,
    ApplicationStatus.final_interview,
    ApplicationStatus.offer,
    ApplicationStatus.rejected,
}

_PREPARATION_ORDER = {
    ApplicationStatus.saved: 0,
    ApplicationStatus.interested: 1,
    ApplicationStatus.resume_tailored: 2,
    ApplicationStatus.cover_letter_created: 3,
}


def sync_applied_at(application: Application) -> None:
    """Set the first submission time when a status proves an application occurred."""
    if application.status in SUBMITTED_STATUSES and application.applied_at is None:
        application.applied_at = datetime.now(UTC)


def link_application_material(
    session: Session,
    *,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    resume_id: uuid.UUID | None = None,
    cover_letter_id: uuid.UUID | None = None,
    material_status: ApplicationStatus,
) -> Application | None:
    """Link a generated local material and advance only preparation statuses."""
    application = session.exec(
        select(Application).where(
            Application.user_id == user_id,
            Application.job_id == job_id,
        )
    ).first()
    if application is None:
        return None

    changed: list[str] = []
    old_status = application.status
    if resume_id is not None and application.resume_id != resume_id:
        application.resume_id = resume_id
        changed.append("resume")
    if cover_letter_id is not None and application.cover_letter_id != cover_letter_id:
        application.cover_letter_id = cover_letter_id
        changed.append("cover letter")
    if (
        application.status in _PREPARATION_ORDER
        and _PREPARATION_ORDER[application.status] < _PREPARATION_ORDER[material_status]
    ):
        application.status = material_status
        changed.append("status")
    if not changed:
        return application

    session.add(application)
    session.add(
        ActivityEvent(
            user_id=user_id,
            entity_type="application",
            entity_id=application.id,
            event_type="application_material_linked",
            description=f"Linked {' and '.join(changed)} to the application workflow",
            event_metadata={
                "from_status": old_status.value,
                "to_status": application.status.value,
                "resume_id": str(application.resume_id) if application.resume_id else None,
                "cover_letter_id": (
                    str(application.cover_letter_id) if application.cover_letter_id else None
                ),
            },
        )
    )
    return application
