import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import ActivityEvent, Application, Job, User
from app.models.enums import ApplicationStatus


def _user(session, email: str = "owner@example.com") -> User:
    user = User(email=email, password_hash="x", display_name=email.split("@")[0])
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _client(session, user: User):
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def _job(session, user: User, company_name: str, title: str = "Engineer") -> Job:
    job = Job(
        user_id=user.id,
        company_name=company_name,
        title=title,
        description="Build reliable services.",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _application(
    session,
    user: User,
    job: Job,
    *,
    follow_up_at: datetime | None,
    status: ApplicationStatus = ApplicationStatus.applied,
    notes: str | None = None,
) -> Application:
    application = Application(
        user_id=user.id,
        job_id=job.id,
        follow_up_at=follow_up_at,
        status=status,
        notes=notes,
    )
    session.add(application)
    session.commit()
    session.refresh(application)
    return application


def test_follow_ups_list_due_and_upcoming_applications(session):
    user = _user(session)
    other_user = _user(session, "other@example.com")
    now = datetime.now(UTC)

    due_job = _job(session, user, "DueCo")
    upcoming_job = _job(session, user, "SoonCo")
    future_job = _job(session, user, "FutureCo")
    terminal_job = _job(session, user, "ClosedCo")
    no_follow_up_job = _job(session, user, "NoReminderCo")
    other_job = _job(session, other_user, "OtherCo")

    due = _application(
        session,
        user,
        due_job,
        follow_up_at=now - timedelta(days=1),
        notes="Due yesterday",
    )
    upcoming = _application(session, user, upcoming_job, follow_up_at=now + timedelta(days=2))
    _application(session, user, future_job, follow_up_at=now + timedelta(days=30))
    _application(
        session,
        user,
        terminal_job,
        follow_up_at=now + timedelta(days=1),
        status=ApplicationStatus.rejected,
    )
    _application(session, user, no_follow_up_job, follow_up_at=None)
    _application(session, other_user, other_job, follow_up_at=now - timedelta(days=1))

    session.add(
        ActivityEvent(
            user_id=user.id,
            entity_type="application",
            entity_id=due.id,
            event_type="application_created",
            description="Started tracking DueCo",
        )
    )
    session.add(
        ActivityEvent(
            user_id=user.id,
            entity_type="application",
            entity_id=due.id,
            event_type="application_follow_up_changed",
            description="Updated follow-up for DueCo",
        )
    )
    session.commit()

    app = _client(session, user)
    with TestClient(app) as client:
        response = client.get("/api/applications/follow-ups?days=14")
    app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["id"] for item in body] == [str(due.id), str(upcoming.id)]
    assert body[0]["due"] is True
    assert body[0]["notes"] == "Due yesterday"
    assert body[0]["job"]["company_name"] == "DueCo"
    assert body[0]["latest_activity"] == {
        "event_type": "application_follow_up_changed",
        "description": "Updated follow-up for DueCo",
        "created_at": body[0]["latest_activity"]["created_at"],
    }
    assert body[1]["due"] is False
    assert body[1]["job"]["company_name"] == "SoonCo"
    assert body[1]["latest_activity"] is None


def test_follow_ups_respect_days_window(session):
    user = _user(session)
    now = datetime.now(UTC)
    today_job = _job(session, user, "TodayCo")
    tomorrow_job = _job(session, user, "TomorrowCo")
    today = _application(session, user, today_job, follow_up_at=now)
    _application(session, user, tomorrow_job, follow_up_at=now + timedelta(days=1))

    app = _client(session, user)
    with TestClient(app) as client:
        response = client.get("/api/applications/follow-ups?days=0")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(today.id)]


def test_follow_ups_require_authentication(session):
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        response = client.get("/api/applications/follow-ups")
    app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_patch_follow_up_records_activity(session):
    user = _user(session)
    job = _job(session, user, "ActivityCo")
    application = _application(session, user, job, follow_up_at=None)
    follow_up_at = datetime.now(UTC) + timedelta(days=3)

    app = _client(session, user)
    with TestClient(app) as client:
        response = client.patch(
            f"/api/applications/{application.id}",
            json={"follow_up_at": follow_up_at.isoformat()},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert response.json()["follow_up_at"] is not None

    event = session.exec(
        select(ActivityEvent).where(
            ActivityEvent.entity_type == "application",
            ActivityEvent.entity_id == uuid.UUID(response.json()["id"]),
            ActivityEvent.event_type == "application_follow_up_changed",
        )
    ).one()
    assert event.user_id == user.id
    assert event.description == "Updated follow-up for Engineer at ActivityCo"
    assert event.event_metadata["from"] is None
    assert datetime.fromisoformat(event.event_metadata["to"]) == datetime.fromisoformat(
        response.json()["follow_up_at"].replace("Z", "+00:00")
    )
