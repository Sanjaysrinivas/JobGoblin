from app.models import Job, Resume
from app.services.ai_provider import MockProvider
from app.services.job_analysis import (
    analyze_resume_for_job,
    keyword_checklist,
    score_resume_for_job,
)


class FailingProvider(MockProvider):
    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None) -> dict:
        raise RuntimeError("provider unavailable")


def _resume(text: str, parsed_json: dict | None = None) -> Resume:
    return Resume(
        user_id="00000000-0000-0000-0000-000000000001",
        title="Resume",
        original_filename="resume.pdf",
        file_key="resume.pdf",
        content_type="application/pdf",
        file_size=len(text),
        extracted_text=text,
        parsed_json=parsed_json,
    )


def _job(description: str, title: str = "Backend Engineer") -> Job:
    return Job(
        user_id="00000000-0000-0000-0000-000000000001",
        company_name="Acme",
        title=title,
        description=description,
    )


async def test_analyze_resume_for_job_scores_and_uses_mock_ai():
    resume = _resume(
        "Backend engineer with Python, FastAPI, PostgreSQL, Docker, and REST API "
        "experience. Built reliable services.",
        parsed_json={
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "experience": [{"role": "Backend Engineer", "highlights": ["Built APIs"]}],
        },
    )
    job = _job(
        "Build backend services with Python, FastAPI, PostgreSQL, Docker, REST APIs, "
        "and Kubernetes."
    )

    result = await analyze_resume_for_job(resume, job, MockProvider())

    assert result.overall_score == sum(
        [
            result.keyword_score,
            result.skills_score,
            result.experience_score,
            result.role_score,
            result.education_score,
            result.formatting_score,
        ]
    )
    assert result.keyword_score > 20
    assert {"python", "fastapi", "postgresql", "docker"}.issubset(set(result.matched_keywords))
    assert "kubernetes" in result.missing_keywords
    assert result.explanation == "sample"
    assert result.recommendations == ["sample"]


def test_score_resume_for_job_matches_high_confidence_fuzzy_terms():
    scores = score_resume_for_job(
        "Platform engineer with Kubernetees and Docker experience.",
        None,
        "Platform Engineer",
        "Must have Kubernetes and Docker experience.",
    )

    assert "kubernetes" in scores.matched_keywords
    assert "docker" in scores.matched_keywords
    assert "kubernetes" not in scores.missing_keywords


def test_missing_keywords_lower_keyword_score():
    complete = score_resume_for_job(
        "Python FastAPI PostgreSQL Docker Kubernetes backend engineer.",
        None,
        "Backend Engineer",
        "Python FastAPI PostgreSQL Docker Kubernetes backend engineer.",
    )
    sparse = score_resume_for_job(
        "Python backend engineer.",
        None,
        "Backend Engineer",
        "Python FastAPI PostgreSQL Docker Kubernetes backend engineer.",
    )

    assert complete.keyword_score > sparse.keyword_score
    assert complete.overall_score > sparse.overall_score
    assert {"fastapi", "postgresql", "docker", "kubernetes"}.issubset(set(sparse.missing_keywords))


def test_job_keywords_skip_generic_terms_and_keep_real_gaps():
    scores = score_resume_for_job(
        "Business analyst with AI project delivery experience.",
        None,
        "Project Manager - artificial intelligence focus",
        "Strong working knowledge of Agile, change management, and stakeholder engagement.",
    )

    assert "strong" not in scores.missing_keywords
    assert "working" not in scores.missing_keywords
    assert "agile" in scores.missing_keywords
    assert "change management" in scores.missing_keywords


def test_keyword_checklist_groups_ats_terms():
    checklist = keyword_checklist(
        "Built LLM data workflows with Python and stakeholder engagement.",
        None,
        "AI Project Manager",
        "Lead AI projects with Agile delivery, stakeholder engagement, Python, and Excel.",
    )

    by_label = {group["label"]: group for group in checklist}
    assert "AI and data" in by_label
    assert "Tools" in by_label
    assert "python" in by_label["Tools"]["matched"]
    assert "excel" in by_label["Tools"]["missing"]


async def test_analyze_resume_for_job_falls_back_when_ai_provider_fails():
    resume = _resume("Python developer with backend API experience.")
    job = _job("Build backend APIs with Python and FastAPI.")

    result = await analyze_resume_for_job(resume, job, FailingProvider())

    assert result.explanation.startswith("Estimated match is ")
    assert result.recommendations
    assert result.overall_score == sum(
        [
            result.keyword_score,
            result.skills_score,
            result.experience_score,
            result.role_score,
            result.education_score,
            result.formatting_score,
        ]
    )


def test_score_resume_for_job_uses_short_skills_for_experience_overlap():
    matching = score_resume_for_job(
        "Implemented CI pipelines for backend services.",
        None,
        "DevOps Engineer",
        "Own CI and CD pipelines for service delivery.",
    )
    missing = score_resume_for_job(
        "Wrote release documentation for backend services.",
        None,
        "DevOps Engineer",
        "Own CI and CD pipelines for service delivery.",
    )

    assert matching.experience_score > missing.experience_score


def test_score_resume_for_job_handles_short_role_title_terms():
    scores = score_resume_for_job(
        "Backend engineer with Python experience.",
        None,
        "QA",
        "Manual and automated QA testing.",
    )

    assert scores.role_score == 0
