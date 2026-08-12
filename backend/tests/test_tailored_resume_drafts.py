import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import Job, JobAnalysis, Profile, Resume, ResumeVersion, User
from app.services.ai_provider import MockProvider


class TailoringProvider(MockProvider):
    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None) -> dict:
        return {
            "summary": "API engineer focused on Python services and internal users.",
            "skills": ["Python", "APIs", "SQL", "Kubernetes"],
            "change_notes": ["Reframed summary around existing Python API evidence."],
        }


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
def client(session, user, monkeypatch):
    import app.api.routes.jobs as job_routes
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(job_routes, "get_ai_provider", lambda: MockProvider())
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _job(session, user: User, **overrides) -> Job:
    job = Job(
        user_id=user.id,
        company_name=overrides.pop("company_name", "Acme"),
        title=overrides.pop("title", "Backend Engineer"),
        description=overrides.pop(
            "description", "Build reliable Python APIs. Kubernetes preferred."
        ),
        **overrides,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _resume_with_version(session, user: User) -> tuple[Resume, ResumeVersion]:
    resume = Resume(
        user_id=user.id,
        title="Baseline",
        original_filename="resume.pdf",
        file_key=f"{user.id}/resume.pdf",
        content_type="application/pdf",
        file_size=123,
        extracted_text="Alice Engineer\nPython APIs",
        parsed_json={"summary": "Alice builds APIs", "skills": ["SQL", "Python", "APIs"]},
    )
    version = ResumeVersion(
        resume_id=resume.id,
        title="Current Resume",
        extracted_text="Current text\nPython APIs",
        parsed_json={
            "summary": "Current API engineer",
            "skills": ["SQL", "Python", "APIs"],
            "experience": [
                {
                    "company": "Widgets Inc",
                    "role": "Engineer",
                    "highlights": ["Built Python APIs for internal users"],
                }
            ],
        },
        is_current=True,
    )
    session.add(resume)
    session.add(version)
    session.commit()
    session.refresh(resume)
    session.refresh(version)
    return resume, version


def test_create_and_list_tailored_resume_draft(client, session, user):
    job = _job(session, user)
    resume, source = _resume_with_version(session, user)
    profile = Profile(user_id=user.id, skills=["Python", "APIs"], projects=[])
    analysis = JobAnalysis(
        user_id=user.id,
        resume_id=resume.id,
        job_id=job.id,
        overall_score=80,
        keyword_score=80,
        skills_score=80,
        experience_score=80,
        role_score=80,
        education_score=80,
        formatting_score=80,
        matched_keywords=["Python", "APIs"],
        missing_keywords=["Kubernetes"],
        recommendations=["Move matching API skills higher."],
        provider="test",
        model_used="test",
    )
    session.add(profile)
    session.add(analysis)
    session.commit()
    source_text = source.extracted_text
    source_json = dict(source.parsed_json)

    created = client.post(
        f"/api/jobs/{job.id}/resume-drafts",
        json={
            "resume_id": str(resume.id),
            "source_version_id": str(source.id),
            "title": "Acme Draft",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["title"] == "Acme Draft"
    assert body["job_id"] == str(job.id)
    assert body["source_version_id"] == str(source.id)
    assert body["is_current"] is False
    assert "Tailoring notes (grounded)" in body["extracted_text"]
    assert body["parsed_json"]["tailored_for"]["company_name"] == "Acme"
    tailoring = body["parsed_json"]["tailoring"]
    assert tailoring["source"]["source_version_id"] == str(source.id)
    assert tailoring["source"]["analysis_id"] == str(analysis.id)
    assert tailoring["grounding"]["matched_existing_terms"] == ["Python", "APIs"]
    assert tailoring["grounding"]["job_terms_not_added"] == ["Kubernetes"]
    assert [item["section"] for item in tailoring["suggested_changes"]] == [
        "summary",
        "skills",
        "experience",
        "gaps",
    ]
    assert body["parsed_json"]["skills"][:2] == ["Python", "APIs"]

    session.refresh(source)
    assert source.extracted_text == source_text
    assert source.parsed_json == source_json

    listed = client.get(f"/api/jobs/{job.id}/resume-drafts")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [body["id"]]


def test_tailored_resume_draft_applies_grounded_ai_edits(
    client, session, user, monkeypatch
):
    import app.api.routes.jobs as job_routes

    job = _job(session, user)
    resume, source = _resume_with_version(session, user)
    session.add(
        JobAnalysis(
            user_id=user.id,
            resume_id=resume.id,
            job_id=job.id,
            overall_score=70,
            keyword_score=20,
            skills_score=20,
            experience_score=15,
            role_score=5,
            education_score=5,
            formatting_score=5,
            matched_keywords=["Python", "APIs"],
            missing_keywords=["Kubernetes"],
            provider="test",
            model_used="test",
        )
    )
    session.commit()
    monkeypatch.setattr(job_routes, "get_ai_provider", lambda: TailoringProvider())

    created = client.post(
        f"/api/jobs/{job.id}/resume-drafts",
        json={"resume_id": str(resume.id), "source_version_id": str(source.id)},
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["parsed_json"]["summary"] == (
        "API engineer focused on Python services and internal users."
    )
    assert body["parsed_json"]["skills"] == ["Python", "APIs", "SQL"]
    tailoring = body["parsed_json"]["tailoring"]
    assert tailoring["ai"]["status"] == "applied"
    assert "Kubernetes" in tailoring["grounding"]["job_terms_not_added"]
    assert any(
        change["action"] == "ai_rewrite"
        for change in tailoring["suggested_changes"]
    )


def test_tailored_resume_drafts_are_user_scoped(client, session, user, other_user):
    job = _job(session, user)
    other_job = _job(session, other_user, company_name="OtherCo")
    resume, source = _resume_with_version(session, user)
    other_resume, other_source = _resume_with_version(session, other_user)
    other_draft = ResumeVersion(
        resume_id=other_resume.id,
        job_id=other_job.id,
        source_version_id=other_source.id,
        title="Private",
        extracted_text="private",
        parsed_json={},
        is_current=False,
    )
    session.add(other_draft)
    session.commit()

    cross_job = client.post(
        f"/api/jobs/{other_job.id}/resume-drafts",
        json={"resume_id": str(resume.id)},
    )
    assert cross_job.status_code == 404
    assert cross_job.json()["code"] == "job_not_found"

    cross_resume = client.post(
        f"/api/jobs/{job.id}/resume-drafts",
        json={"resume_id": str(other_resume.id)},
    )
    assert cross_resume.status_code == 404
    assert cross_resume.json()["code"] == "resume_not_found"

    cross_source = client.post(
        f"/api/jobs/{job.id}/resume-drafts",
        json={"resume_id": str(resume.id), "source_version_id": str(other_source.id)},
    )
    assert cross_source.status_code == 404
    assert cross_source.json()["code"] == "resume_version_not_found"

    own = client.post(f"/api/jobs/{job.id}/resume-drafts", json={"resume_id": str(resume.id)})
    assert own.status_code == 201
    listed = client.get(f"/api/jobs/{job.id}/resume-drafts")
    assert listed.status_code == 200
    assert [uuid.UUID(item["job_id"]) for item in listed.json()] == [job.id]
