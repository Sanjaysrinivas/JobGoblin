import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import ActivityEvent, Contact, Job, OutreachMessage, User
from app.models.enums import OutreachChannel


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


def _contact(session, user: User, **overrides) -> Contact:
    contact = Contact(
        user_id=user.id,
        name=overrides.pop("name", "Taylor Recruiter"),
        email=overrides.pop("email", "taylor@example.com"),
        **overrides,
    )
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


def _payload(**overrides):
    payload = {
        "channel": "email",
        "message_type": "recruiter_intro",
        "content": "Hello Taylor, I am interested in the role.",
        "status": "draft",
    }
    payload.update(overrides)
    return payload


def test_create_list_update_copy_and_delete_outreach(client, session, user):
    job = _job(session, user)
    contact = _contact(session, user, job_id=job.id)

    created = client.post(
        "/api/outreach",
        json=_payload(job_id=str(job.id), contact_id=str(contact.id), content="  Hello.  "),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["content"] == "Hello."
    assert body["job"]["company_name"] == "Acme"
    assert body["contact"]["name"] == "Taylor Recruiter"
    assert body["status"] == "draft"

    stored = session.get(OutreachMessage, uuid.UUID(body["id"]))
    assert stored is not None
    assert stored.user_id == user.id

    events = session.exec(select(ActivityEvent).order_by(ActivityEvent.created_at)).all()
    assert [event.event_type for event in events] == ["outreach_created"]

    copied = client.patch(f"/api/outreach/{body['id']}", json={"status": "copied"})
    assert copied.status_code == 200, copied.text
    assert copied.json()["status"] == "copied"

    events = session.exec(select(ActivityEvent).order_by(ActivityEvent.created_at)).all()
    assert [event.event_type for event in events] == [
        "outreach_created",
        "outreach_copied",
    ]
    assert events[-1].event_metadata == {"from": "draft", "to": "copied"}

    edited = client.patch(
        f"/api/outreach/{body['id']}",
        json={"message_type": "follow_up", "content": "Checking in."},
    )
    assert edited.status_code == 200
    assert edited.json()["message_type"] == "follow_up"

    listed = client.get("/api/outreach")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [body["id"]]

    deleted = client.delete(f"/api/outreach/{body['id']}")
    assert deleted.status_code == 204
    assert session.get(OutreachMessage, uuid.UUID(body["id"])) is None


def test_list_returns_only_current_users_outreach(client, session, user, other_user):
    mine_job = _job(session, user, company_name="MineCo")
    other_job = _job(session, other_user, company_name="TheirCo")
    session.add(
        OutreachMessage(
            user_id=other_user.id,
            job_id=other_job.id,
            channel=OutreachChannel.email,
            message_type="private",
            content="Do not leak.",
        )
    )
    session.commit()

    created = client.post("/api/outreach", json=_payload(job_id=str(mine_job.id)))
    assert created.status_code == 201

    listed = client.get("/api/outreach")
    assert listed.status_code == 200
    assert [item["job"]["company_name"] for item in listed.json()] == ["MineCo"]


def test_cross_user_detail_update_and_delete_are_404(client, session, other_user):
    outreach = OutreachMessage(
        user_id=other_user.id,
        channel=OutreachChannel.linkedin,
        message_type="intro",
        content="Private draft.",
    )
    session.add(outreach)
    session.commit()
    session.refresh(outreach)

    detail = client.get(f"/api/outreach/{outreach.id}")
    assert detail.status_code == 404
    assert detail.json()["code"] == "outreach_not_found"

    updated = client.patch(f"/api/outreach/{outreach.id}", json={"status": "copied"})
    assert updated.status_code == 404

    deleted = client.delete(f"/api/outreach/{outreach.id}")
    assert deleted.status_code == 404


def test_create_enforces_owned_references(client, session, other_user):
    other_job = _job(session, other_user)
    other_contact = _contact(session, other_user)

    missing_job = client.post("/api/outreach", json=_payload(job_id=str(other_job.id)))
    assert missing_job.status_code == 404
    assert missing_job.json()["code"] == "job_not_found"

    missing_contact = client.post("/api/outreach", json=_payload(contact_id=str(other_contact.id)))
    assert missing_contact.status_code == 404
    assert missing_contact.json()["code"] == "contact_not_found"


def test_patch_rejects_cross_user_references(client, session, other_user):
    created = client.post("/api/outreach", json=_payload()).json()
    other_job = _job(session, other_user)
    other_contact = _contact(session, other_user)

    job_resp = client.patch(f"/api/outreach/{created['id']}", json={"job_id": str(other_job.id)})
    assert job_resp.status_code == 404
    assert job_resp.json()["code"] == "job_not_found"

    contact_resp = client.patch(
        f"/api/outreach/{created['id']}", json={"contact_id": str(other_contact.id)}
    )
    assert contact_resp.status_code == 404
    assert contact_resp.json()["code"] == "contact_not_found"


def test_validation_rejects_blank_and_null_required_fields(client):
    blank = client.post("/api/outreach", json=_payload(content="   "))
    assert blank.status_code == 422

    created = client.post("/api/outreach", json=_payload()).json()

    null_status = client.patch(f"/api/outreach/{created['id']}", json={"status": None})
    assert null_status.status_code == 422

    null_content = client.patch(f"/api/outreach/{created['id']}", json={"content": None})
    assert null_content.status_code == 422


def test_patch_records_generic_status_transition(client, session):
    created = client.post("/api/outreach", json=_payload()).json()

    resp = client.patch(f"/api/outreach/{created['id']}", json={"status": "closed"})
    assert resp.status_code == 200

    events = session.exec(select(ActivityEvent).order_by(ActivityEvent.created_at)).all()
    assert [event.event_type for event in events] == [
        "outreach_created",
        "outreach_status_changed",
    ]
    assert events[-1].event_metadata == {"from": "draft", "to": "closed"}


def test_requires_authentication(session):
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as c:
            resp = c.get("/api/outreach")

        assert resp.status_code == 401
        assert resp.json()["code"] == "not_authenticated"
    finally:
        app.dependency_overrides.clear()


def test_email_export_returns_mailto_text_and_records_activity(client, session, user):
    job = _job(session, user)
    contact = _contact(session, user, job_id=job.id, email="taylor@example.com")
    created = client.post(
        "/api/outreach",
        json=_payload(job_id=str(job.id), contact_id=str(contact.id), content="Hello Taylor"),
    )
    assert created.status_code == 201, created.text

    exported = client.post(f"/api/outreach/{created.json()['id']}/email-export")
    assert exported.status_code == 200, exported.text
    body = exported.json()
    assert body["to"] == "taylor@example.com"
    assert body["subject"] == "Backend Engineer at Acme"
    assert body["body"] == "Hello Taylor"
    assert body["mailto_url"].startswith("mailto:taylor%40example.com?")
    assert "subject=Backend%20Engineer%20at%20Acme" in body["mailto_url"]
    assert (
        body["text"] == "To: taylor@example.com\nSubject: Backend Engineer at Acme\n\nHello Taylor"
    )
    assert body["filename"].startswith("outreach-recruiter_intro-")

    events = session.exec(select(ActivityEvent).order_by(ActivityEvent.created_at)).all()
    assert events[-1].event_type == "outreach_email_exported"
    assert events[-1].entity_id == uuid.UUID(created.json()["id"])


def test_email_export_rejects_non_email_outreach(client):
    created = client.post("/api/outreach", json=_payload(channel="linkedin"))
    assert created.status_code == 201, created.text

    exported = client.post(f"/api/outreach/{created.json()['id']}/email-export")
    assert exported.status_code == 422
    assert exported.json()["code"] == "not_email_outreach"
