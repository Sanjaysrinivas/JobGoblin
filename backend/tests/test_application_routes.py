import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import (
    ActivityEvent,
    Application,
    Contact,
    CoverLetter,
    Job,
    OutreachMessage,
    Resume,
    ResumeVersion,
    User,
)
from app.models.enums import CoverLetterTone, OutreachChannel


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


def _cover_letter(session, user: User, job: Job, resume: Resume) -> CoverLetter:
    cover_letter = CoverLetter(
        user_id=user.id,
        job_id=job.id,
        resume_id=resume.id,
        content="Dear hiring team...",
        tone=CoverLetterTone.professional,
    )
    session.add(cover_letter)
    session.commit()
    session.refresh(cover_letter)
    return cover_letter


def test_create_list_update_and_delete_application(client, session, user):
    job = _job(session, user)
    resume = _resume(session, user)
    cover_letter = _cover_letter(session, user, job, resume)
    follow_up_at = datetime.now(UTC) + timedelta(days=7)

    created = client.post(
        "/api/applications",
        json={
            "job_id": str(job.id),
            "resume_id": str(resume.id),
            "cover_letter_id": str(cover_letter.id),
            "status": "saved",
            "follow_up_at": follow_up_at.isoformat(),
            "notes": "  Follow up next week.  ",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["job"]["company_name"] == "Acme"
    assert body["notes"] == "Follow up next week."

    stored = session.get(Application, uuid.UUID(body["id"]))
    assert stored is not None
    assert stored.user_id == user.id

    events = session.exec(select(ActivityEvent)).all()
    assert len(events) == 1
    assert events[0].event_type == "application_created"
    assert events[0].user_id == user.id

    updated = client.patch(
        f"/api/applications/{body['id']}",
        json={"status": "applied", "notes": "Applied via company site."},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "applied"

    events = session.exec(select(ActivityEvent).order_by(ActivityEvent.created_at)).all()
    assert [event.event_type for event in events] == [
        "application_created",
        "application_status_changed",
    ]
    assert events[-1].event_metadata == {"from": "saved", "to": "applied"}

    listed = client.get("/api/applications")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [body["id"]]

    deleted = client.delete(f"/api/applications/{body['id']}")
    assert deleted.status_code == 204
    assert session.get(Application, uuid.UUID(body["id"])) is None


def test_rejects_duplicate_application_for_same_user_job(client, session, user):
    job = _job(session, user)

    first = client.post("/api/applications", json={"job_id": str(job.id)})
    assert first.status_code == 201, first.text

    duplicate = client.post("/api/applications", json={"job_id": str(job.id)})
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "application_exists"


def test_list_returns_only_current_users_applications(client, session, user, other_user):
    mine = _job(session, user, company_name="MineCo")
    theirs = _job(session, other_user, company_name="TheirCo")
    session.add(Application(user_id=other_user.id, job_id=theirs.id))
    session.commit()

    created = client.post("/api/applications", json={"job_id": str(mine.id)})
    assert created.status_code == 201

    listed = client.get("/api/applications")
    assert listed.status_code == 200
    assert [item["job"]["company_name"] for item in listed.json()] == ["MineCo"]


def test_cross_user_detail_update_and_delete_are_404(client, session, other_user):
    other_job = _job(session, other_user)
    application = Application(user_id=other_user.id, job_id=other_job.id)
    session.add(application)
    session.commit()
    session.refresh(application)

    detail = client.get(f"/api/applications/{application.id}")
    assert detail.status_code == 404
    assert detail.json()["code"] == "application_not_found"

    updated = client.patch(f"/api/applications/{application.id}", json={"status": "applied"})
    assert updated.status_code == 404

    deleted = client.delete(f"/api/applications/{application.id}")
    assert deleted.status_code == 404


def test_detail_rejects_application_linked_to_cross_user_job(client, session, user, other_user):
    other_job = _job(session, other_user)
    application = Application(user_id=user.id, job_id=other_job.id)
    session.add(application)
    session.commit()
    session.refresh(application)

    detail = client.get(f"/api/applications/{application.id}")
    assert detail.status_code == 404
    assert detail.json()["code"] == "application_not_found"


def test_create_enforces_owned_references(client, session, user, other_user):
    own_job = _job(session, user)
    own_second_job = _job(session, user, title="Frontend Engineer")
    other_job = _job(session, other_user)
    other_resume = _resume(session, other_user)
    own_resume = _resume(session, user)
    mismatched_cover_letter = _cover_letter(session, user, own_second_job, own_resume)
    other_cover_letter = _cover_letter(session, other_user, other_job, other_resume)

    missing_job = client.post("/api/applications", json={"job_id": str(other_job.id)})
    assert missing_job.status_code == 404
    assert missing_job.json()["code"] == "job_not_found"

    missing_resume = client.post(
        "/api/applications",
        json={"job_id": str(own_job.id), "resume_id": str(other_resume.id)},
    )
    assert missing_resume.status_code == 404
    assert missing_resume.json()["code"] == "resume_not_found"

    missing_cover_letter = client.post(
        "/api/applications",
        json={"job_id": str(own_job.id), "cover_letter_id": str(other_cover_letter.id)},
    )
    assert missing_cover_letter.status_code == 404
    assert missing_cover_letter.json()["code"] == "cover_letter_not_found"

    mismatch = client.post(
        "/api/applications",
        json={
            "job_id": str(own_job.id),
            "cover_letter_id": str(mismatched_cover_letter.id),
        },
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["code"] == "cover_letter_job_mismatch"


def test_patch_rejects_null_status(client, session, user):
    job = _job(session, user)
    created = client.post("/api/applications", json={"job_id": str(job.id)}).json()

    resp = client.patch(f"/api/applications/{created['id']}", json={"status": None})
    assert resp.status_code == 422
    assert resp.json()["code"] == "invalid_application_status"


def test_requires_authentication(session):
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        resp = c.get("/api/applications")
    app.dependency_overrides.clear()

    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authenticated"


def test_application_workflow_includes_owned_job_artifacts(client, session, user, other_user):
    job = _job(session, user)
    resume = _resume(session, user)
    version = ResumeVersion(
        resume_id=resume.id,
        title="Workflow Resume",
        extracted_text="Python APIs",
        parsed_json={},
        is_current=True,
    )
    tailored_draft = ResumeVersion(
        resume_id=resume.id,
        job_id=job.id,
        source_version_id=version.id,
        title="Acme Tailored Draft",
        extracted_text="Python APIs\n\nTailoring notes",
        parsed_json={"tailoring": {"suggested_changes": []}},
        is_current=False,
    )
    cover_letter = _cover_letter(session, user, job, resume)
    contact = Contact(
        user_id=user.id,
        job_id=job.id,
        name="Taylor Recruiter",
        email="taylor@example.com",
    )
    outreach = OutreachMessage(
        user_id=user.id,
        job_id=job.id,
        contact_id=contact.id,
        channel=OutreachChannel.email,
        message_type="intro",
        content="Hello",
    )
    other_job = _job(session, other_user, company_name="OtherCo")
    other_contact = Contact(user_id=other_user.id, job_id=other_job.id, name="Private")
    session.add(version)
    session.add(tailored_draft)
    session.add(contact)
    session.add(outreach)
    session.add(other_contact)
    session.commit()

    created = client.post(
        "/api/applications",
        json={
            "job_id": str(job.id),
            "resume_id": str(resume.id),
            "cover_letter_id": str(cover_letter.id),
        },
    )
    assert created.status_code == 201, created.text

    workflow = client.get(f"/api/applications/{created.json()['id']}/workflow")
    assert workflow.status_code == 200, workflow.text
    body = workflow.json()
    assert body["job"]["id"] == str(job.id)
    assert body["linked_resume"]["current_version_id"] == str(version.id)
    assert body["linked_resume"]["current_version_title"] == "Workflow Resume"
    assert body["linked_resume"]["tailored_draft"]["id"] == str(tailored_draft.id)
    assert body["linked_resume"]["tailored_draft"]["source_version_id"] == str(version.id)
    assert body["next_action"] == {"label": "Review saved job", "due_at": None, "due": False}
    assert body["linked_cover_letter"]["id"] == str(cover_letter.id)
    assert [item["id"] for item in body["cover_letters"]] == [str(cover_letter.id)]
    assert [item["id"] for item in body["contacts"]] == [str(contact.id)]
    assert [item["id"] for item in body["outreach_drafts"]] == [str(outreach.id)]
    assert "Private" not in str(body)
    assert body["recent_activity"][0]["event_type"] == "application_created"