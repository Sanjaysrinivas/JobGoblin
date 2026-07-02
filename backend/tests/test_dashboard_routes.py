import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import (
    ActivityEvent,
    Application,
    Contact,
    Job,
    JobAnalysis,
    Resume,
    User,
)
from app.models.enums import ApplicationStatus


@pytest.fixture
def user(session) -> User:
    u = User(email="owner@example.com", password_hash="x", display_name="Owner")
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


@pytest.fixture
def other_user(session) -> User:
    u = User(email="other@example.com", password_hash="x", display_name="Other")
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


@pytest.fixture
def client(session, user):
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _job(session, user: User, **overrides) -> Job:
    values = {
        "user_id": user.id,
        "company_name": "Acme",
        "title": "Backend Engineer",
        "description": "Build reliable services.",
    }
    values.update(overrides)
    job = Job(**values)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _resume(session, user: User) -> Resume:
    resume = Resume(
        user_id=user.id,
        title="Baseline",
        original_filename="resume.pdf",
        file_key=f"{user.id}/resume.pdf",
        content_type="application/pdf",
        file_size=123,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def _analysis(session, user: User, resume: Resume, job: Job, score: int) -> JobAnalysis:
    analysis = JobAnalysis(
        user_id=user.id,
        resume_id=resume.id,
        job_id=job.id,
        overall_score=score,
        keyword_score=score,
        skills_score=0,
        experience_score=0,
        role_score=0,
        education_score=0,
        formatting_score=0,
        provider="mock",
        model_used="mock",
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis


def test_summary_counts_only_current_user_data(client, session, user, other_user):
    now = datetime.now(UTC)
    owned_job = _job(session, user)
    second_owned_job = _job(session, user, title="Platform Engineer")
    other_job = _job(session, other_user, company_name="OtherCo")
    owned_resume = _resume(session, user)
    other_resume = _resume(session, other_user)
    session.add(Contact(user_id=user.id, name="Recruiter", company="Acme"))
    session.add(Contact(user_id=other_user.id, name="Hidden", company="OtherCo"))
    session.add_all(
        [
            Application(
                user_id=user.id,
                job_id=owned_job.id,
                status=ApplicationStatus.saved,
                follow_up_at=now - timedelta(days=1),
            ),
            Application(
                user_id=user.id,
                job_id=second_owned_job.id,
                status=ApplicationStatus.rejected,
                follow_up_at=now - timedelta(days=2),
            ),
            Application(
                user_id=other_user.id,
                job_id=other_job.id,
                status=ApplicationStatus.saved,
                follow_up_at=now - timedelta(days=3),
            ),
        ]
    )
    session.commit()
    _analysis(session, user, owned_resume, owned_job, 80)
    _analysis(session, user, owned_resume, second_owned_job, 90)
    _analysis(session, other_user, other_resume, other_job, 10)

    resp = client.get("/api/dashboard/summary")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["saved"] == 2
    assert body["applied"] == 0
    assert body["interviewing"] == 0
    assert body["offers"] == 0
    assert body["follow_ups_due"] == 1
    assert body["avg_score"] == 85.0


def test_activity_is_user_scoped_ordered_and_limited(client, session, user, other_user):
    entity_id = uuid.uuid4()
    old = ActivityEvent(
        user_id=user.id,
        entity_type="application",
        entity_id=entity_id,
        event_type="old",
        description="Old event",
        event_metadata={"rank": 1},
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newest = ActivityEvent(
        user_id=user.id,
        entity_type="application",
        entity_id=entity_id,
        event_type="newest",
        description="Newest event",
        event_metadata={"rank": 3},
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    middle = ActivityEvent(
        user_id=user.id,
        entity_type="application",
        entity_id=entity_id,
        event_type="middle",
        description="Middle event",
        event_metadata={"rank": 2},
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    hidden = ActivityEvent(
        user_id=other_user.id,
        entity_type="application",
        entity_id=uuid.uuid4(),
        event_type="hidden",
        created_at=datetime(2026, 1, 4, tzinfo=UTC),
    )
    session.add_all([old, newest, middle, hidden])
    session.commit()

    resp = client.get("/api/dashboard/activity?limit=2")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [event["event_type"] for event in body] == ["newest", "middle"]
    assert body[0]["metadata"] == {"rank": 3}


def test_dashboard_requires_authentication(session):
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        resp = c.get("/api/dashboard/summary")
    app.dependency_overrides.clear()

    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authenticated"
