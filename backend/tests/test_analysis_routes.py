import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.models import Job, JobAnalysis, Resume, User


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


def _create_resume(session, user: User, **overrides) -> Resume:
    values = {
        "user_id": user.id,
        "title": "Backend Resume",
        "original_filename": "resume.pdf",
        "file_key": f"{user.id}/resume.pdf",
        "content_type": "application/pdf",
        "file_size": 100,
        "extracted_text": (
            "Backend engineer with Python, FastAPI, PostgreSQL, Docker, and REST "
            "API experience."
        ),
        "parsed_json": {
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "experience": [{"role": "Backend Engineer", "highlights": ["Built APIs"]}],
        },
    }
    values.update(overrides)
    resume = Resume(**values)
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def _create_job(session, user: User, **overrides) -> Job:
    values = {
        "user_id": user.id,
        "company_name": "Acme",
        "title": "Backend Engineer",
        "description": (
            "Build backend services with Python, FastAPI, PostgreSQL, Docker, "
            "REST APIs, and Kubernetes."
        ),
    }
    values.update(overrides)
    job = Job(**values)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def test_create_resume_job_analysis_persists_result(client, session, user):
    resume = _create_resume(session, user)
    job = _create_job(session, user)

    resp = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(resume.id), "job_id": str(job.id)},
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["resume_id"] == str(resume.id)
    assert body["job_id"] == str(job.id)
    assert body["overall_score"] == sum(
        body[field]
        for field in (
            "keyword_score",
            "skills_score",
            "experience_score",
            "role_score",
            "education_score",
            "formatting_score",
        )
    )
    assert body["provider"] == "mock"
    assert body["model_used"] == "mock"
    assert body["explanation"] == "sample"
    assert body["recommendations"] == ["sample"]
    assert "python" in body["matched_keywords"]
    assert "kubernetes" in body["missing_keywords"]

    stored = session.get(JobAnalysis, uuid.UUID(body["id"]))
    assert stored is not None
    assert stored.user_id == user.id
    assert stored.provider == "mock"


def test_cross_user_resume_or_job_returns_404(client, session, user, other_user):
    owned_resume = _create_resume(session, user)
    owned_job = _create_job(session, user)
    other_resume = _create_resume(session, other_user)
    other_job = _create_job(session, other_user)

    other_resume_resp = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(other_resume.id), "job_id": str(owned_job.id)},
    )
    assert other_resume_resp.status_code == 404
    assert other_resume_resp.json()["code"] == "analysis_target_not_found"

    other_job_resp = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(owned_resume.id), "job_id": str(other_job.id)},
    )
    assert other_job_resp.status_code == 404
    assert other_job_resp.json()["code"] == "analysis_target_not_found"

    assert session.exec(JobAnalysis.__table__.select()).all() == []


def test_unknown_resume_or_job_returns_404(client, session, user):
    resume = _create_resume(session, user)
    job = _create_job(session, user)

    unknown_resume = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(uuid.uuid4()), "job_id": str(job.id)},
    )
    assert unknown_resume.status_code == 404

    unknown_job = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(resume.id), "job_id": str(uuid.uuid4())},
    )
    assert unknown_job.status_code == 404


def test_resume_without_extracted_text_is_400(client, session, user):
    resume = _create_resume(session, user, extracted_text=None, parsed_json=None)
    job = _create_job(session, user)

    resp = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(resume.id), "job_id": str(job.id)},
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == "no_extracted_text"


def test_requires_authentication(session):
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        resp = c.post(
            "/api/analysis/resume-job",
            json={"resume_id": str(uuid.uuid4()), "job_id": str(uuid.uuid4())},
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authenticated"


def _analysis(session, user: User, resume: Resume, job: Job, **overrides) -> JobAnalysis:
    values = {
        "user_id": user.id,
        "resume_id": resume.id,
        "job_id": job.id,
        "overall_score": 74,
        "keyword_score": 20,
        "skills_score": 18,
        "experience_score": 16,
        "role_score": 8,
        "education_score": 5,
        "formatting_score": 7,
        "matched_keywords": ["python"],
        "missing_keywords": ["kubernetes"],
        "recommendations": ["Add truthful Kubernetes context if applicable."],
        "explanation": "Estimated match.",
        "provider": "mock",
        "model_used": "mock",
    }
    values.update(overrides)
    analysis = JobAnalysis(**values)
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis


def test_get_analysis_returns_owned_analysis(client, session, user):
    resume = _create_resume(session, user)
    job = _create_job(session, user)
    analysis = _analysis(session, user, resume, job)

    resp = client.get(f"/api/analysis/{analysis.id}")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(analysis.id)
    assert body["missing_keywords"] == ["kubernetes"]


def test_get_analysis_cross_user_returns_404(client, session, other_user):
    resume = _create_resume(session, other_user)
    job = _create_job(session, other_user)
    analysis = _analysis(session, other_user, resume, job)

    resp = client.get(f"/api/analysis/{analysis.id}")

    assert resp.status_code == 404
    assert resp.json()["code"] == "analysis_not_found"


def test_list_job_analyses_is_owned_and_newest_first(client, session, user, other_user):
    resume = _create_resume(session, user)
    job = _create_job(session, user)
    older = _analysis(
        session,
        user,
        resume,
        job,
        overall_score=60,
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    newer = _analysis(session, user, resume, job, overall_score=90)
    other_resume = _create_resume(session, other_user)
    other_job = _create_job(session, other_user)
    _analysis(session, other_user, other_resume, other_job, overall_score=10)

    resp = client.get(f"/api/jobs/{job.id}/analysis")

    assert resp.status_code == 200, resp.text
    assert [item["id"] for item in resp.json()] == [str(newer.id), str(older.id)]

    cross_user_job = client.get(f"/api/jobs/{other_job.id}/analysis")
    assert cross_user_job.status_code == 404
    assert cross_user_job.json()["code"] == "job_not_found"

