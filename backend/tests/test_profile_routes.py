import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import Profile, Resume, User


@pytest.fixture
def user(session) -> User:
    u = User(email="owner-profile@example.com", password_hash="x", display_name="Owner")
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


def _resume(session, user: User, *, parsed_json: dict | None) -> Resume:
    resume = Resume(
        user_id=user.id,
        title="Base Resume",
        original_filename="base.pdf",
        file_key=f"{user.id}/base.pdf",
        content_type="application/pdf",
        file_size=10,
        parsed_json=parsed_json,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def test_get_profile_missing_is_404(client):
    resp = client.get("/api/profile")
    assert resp.status_code == 404
    assert resp.json()["code"] == "profile_not_found"


def test_save_profile_creates_private_profile(client, session, user):
    resp = client.put(
        "/api/profile",
        json={
            "full_name": "Ada Lovelace",
            "headline": "Backend Engineer",
            "location": "Remote",
            "website_url": "https://example.com",
            "linkedin_url": "https://linkedin.com/in/ada",
            "summary": "Builds reliable systems.",
            "skills": ["Python", "FastAPI"],
            "experience": [
                {
                    "company": "Analytical Engines",
                    "role": "Engineer",
                    "start": "2022",
                    "end": None,
                    "highlights": ["Shipped APIs"],
                }
            ],
            "education": [],
            "projects": ["Profile Builder"],
            "certifications": [],
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["full_name"] == "Ada Lovelace"
    assert body["skills"] == ["Python", "FastAPI"]

    stored = session.get(Profile, uuid.UUID(body["id"]))
    assert stored is not None
    assert stored.user_id == user.id

    get_resp = client.get("/api/profile")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == body["id"]


def test_seed_profile_from_owned_parsed_resume(client, session, user):
    resume = _resume(
        session,
        user,
        parsed_json={
            "summary": "API-focused engineer.",
            "skills": ["Python", "SQL", ""],
            "experience": [
                {
                    "company": "Goblin Labs",
                    "role": "Developer",
                    "start": "2021",
                    "end": "2024",
                    "highlights": ["Built parsers", ""],
                }
            ],
            "education": [{"institution": "State", "credential": "BS CS", "year": "2020"}],
            "projects": ["Resume Parser"],
            "certifications": ["AWS"],
        },
    )

    resp = client.post("/api/profile/seed", json={"resume_id": str(resume.id)})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_resume_id"] == str(resume.id)
    assert body["summary"] == "API-focused engineer."
    assert body["skills"] == ["Python", "SQL"]
    assert body["experience"][0]["highlights"] == ["Built parsers"]
    assert body["education"][0]["credential"] == "BS CS"


def test_seed_rejects_unparsed_resume(client, session, user):
    resume = _resume(session, user, parsed_json=None)

    resp = client.post("/api/profile/seed", json={"resume_id": str(resume.id)})

    assert resp.status_code == 400
    assert resp.json()["code"] == "resume_not_parsed"


def test_seed_other_users_resume_is_404(client, session):
    other = User(email="other-profile@example.com", password_hash="x", display_name="Other")
    session.add(other)
    session.commit()
    session.refresh(other)
    resume = _resume(session, other, parsed_json={"summary": "Private"})

    resp = client.post("/api/profile/seed", json={"resume_id": str(resume.id)})

    assert resp.status_code == 404
    assert resp.json()["code"] == "resume_not_found"


def test_delete_profile(client):
    created = client.put("/api/profile", json={"summary": "temporary"})
    assert created.status_code == 200

    deleted = client.delete("/api/profile")
    assert deleted.status_code == 204

    assert client.get("/api/profile").status_code == 404