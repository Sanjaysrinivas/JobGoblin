import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import Contact, Job, User


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
def owned_job(session, user) -> Job:
    job = Job(
        user_id=user.id,
        company_name="Acme",
        title="Backend Engineer",
        description="Build reliable backend services.",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@pytest.fixture
def other_job(session, other_user) -> Job:
    job = Job(
        user_id=other_user.id,
        company_name="OtherCo",
        title="Private Role",
        description="Do not leak.",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@pytest.fixture
def client(session, user):
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _contact_payload(**overrides):
    payload = {
        "name": "Taylor Recruiter",
        "company": "Acme",
        "role": "Technical Recruiter",
        "email": "taylor@example.com",
        "linkedin_url": "https://www.linkedin.com/in/taylor",
        "notes": "Met through a referral.",
        "contacted": False,
    }
    payload.update(overrides)
    return payload


def _create_contact(client, **overrides):
    return client.post("/api/contacts", json=_contact_payload(**overrides))


def test_create_get_update_delete_contact(client, session, user, owned_job):
    created = _create_contact(client, job_id=str(owned_job.id))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "Taylor Recruiter"
    assert body["job_id"] == str(owned_job.id)
    assert body["contacted"] is False

    spaced = _create_contact(
        client,
        name="  Morgan Referral  ",
        email="  morgan@example.com  ",
        notes="   ",
    )
    assert spaced.status_code == 201, spaced.text
    assert spaced.json()["name"] == "Morgan Referral"
    assert spaced.json()["email"] == "morgan@example.com"
    assert spaced.json()["notes"] is None

    contact_id = uuid.UUID(body["id"])
    stored = session.get(Contact, contact_id)
    assert stored is not None
    assert stored.user_id == user.id

    detail = client.get(f"/api/contacts/{contact_id}")
    assert detail.status_code == 200
    assert detail.json()["email"] == "taylor@example.com"

    updated = client.patch(
        f"/api/contacts/{contact_id}",
        json={
            "role": "Recruiting Lead",
            "contacted": True,
            "job_id": None,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["role"] == "Recruiting Lead"
    assert updated.json()["contacted"] is True
    assert updated.json()["job_id"] is None

    deleted = client.delete(f"/api/contacts/{contact_id}")
    assert deleted.status_code == 204
    assert session.get(Contact, contact_id) is None


def test_list_returns_only_current_users_contacts(client, session, user, other_user):
    mine = _create_contact(client, name="Mine").json()
    session.add(Contact(user_id=other_user.id, name="Their Contact"))
    session.commit()

    resp = client.get("/api/contacts")
    assert resp.status_code == 200
    names = [contact["name"] for contact in resp.json()]
    assert names == [mine["name"]]


def test_cross_user_detail_update_and_delete_are_404(client, session, other_user):
    contact = Contact(user_id=other_user.id, name="Private Contact")
    session.add(contact)
    session.commit()
    session.refresh(contact)

    detail = client.get(f"/api/contacts/{contact.id}")
    assert detail.status_code == 404
    assert detail.json()["code"] == "contact_not_found"

    updated = client.patch(f"/api/contacts/{contact.id}", json={"name": "Leaked"})
    assert updated.status_code == 404

    deleted = client.delete(f"/api/contacts/{contact.id}")
    assert deleted.status_code == 404

    session.refresh(contact)
    assert contact.name == "Private Contact"


def test_unknown_contact_is_404(client):
    resp = client.get(f"/api/contacts/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["code"] == "contact_not_found"


def test_create_accepts_unlinked_contact(client):
    resp = _create_contact(client, job_id=None)
    assert resp.status_code == 201, resp.text
    assert resp.json()["job_id"] is None


def test_create_rejects_unknown_job(client):
    resp = _create_contact(client, job_id=str(uuid.uuid4()))
    assert resp.status_code == 404
    assert resp.json()["code"] == "job_not_found"


def test_create_rejects_cross_user_job(client, other_job):
    resp = _create_contact(client, job_id=str(other_job.id))
    assert resp.status_code == 404
    assert resp.json()["code"] == "job_not_found"


def test_patch_rejects_cross_user_job(client, other_job):
    created = _create_contact(client).json()
    resp = client.patch(
        f"/api/contacts/{created['id']}",
        json={"job_id": str(other_job.id)},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "job_not_found"


def test_patch_accepts_owned_job(client, owned_job):
    created = _create_contact(client).json()
    resp = client.patch(
        f"/api/contacts/{created['id']}",
        json={"job_id": str(owned_job.id)},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["job_id"] == str(owned_job.id)


def test_patch_rejects_blank_name(client):
    created = _create_contact(client).json()
    resp = client.patch(f"/api/contacts/{created['id']}", json={"name": "   "})
    assert resp.status_code == 422


def test_create_rejects_blank_name(client):
    resp = _create_contact(client, name="   ")
    assert resp.status_code == 422


def test_requires_authentication(session):
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        resp = c.get("/api/contacts")
    app.dependency_overrides.clear()

    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authenticated"
