"""Dashboard summary and activity endpoints."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import ActivityEvent, Application, Job, JobAnalysis, User
from app.models.enums import ApplicationStatus
from app.schemas.dashboard import ActivityEventOut, DashboardSummaryOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_INTERVIEW_STATUSES = (
    ApplicationStatus.phone_screen,
    ApplicationStatus.technical_interview,
    ApplicationStatus.final_interview,
)
_TERMINAL_STATUSES = (
    ApplicationStatus.offer,
    ApplicationStatus.rejected,
    ApplicationStatus.withdrawn,
    ApplicationStatus.archived,
)


def _count(session: Session, statement) -> int:
    value = session.exec(statement).one()
    return int(value or 0)


def _serialize_event(event: ActivityEvent) -> ActivityEventOut:
    return ActivityEventOut(
        id=event.id,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        event_type=event.event_type,
        description=event.description,
        metadata=event.event_metadata,
        created_at=event.created_at,
    )


@router.get("/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> DashboardSummaryOut:
    now = datetime.now(UTC)
    avg_score = session.exec(
        select(func.avg(JobAnalysis.overall_score)).where(JobAnalysis.user_id == current_user.id)
    ).one()

    return DashboardSummaryOut(
        saved=_count(
            session,
            select(func.count()).select_from(Job).where(Job.user_id == current_user.id),
        ),
        applied=_count(
            session,
            select(func.count())
            .select_from(Application)
            .where(
                Application.user_id == current_user.id,
                Application.applied_at.is_not(None),
            ),
        ),
        interviewing=_count(
            session,
            select(func.count())
            .select_from(Application)
            .where(
                Application.user_id == current_user.id,
                Application.status.in_(_INTERVIEW_STATUSES),
            ),
        ),
        offers=_count(
            session,
            select(func.count())
            .select_from(Application)
            .where(
                Application.user_id == current_user.id,
                Application.status == ApplicationStatus.offer,
            ),
        ),
        follow_ups_due=_count(
            session,
            select(func.count())
            .select_from(Application)
            .where(
                Application.user_id == current_user.id,
                Application.follow_up_at.is_not(None),
                Application.follow_up_at <= now,
                Application.status.notin_(_TERMINAL_STATUSES),
            ),
        ),
        avg_score=float(avg_score) if avg_score is not None else None,
    )


@router.get("/activity", response_model=list[ActivityEventOut])
def list_dashboard_activity(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[ActivityEventOut]:
    events = session.exec(
        select(ActivityEvent)
        .where(ActivityEvent.user_id == current_user.id)
        .order_by(ActivityEvent.created_at.desc())
        .limit(limit)
    ).all()
    return [_serialize_event(event) for event in events]
