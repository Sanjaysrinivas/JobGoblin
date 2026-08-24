import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import Job, User


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


def _job_payload(**overrides):
    payload = {
        "company_name": "Acme",
        "title": "Backend Engineer",
        "location": "Remote",
        "work_mode": "remote",
        "source": "linkedin",
        "source_url": "https://example.com/jobs/1",
        "description": "Build reliable backend services.",
        "salary_min": 120000,
        "salary_max": 150000,
        "currency": "usd",
        "priority": "high",
    }
    payload.update(overrides)
    return payload


def _create_job(client, **overrides):
    return client.post("/api/jobs", json=_job_payload(**overrides))


def test_create_get_update_delete_job(client, session, user):
    created = _create_job(client)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["company_name"] == "Acme"
    assert body["work_mode"] == "remote"
    assert body["source"] == "linkedin"
    assert body["priority"] == "high"
    assert body["currency"] == "USD"

    spaced = _create_job(
        client,
        company_name="  TrimCo  ",
        title="  Platform Engineer  ",
        currency=" usd ",
    )
    assert spaced.status_code == 201, spaced.text
    assert spaced.json()["company_name"] == "TrimCo"
    assert spaced.json()["title"] == "Platform Engineer"
    assert spaced.json()["currency"] == "USD"

    job_id = uuid.UUID(body["id"])
    stored = session.get(Job, job_id)
    assert stored is not None
    assert stored.user_id == user.id

    detail = client.get(f"/api/jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Backend Engineer"

    updated = client.patch(
        f"/api/jobs/{job_id}",
        json={
            "title": "Senior Backend Engineer",
            "priority": "medium",
            "salary_min": 130000,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Senior Backend Engineer"
    assert updated.json()["priority"] == "medium"
    assert updated.json()["salary_max"] == 150000

    deleted = client.delete(f"/api/jobs/{job_id}")
    assert deleted.status_code == 204
    assert session.get(Job, job_id) is None


def test_list_returns_only_current_users_jobs(client, session, user, other_user):
    mine = _create_job(client, company_name="MineCo").json()
    session.add(
        Job(
            user_id=other_user.id,
            company_name="TheirCo",
            title="Secret Role",
            description="Hidden job",
        )
    )
    session.commit()

    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    companies = [job["company_name"] for job in resp.json()]
    assert companies == [mine["company_name"]]


def test_cross_user_detail_update_and_delete_are_404(client, session, other_user):
    job = Job(
        user_id=other_user.id,
        company_name="OtherCo",
        title="Private Role",
        description="Do not leak",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    detail = client.get(f"/api/jobs/{job.id}")
    assert detail.status_code == 404
    assert detail.json()["code"] == "job_not_found"

    updated = client.patch(f"/api/jobs/{job.id}", json={"title": "Leaked"})
    assert updated.status_code == 404

    deleted = client.delete(f"/api/jobs/{job.id}")
    assert deleted.status_code == 404

    session.refresh(job)
    assert job.title == "Private Role"


def test_unknown_job_is_404(client):
    resp = client.get(f"/api/jobs/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["code"] == "job_not_found"


def test_create_rejects_invalid_enum(client):
    resp = _create_job(client, work_mode="teleport")
    assert resp.status_code == 422


def test_create_rejects_invalid_salary_range(client):
    resp = _create_job(client, salary_min=200000, salary_max=100000)
    assert resp.status_code == 422
    assert resp.json()["code"] == "invalid_salary_range"


def test_import_job_from_text_prefills_create_payload(client, monkeypatch):
    import app.api.routes.jobs as job_routes

    class Provider:
        async def generate_json(self, prompt, schema, *, system=None):
            return {
                "company_name": "Acme Data",
                "title": "Data Analyst",
                "location": "Milan, Italy",
                "work_mode": "hybrid",
                "source": "company_site",
                "description": "Analyze product data with SQL and dashboards.",
                "salary_min": 45000,
                "salary_max": 55000,
                "currency": "eur",
                "priority": "high",
            }

    monkeypatch.setattr(job_routes, "get_ai_provider", lambda: Provider())
    resp = client.post(
        "/api/jobs/import",
        json={
            "mode": "text",
            "content": "Data Analyst\nAcme Data\nMilan, Italy\nAnalyze product data.",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["company_name"] == "Acme Data"
    assert body["title"] == "Data Analyst"
    assert body["work_mode"] == "hybrid"
    assert body["currency"] == "EUR"


def test_import_job_keeps_full_description_and_explicit_salary(client, monkeypatch):
    import app.api.routes.jobs as job_routes

    class Provider:
        async def generate_json(self, prompt, schema, *, system=None):
            return {
                "company_name": "Ferrero",
                "title": "Data Scientist",
                "location": "",
                "work_mode": "remote",
                "source": "company_site",
                "description": "Short AI summary.",
                "priority": "medium",
            }

    posting = """
    Data Scientist
    Ferrero
    Alba, CN, IT (Hybrid)

    About the Role:
    We are looking for a Data Scientist to join the Global Data Science & AI team.
    Main Responsibilities:
    You will analyze diverse datasets and build advanced statistical and AI-driven models.
    About You:
    You hold a master's degree and bring experience in applied data science roles.
    What We Offer:
    The guaranteed minimum base annual gross salary is €43.249.
    """
    monkeypatch.setattr(job_routes, "get_ai_provider", lambda: Provider())

    resp = client.post("/api/jobs/import", json={"mode": "text", "content": posting})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "Main Responsibilities" in body["description"]
    assert body["location"] == "Alba, CN, IT (Hybrid)"
    assert body["work_mode"] == "hybrid"
    assert body["salary_min"] == 43249
    assert body["currency"] == "EUR"


def test_import_job_rejects_private_url(client):
    resp = client.post(
        "/api/jobs/import",
        json={"mode": "url", "content": "http://127.0.0.1:8000/private"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "bad_url"


def test_patch_rejects_blank_required_field(client):
    created = _create_job(client).json()
    resp = client.patch(f"/api/jobs/{created['id']}", json={"title": "   "})
    assert resp.status_code == 422


def test_patch_rejects_invalid_persisted_salary_range(client):
    created = _create_job(client, salary_min=100000, salary_max=120000).json()
    resp = client.patch(f"/api/jobs/{created['id']}", json={"salary_min": 130000})
    assert resp.status_code == 422
    assert resp.json()["code"] == "invalid_salary_range"


def test_requires_authentication(session):
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        resp = c.get("/api/jobs")
    app.dependency_overrides.clear()

    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authenticated"
