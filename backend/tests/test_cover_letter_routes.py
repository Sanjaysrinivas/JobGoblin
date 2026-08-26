import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.models import ActivityEvent, Application, CoverLetter, Job, Resume, ResumeVersion, User
from app.models.enums import ApplicationStatus


@pytest.fixture(autouse=True)
def _mock_ai(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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
        "description": "Build APIs with Python and PostgreSQL.",
    }
    values.update(overrides)
    job = Job(**values)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _resume(session, user: User, **overrides) -> Resume:
    values = {
        "user_id": user.id,
        "title": "Backend Resume",
        "original_filename": "resume.pdf",
        "file_key": f"{user.id}/resume.pdf",
        "content_type": "application/pdf",
        "file_size": 123,
        "extracted_text": "Backend engineer with Python and PostgreSQL experience.",
    }
    values.update(overrides)
    resume = Resume(**values)
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def test_create_list_get_and_update_cover_letter(client, session, user):
    job = _job(session, user)
    resume = _resume(session, user)

    created = client.post(
        "/api/cover-letters",
        json={
            "job_id": str(job.id),
            "resume_id": str(resume.id),
            "tone": "concise",
        },
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["job_id"] == str(job.id)
    assert body["resume_id"] == str(resume.id)
    assert body["tone"] == "concise"
    assert body["status"] == "draft"
    assert body["content"].startswith("Dear Hiring Team,")
    assert "Backend engineer with Python and PostgreSQL experience." in body["content"]

    stored = session.get(CoverLetter, uuid.UUID(body["id"]))
    assert stored is not None
    assert stored.user_id == user.id

    events = session.exec(select(ActivityEvent)).all()
    assert [event.event_type for event in events] == ["cover_letter_created"]
    assert events[0].event_metadata == {"tone": "concise", "status": "draft"}

    listed = client.get("/api/cover-letters")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [body["id"]]

    detail = client.get(f"/api/cover-letters/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == body["id"]

    updated = client.patch(
        f"/api/cover-letters/{body['id']}",
        json={"content": "  Edited local draft.  ", "status": "reviewed"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["content"] == "Edited local draft."
    assert updated.json()["status"] == "reviewed"

    events = session.exec(select(ActivityEvent).order_by(ActivityEvent.created_at)).all()
    assert [event.event_type for event in events] == [
        "cover_letter_created",
        "cover_letter_status_changed",
    ]
    assert events[-1].event_metadata == {"from": "draft", "to": "reviewed"}


def test_create_enforces_owned_job_and_resume(client, session, user, other_user):
    own_job = _job(session, user)
    own_resume = _resume(session, user)
    other_job = _job(session, other_user)
    other_resume = _resume(session, other_user)

    other_job_resp = client.post(
        "/api/cover-letters",
        json={"job_id": str(other_job.id), "resume_id": str(own_resume.id)},
    )
    assert other_job_resp.status_code == 404
    assert other_job_resp.json()["code"] == "job_not_found"

    other_resume_resp = client.post(
        "/api/cover-letters",
        json={"job_id": str(own_job.id), "resume_id": str(other_resume.id)},
    )
    assert other_resume_resp.status_code == 404
    assert other_resume_resp.json()["code"] == "resume_not_found"


def test_cross_user_cover_letter_reads_and_updates_are_404(client, session, other_user):
    job = _job(session, other_user)
    resume = _resume(session, other_user)
    cover_letter = CoverLetter(
        user_id=other_user.id,
        job_id=job.id,
        resume_id=resume.id,
        content="Other user draft",
        tone="professional",
    )
    session.add(cover_letter)
    session.commit()
    session.refresh(cover_letter)

    detail = client.get(f"/api/cover-letters/{cover_letter.id}")
    assert detail.status_code == 404
    assert detail.json()["code"] == "cover_letter_not_found"

    updated = client.patch(
        f"/api/cover-letters/{cover_letter.id}",
        json={"status": "reviewed"},
    )
    assert updated.status_code == 404


def test_list_can_filter_by_owned_job(client, session, user, other_user):
    own_job = _job(session, user)
    other_owned_job = _job(session, user, title="Frontend Engineer")
    foreign_job = _job(session, other_user)
    resume = _resume(session, user)

    mine = CoverLetter(
        user_id=user.id,
        job_id=own_job.id,
        resume_id=resume.id,
        content="Mine",
        tone="professional",
    )
    other_mine = CoverLetter(
        user_id=user.id,
        job_id=other_owned_job.id,
        resume_id=resume.id,
        content="Other mine",
        tone="professional",
    )
    foreign = CoverLetter(
        user_id=other_user.id,
        job_id=foreign_job.id,
        resume_id=_resume(session, other_user).id,
        content="Foreign",
        tone="professional",
    )
    session.add_all([mine, other_mine, foreign])
    session.commit()
    session.refresh(mine)

    listed = client.get(f"/api/cover-letters?job_id={own_job.id}")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [str(mine.id)]

    foreign_filter = client.get(f"/api/cover-letters?job_id={foreign_job.id}")
    assert foreign_filter.status_code == 404
    assert foreign_filter.json()["code"] == "job_not_found"


def test_rejects_resume_without_content_and_blank_update(client, session, user):
    job = _job(session, user)
    empty_resume = _resume(session, user, extracted_text=None, parsed_json=None)

    created = client.post(
        "/api/cover-letters",
        json={"job_id": str(job.id), "resume_id": str(empty_resume.id)},
    )
    assert created.status_code == 400
    assert created.json()["code"] == "no_resume_content"

    resume = _resume(session, user)
    ok = client.post(
        "/api/cover-letters",
        json={"job_id": str(job.id), "resume_id": str(resume.id)},
    ).json()
    blank = client.patch(f"/api/cover-letters/{ok['id']}", json={"content": "   "})
    assert blank.status_code == 422
    assert blank.json()["code"] == "invalid_cover_letter_content"

    null_status = client.patch(f"/api/cover-letters/{ok['id']}", json={"status": None})
    assert null_status.status_code == 422
    assert null_status.json()["code"] == "invalid_cover_letter_status"


def test_requires_authentication(session):
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        resp = c.get("/api/cover-letters")
    app.dependency_overrides.clear()

    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authenticated"


def test_create_cover_letter_uses_current_resume_version(client, session, user, monkeypatch):
    prompts: list[str] = []

    class CaptureProvider:
        async def generate_text(self, prompt, *, system=None):
            prompts.append(prompt)
            return "Draft from captured provider"

        async def generate_json(self, prompt, schema, *, system=None):
            prompts.append(prompt)
            return {}

    import app.api.routes.cover_letters as cover_letter_routes

    monkeypatch.setattr(cover_letter_routes, "get_ai_provider", lambda: CaptureProvider())
    job = _job(session, user)
    resume = _resume(session, user, extracted_text="Base resume text")
    session.add(
        ResumeVersion(
            resume_id=resume.id,
            title="Current",
            extracted_text="Current resume version text",
            parsed_json={"skills": ["Python"]},
            is_current=True,
        )
    )
    session.commit()

    resp = client.post(
        "/api/cover-letters",
        json={"job_id": str(job.id), "resume_id": str(resume.id), "tone": "concise"},
    )

    assert resp.status_code == 201, resp.text
    assert "Current resume version text" in resp.json()["content"]
    assert "Current resume version text" in prompts[0]
    assert "Base resume text" not in prompts[0]


def test_create_cover_letter_links_existing_application(client, session, user):
    job = _job(session, user)
    resume = _resume(session, user)
    application = Application(user_id=user.id, job_id=job.id)
    session.add(application)
    session.commit()

    response = client.post(
        "/api/cover-letters",
        json={"job_id": str(job.id), "resume_id": str(resume.id)},
    )

    assert response.status_code == 201
    session.refresh(application)
    assert application.resume_id == resume.id
    assert application.cover_letter_id == uuid.UUID(response.json()["id"])
    assert application.status == ApplicationStatus.cover_letter_created
