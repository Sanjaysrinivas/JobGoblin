import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.models import Job, JobAnalysis, Resume, ResumeVersion, User


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
            "Backend engineer with Python, FastAPI, PostgreSQL, Docker, and REST API experience."
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
    assert 0 <= body["overall_score"] <= 100
    assert body["provider"] == "deterministic"
    assert body["model_used"] == "grounded-v2"
    assert body["explanation"].startswith("Estimated match is ")
    assert body["recommendations"]
    assert "python" in body["matched_keywords"]
    assert "kubernetes" in body["missing_keywords"]
    assert body["fit_label"] == "Strong match"
    assert body["application_readiness"] == "Needs tailoring"
    assert body["keyword_checklist"]
    assert body["rewrite_suggestions"]

    stored = session.get(JobAnalysis, uuid.UUID(body["id"]))
    assert stored is not None
    assert stored.user_id == user.id
    assert stored.provider == "deterministic"
    assert stored.guidance_snapshot == {
        "fit_label": body["fit_label"],
        "application_readiness": body["application_readiness"],
        "readiness_steps": body["readiness_steps"],
        "keyword_checklist": body["keyword_checklist"],
        "rewrite_suggestions": body["rewrite_suggestions"],
    }
    assert stored.resume_evidence_hash


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
    assert body["fit_label"] is None
    assert body["application_readiness"] is None


def test_get_analysis_cross_user_returns_404(client, session, other_user):
    resume = _create_resume(session, other_user)
    job = _create_job(session, other_user)
    analysis = _analysis(session, other_user, resume, job)

    resp = client.get(f"/api/analysis/{analysis.id}")

    assert resp.status_code == 404
    assert resp.json()["code"] == "analysis_not_found"


def test_analysis_drift_lookup_does_not_cross_user_ownership(
    client, session, user, other_user
):
    resume = _create_resume(session, user)
    job = _create_job(session, user)
    created = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(resume.id), "job_id": str(job.id)},
    ).json()
    analysis = session.get(JobAnalysis, uuid.UUID(created["id"]))
    assert analysis is not None

    analysis.resume_id = _create_resume(session, other_user).id
    analysis.job_id = _create_job(session, other_user).id
    session.add(analysis)
    session.commit()

    resp = client.get(f"/api/analysis/{analysis.id}")
    assert resp.status_code == 200
    assert resp.json()["inputs_changed"] is False


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


def test_analysis_reports_category_applicability(client, session, user):
    resume = _create_resume(session, user)
    job = _create_job(session, user)  # description has no education requirement

    resp = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(resume.id), "job_id": str(job.id)},
    )

    assert resp.status_code == 201, resp.text
    breakdown = {row["key"]: row for row in resp.json()["score_breakdown"]}
    assert set(breakdown) == {"keyword", "skills", "experience", "role", "education"}

    education = breakdown["education"]
    assert education["applicable"] is False
    assert education["maximum"] == 5

    keyword = breakdown["keyword"]
    assert keyword["applicable"] is True
    assert keyword["maximum"] == 35
    assert keyword["earned"] == resp.json()["keyword_score"]

    applicable_maxima = sum(row["maximum"] for row in breakdown.values() if row["applicable"])
    assert applicable_maxima > 0


def test_analysis_marks_education_applicable_when_required(client, session, user):
    resume = _create_resume(session, user)
    job = _create_job(
        session,
        user,
        description=(
            "Build backend services with Python, FastAPI, PostgreSQL, Docker, "
            "REST APIs, and Kubernetes. Bachelor degree in Computer Science required."
        ),
    )

    resp = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(resume.id), "job_id": str(job.id)},
    )

    assert resp.status_code == 201, resp.text
    breakdown = {row["key"]: row for row in resp.json()["score_breakdown"]}
    assert breakdown["education"]["applicable"] is True
    assert breakdown["education"]["earned"] == resp.json()["education_score"]


def test_analysis_flags_legacy_results(client, session, user):
    resume = _create_resume(session, user)
    job = _create_job(session, user)

    legacy = JobAnalysis(
        user_id=user.id,
        resume_id=resume.id,
        job_id=job.id,
        overall_score=80,
        keyword_score=28,
        skills_score=24,
        experience_score=16,
        role_score=8,
        education_score=4,
        formatting_score=8,
        matched_keywords=["python"],
        missing_keywords=[],
        recommendations=["Mention your Kubernetes exposure."],
        explanation="Old model explanation.",
        provider="ollama",
        model_used="qwen2.5:7b-instruct",
    )
    session.add(legacy)
    session.commit()
    session.refresh(legacy)

    legacy_resp = client.get(f"/api/analysis/{legacy.id}")
    assert legacy_resp.status_code == 200
    assert legacy_resp.json()["is_legacy"] is True

    fresh_resp = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(resume.id), "job_id": str(job.id)},
    )
    assert fresh_resp.status_code == 201
    assert fresh_resp.json()["is_legacy"] is False

    # Historical record is untouched by the new run.
    stored = session.get(JobAnalysis, legacy.id)
    assert stored is not None
    assert stored.model_used == "qwen2.5:7b-instruct"
    assert stored.recommendations == ["Mention your Kubernetes exposure."]


def test_stored_breakdown_is_immutable_and_reproducible(client, session, user):
    resume = _create_resume(session, user)
    job = _create_job(session, user)

    created = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(resume.id), "job_id": str(job.id)},
    ).json()
    original_breakdown = created["score_breakdown"]
    original_guidance = {
        key: created[key]
        for key in (
            "fit_label",
            "application_readiness",
            "readiness_steps",
            "keyword_checklist",
            "rewrite_suggestions",
        )
    }
    assert original_breakdown
    assert created["inputs_changed"] is False

    # Editing the job must not rewrite the stored explanation.
    job.description = "Completely different role requiring Rust and embedded C."
    resume.parsed_json = {"skills": ["Rust"], "experience": []}
    session.add(job)
    session.add(resume)
    session.commit()

    refetched = client.get(f"/api/analysis/{created['id']}").json()
    assert refetched["score_breakdown"] == original_breakdown
    assert {key: refetched[key] for key in original_guidance} == original_guidance
    assert refetched["inputs_changed"] is True

    # A non-legacy overall score is reproducible from its stored breakdown.
    earned = sum(r["earned"] for r in refetched["score_breakdown"])
    maximum = sum(r["maximum"] for r in refetched["score_breakdown"] if r["applicable"])
    if maximum > 0:
        assert abs(refetched["overall_score"] - round(100 * earned / maximum)) <= 1


def test_analysis_detects_parsed_resume_evidence_changes(client, session, user):
    resume = _create_resume(session, user)
    job = _create_job(session, user)
    created = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(resume.id), "job_id": str(job.id)},
    ).json()

    resume.parsed_json = {"skills": ["Rust"], "experience": []}
    session.add(resume)
    session.commit()

    refetched = client.get(f"/api/analysis/{created['id']}").json()
    assert refetched["inputs_changed"] is True


def test_analysis_detects_resume_version_changes_with_identical_evidence(
    client, session, user
):
    resume = _create_resume(session, user)
    first = ResumeVersion(
        resume_id=resume.id,
        title="First",
        extracted_text=resume.extracted_text,
        parsed_json=resume.parsed_json,
        is_current=True,
    )
    session.add(first)
    session.commit()
    job = _create_job(session, user)
    created = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(resume.id), "job_id": str(job.id)},
    ).json()

    first.is_current = False
    session.add(first)
    session.flush()
    session.add(
        ResumeVersion(
            resume_id=resume.id,
            title="Second",
            extracted_text=resume.extracted_text,
            parsed_json=resume.parsed_json,
            is_current=True,
        )
    )
    session.commit()

    refetched = client.get(f"/api/analysis/{created['id']}").json()
    assert refetched["inputs_changed"] is True


def test_legacy_row_without_snapshot_has_no_fabricated_breakdown(client, session, user):
    resume = _create_resume(session, user)
    job = _create_job(session, user)
    legacy = JobAnalysis(
        user_id=user.id,
        resume_id=resume.id,
        job_id=job.id,
        overall_score=84,
        keyword_score=28,
        skills_score=24,
        experience_score=16,
        role_score=8,
        education_score=4,
        formatting_score=8,
        matched_keywords=[],
        missing_keywords=[],
        recommendations=["Old advice."],
        explanation="Old explanation.",
        provider="deterministic",
        model_used="grounded-v2",  # version matches, but no persisted snapshot
    )
    session.add(legacy)
    session.commit()
    session.refresh(legacy)

    resp = client.get(f"/api/analysis/{legacy.id}").json()
    assert resp["is_legacy"] is True
    assert resp["score_breakdown"] is None


def test_required_but_zero_and_not_applicable_categories(client, session, user):
    resume = _create_resume(
        session,
        user,
        extracted_text="Sales account manager with retail experience.",
        parsed_json={"skills": ["Excel"], "experience": []},
    )
    job = _create_job(
        session,
        user,
        description=(
            "Bachelor degree required. Must have Kubernetes, Docker, and "
            "Terraform skills."
        ),
    )

    resp = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(resume.id), "job_id": str(job.id)},
    ).json()
    breakdown = {row["key"]: row for row in resp["score_breakdown"]}
    assert breakdown["education"]["applicable"] is True
    assert breakdown["education"]["earned"] == 0  # required but no evidence
    assert breakdown["skills"]["applicable"] is True
    assert breakdown["skills"]["earned"] == 0
    assert breakdown["education"]["maximum"] == 5
    assert breakdown["skills"]["maximum"] == 30


def test_create_analysis_uses_current_resume_version(client, session, user):
    resume = _create_resume(
        session,
        user,
        extracted_text="Base resume with Python only.",
        parsed_json={"skills": ["Python"]},
    )
    session.add(
        ResumeVersion(
            resume_id=resume.id,
            title="Kubernetes version",
            extracted_text="Current version with Python and Kubernetes platform work.",
            parsed_json={"skills": ["Python", "Kubernetes"]},
            is_current=True,
        )
    )
    session.commit()
    job = _create_job(
        session,
        user,
        description="Build Kubernetes platform services with Python.",
    )

    resp = client.post(
        "/api/analysis/resume-job",
        json={"resume_id": str(resume.id), "job_id": str(job.id)},
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "kubernetes" in body["matched_keywords"]
    assert "kubernetes" not in body["missing_keywords"]
