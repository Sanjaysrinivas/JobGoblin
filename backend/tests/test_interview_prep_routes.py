
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import (
    ActivityEvent,
    Application,
    InterviewPrep,
    Job,
    Profile,
    Resume,
    ResumeVersion,
    User,
)


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
    job = Job(
        user_id=user.id,
        company_name=overrides.pop("company_name", "Acme"),
        title=overrides.pop("title", "Backend Engineer"),
        description=overrides.pop("description", "Build reliable services."),
        **overrides,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _resume_version(session, user: User) -> tuple[Resume, ResumeVersion]:
    resume = Resume(
        user_id=user.id,
        title="Baseline",
        original_filename="resume.pdf",
        file_key=f"{user.id}/resume.pdf",
        content_type="application/pdf",
        file_size=123,
        extracted_text="Alice Engineer\nPython APIs",
        parsed_json={},
    )
    version = ResumeVersion(
        resume_id=resume.id,
        title="Current",
        extracted_text="Current Python APIs",
        parsed_json={},
        is_current=True,
    )
    session.add(resume)
    session.add(version)
    session.commit()
    session.refresh(resume)
    session.refresh(version)
    return resume, version


def test_create_list_get_and_patch_interview_prep(client, session, user):
    job = _job(session, user)
    resume, version = _resume_version(session, user)
    application = Application(
        user_id=user.id,
        job_id=job.id,
        resume_id=resume.id,
        notes="Ask about platform ownership.",
    )
    session.add(
        Profile(
            user_id=user.id,
            headline="Backend platform engineer",
            skills=["Python", "FastAPI"],
            projects=["Reduced API latency by 30%"],
        )
    )
    session.add(application)
    session.commit()
    session.refresh(application)

    created = client.post(
        "/api/interview-prep",
        json={
            "job_id": str(job.id),
            "application_id": str(application.id),
            "resume_version_id": str(version.id),
            "notes": "  Prep notes  ",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "draft"
    assert body["resume_id"] == str(resume.id)
    assert body["resume_version_id"] == str(version.id)
    assert body["notes"] == "Prep notes"
    assert body["provider"] == "mock"
    assert body["model_used"] == "deterministic"
    assert {"question", "category", "why", "answer_outline", "evidence"} <= set(
        body["questions"][0]
    )
    assert "story_bank" in {question["category"] for question in body["questions"]}
    evidence = {item for question in body["questions"] for item in question["evidence"]}
    assert "Current Python APIs" in evidence
    assert "Backend platform engineer" in evidence
    assert "Ask about platform ownership." in evidence
    assert "Prep notes" in evidence

    listed = client.get(f"/api/interview-prep?job_id={job.id}")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [body["id"]]

    detail = client.get(f"/api/interview-prep/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == body["id"]

    patched = client.patch(f"/api/interview-prep/{body['id']}", json={"status": "ready"})
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "ready"

    notes_patch = client.patch(
        f"/api/interview-prep/{body['id']}", json={"notes": "Round 1 with hiring manager"}
    )
    assert notes_patch.status_code == 200
    assert notes_patch.json()["notes"] == "Round 1 with hiring manager"

    null_questions = client.patch(f"/api/interview-prep/{body['id']}", json={"questions": None})
    assert null_questions.status_code == 422

    events = session.exec(select(ActivityEvent).order_by(ActivityEvent.created_at)).all()
    assert [event.event_type for event in events] == [
        "interview_prep_created",
        "interview_prep_status_changed",
        "interview_prep_notes_updated",
    ]
    assert events[-2].event_metadata == {"from": "draft", "to": "ready"}
    assert events[-1].event_metadata is None


def test_interview_prep_validates_owned_references(client, session, user, other_user):
    job = _job(session, user)
    other_job = _job(session, other_user)
    other_resume, other_version = _resume_version(session, other_user)
    application = Application(user_id=user.id, job_id=job.id)
    mismatched_application = Application(
        user_id=user.id, job_id=_job(session, user, title="Other").id
    )
    session.add(application)
    session.add(mismatched_application)
    session.commit()
    session.refresh(application)
    session.refresh(mismatched_application)

    cross_job = client.post("/api/interview-prep", json={"job_id": str(other_job.id)})
    assert cross_job.status_code == 404
    assert cross_job.json()["code"] == "job_not_found"

    cross_resume = client.post(
        "/api/interview-prep",
        json={"job_id": str(job.id), "resume_id": str(other_resume.id)},
    )
    assert cross_resume.status_code == 404
    assert cross_resume.json()["code"] == "resume_not_found"

    cross_version = client.post(
        "/api/interview-prep",
        json={"job_id": str(job.id), "resume_version_id": str(other_version.id)},
    )
    assert cross_version.status_code == 404
    assert cross_version.json()["code"] == "resume_version_not_found"

    mismatch = client.post(
        "/api/interview-prep",
        json={"job_id": str(job.id), "application_id": str(mismatched_application.id)},
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["code"] == "application_job_mismatch"

    prep = InterviewPrep(user_id=other_user.id, job_id=other_job.id, questions=[])
    session.add(prep)
    session.commit()
    session.refresh(prep)
    detail = client.get(f"/api/interview-prep/{prep.id}")
    assert detail.status_code == 404

    listed = client.get(f"/api/interview-prep?application_id={application.id}")
    assert listed.status_code == 200
    assert listed.json() == []
