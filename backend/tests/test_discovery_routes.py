import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.models import (
    DiscoveryResultStatus,
    Job,
    JobSearchResult,
    JobSource,
    Profile,
    User,
    WorkMode,
)


@pytest.fixture(autouse=True)
def _mock_settings(monkeypatch):
    monkeypatch.setenv("JOB_DISCOVERY_PROVIDER", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def user(session) -> User:
    u = User(email="discover@example.com", password_hash="x", display_name="Owner")
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


@pytest.fixture
def other_user(session) -> User:
    u = User(email="other-discover@example.com", password_hash="x", display_name="Other")
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


def test_preferences_round_trip(client):
    resp = client.put(
        "/api/discovery/preferences",
        json={
            "target_countries": ["GB", "gb", ""],
            "target_locations": ["London"],
            "desired_titles": ["Backend Engineer"],
            "required_keywords": ["Python", "FastAPI"],
            "work_mode": "remote",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["target_countries"] == ["gb"]
    assert body["target_locations"] == ["London"]
    assert body["work_mode"] == "remote"

    loaded = client.get("/api/discovery/preferences")
    assert loaded.status_code == 200
    assert loaded.json()["desired_titles"] == ["Backend Engineer"]


def test_run_creates_ranked_results_and_save_to_job(client, session):
    prefs = client.put(
        "/api/discovery/preferences",
        json={
            "target_countries": ["gb"],
            "target_locations": ["London"],
            "desired_titles": ["Platform"],
            "required_keywords": ["Python", "PostgreSQL"],
            "work_mode": "remote",
        },
    )
    assert prefs.status_code == 200

    run = client.post("/api/discovery/runs", json={"results_per_page": 2})
    assert run.status_code == 201, run.text
    run_body = run.json()
    assert run_body["status"] == "completed"
    assert run_body["country"] == "gb"
    assert run_body["result_count"] == 2

    results = client.get("/api/discovery/results")
    assert results.status_code == 200
    result = results.json()[0]
    assert result["fit_score"] > 0
    assert result["status"] == "new"

    saved = client.post(f"/api/discovery/results/{result['id']}/save")
    assert saved.status_code == 201, saved.text
    job = saved.json()
    assert job["title"] == result["title"]
    assert session.get(Job, uuid.UUID(job["id"])) is not None

    stored = session.get(JobSearchResult, uuid.UUID(result["id"]))
    assert stored.status == DiscoveryResultStatus.saved
    assert stored.saved_job_id == uuid.UUID(job["id"])


def test_dismiss_and_cross_user_result_access(client, session, other_user):
    run = client.post("/api/discovery/runs", json={"country": "us", "query": "python"})
    assert run.status_code == 201
    result = client.get("/api/discovery/results").json()[0]

    dismissed = client.patch(f"/api/discovery/results/{result['id']}", json={"status": "dismissed"})
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"

    stored = session.get(JobSearchResult, uuid.UUID(result["id"]))
    stored.user_id = other_user.id
    session.add(stored)
    session.commit()

    hidden = client.post(f"/api/discovery/results/{result['id']}/save")
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "result_not_found"


def test_run_uses_profile_terms_when_preferences_are_sparse(client, session, user):
    profile = Profile(
        user_id=user.id,
        headline="Data Platform Engineer",
        skills=["Kubernetes", "Python"],
    )
    session.add(profile)
    session.commit()

    run = client.post("/api/discovery/runs", json={"country": "us"})
    assert run.status_code == 201, run.text
    body = run.json()
    assert "Data Platform Engineer" in body["query"]
    assert body["preferences_snapshot"]["profile_terms"] == [
        "Data Platform Engineer",
        "Kubernetes",
        "Python",
    ]

    result = client.get("/api/discovery/results").json()[0]
    assert result["fit_score"] > 35


def test_patch_cannot_mark_result_saved_directly(client):
    run = client.post("/api/discovery/runs", json={"country": "us", "query": "python"})
    assert run.status_code == 201
    result = client.get("/api/discovery/results").json()[0]

    patched = client.patch(f"/api/discovery/results/{result['id']}", json={"status": "saved"})
    assert patched.status_code == 409
    assert patched.json()["code"] == "use_save_endpoint"


def test_preferences_drop_invalid_country_codes(client):
    resp = client.put(
        "/api/discovery/preferences",
        json={"target_countries": ["USA", "d", "DE", "de"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["target_countries"] == ["de"]


async def _duplicate_results(**_kwargs):
    from app.services.job_discovery import DiscoveredJob

    result = DiscoveredJob(
        provider="mock",
        source=JobSource.other,
        source_url="https://example.com/jobs/duplicate",
        title="Python Engineer",
        company_name="Duplicate Co",
        location="Remote",
        work_mode=WorkMode.remote,
        description="Python API work.",
    )
    return [result, result]


def test_run_dedupes_results_within_same_provider_response(client, monkeypatch):
    import app.api.routes.discovery as discovery_routes

    monkeypatch.setattr(discovery_routes, "search_jobs", _duplicate_results)
    run = client.post("/api/discovery/runs", json={"country": "us", "query": "python"})
    assert run.status_code == 201
    assert run.json()["result_count"] == 1
    assert len(client.get("/api/discovery/results").json()) == 1
