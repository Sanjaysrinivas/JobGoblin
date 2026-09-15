from app.models import Job, Resume
from app.services.ai_provider import MockProvider
from app.services.job_analysis import (
    analyze_resume_for_job,
    extract_job_keywords,
    keyword_checklist,
    score_resume_for_job,
)


class FailingProvider(MockProvider):
    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None) -> dict:
        raise RuntimeError("provider unavailable")


class UngroundedAdviceProvider(MockProvider):
    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None) -> dict:
        return {
            "explanation": "The resume does not show the role's core requirements.",
            "recommendations": [
                "Highlight experience with Java, Spring Boot, and Apache Kafka.",
                "Consider adding relevant coursework or certifications in sales.",
                "Prepare to address the lack of direct enterprise sales experience.",
            ],
        }


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

    assert 0 <= result.overall_score <= 100
    assert result.keyword_score > 20
    assert {"python", "fastapi", "postgresql", "docker"}.issubset(set(result.matched_keywords))
    assert "kubernetes" in result.missing_keywords
    assert result.explanation.startswith("Estimated match is ")
    assert result.recommendations[0].startswith("Only add these missing job terms")


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
    assert 0 <= result.overall_score <= 100


async def test_analyze_resume_for_job_filters_ungrounded_ai_advice():
    resume = _resume("Data scientist with Python and machine learning experience.")
    job = _job(
        "Lead enterprise sales and account management for Java, Spring Boot, and "
        "Apache Kafka products.",
        title="Account Executive",
    )

    result = await analyze_resume_for_job(resume, job, UngroundedAdviceProvider())

    assert {"java", "spring", "boot", "apache", "kafka"}.issubset(result.missing_keywords)
    assert result.recommendations[0].startswith("Only add these missing job terms")


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


def test_keyword_extraction_deduplicates_terms_and_drops_sentence_punctuation():
    keywords = extract_job_keywords(
        "Terraform. Terraform powers infrastructure. Build reliable data pipelines."
    )

    assert keywords.count("terraform") == 1
    assert not any(keyword.endswith(".") for keyword in keywords)


def test_unrecognized_job_skills_do_not_receive_free_skill_points():
    scores = score_resume_for_job(
        "Backend engineer with Python and Django experience.",
        {"experience": [{"role": "Backend Engineer"}], "skills": ["Python", "Django"]},
        "Backend Engineer",
        "Build Java services with Spring Boot and Apache Kafka.",
    )

    assert scores.skills_score == 0
    assert scores.overall_score < 50


def test_unrelated_experience_does_not_create_a_high_fit_score():
    scores = score_resume_for_job(
        "Backend engineer who built Python APIs and PostgreSQL services.",
        {"experience": [{"role": "Backend Engineer"}], "skills": ["Python", "PostgreSQL"]},
        "Account Executive",
        "Own enterprise sales, prospecting, negotiation, and revenue forecasting.",
    )

    assert scores.overall_score < 40
    assert scores.skills_score == 0


def test_optional_and_negated_job_terms_are_not_scored_as_requirements():
    scores = score_resume_for_job(
        "Python engineer who builds backend services.",
        None,
        "Backend Engineer",
        "Python is required. Kubernetes is nice to have. No AWS experience required.",
    )

    assert "python" in scores.matched_keywords
    assert "kubernetes" not in scores.missing_keywords
    assert "aws" not in scores.missing_keywords


def test_negated_or_aspirational_resume_mentions_are_not_evidence():
    scores = score_resume_for_job(
        "No Kubernetes experience. Interested in learning Terraform.",
        None,
        "Platform Engineer",
        "Kubernetes and Terraform are required.",
    )

    assert "kubernetes" in scores.missing_keywords
    assert "terraform" in scores.missing_keywords


def test_aliases_match_singular_and_plural_api_forms():
    scores = score_resume_for_job(
        "Designed and maintained a public REST API.",
        None,
        "API Engineer",
        "Design reliable APIs for partner integrations.",
    )

    assert "api" in scores.matched_keywords
    assert "api" not in scores.missing_keywords


def test_education_score_requires_the_requested_degree_level():
    scores = score_resume_for_job(
        "Backend engineer with a bachelor's degree in computer science.",
        {"education": [{"degree": "Bachelor of Science", "field": "Computer Science"}]},
        "Research Engineer",
        "A PhD degree in computer science is required.",
    )

    assert scores.education_score == 0
    assert scores.formatting_score == 0


def test_unrequested_categories_do_not_cap_a_perfect_match():
    text = "Enterprise account executive. Own prospecting, negotiation, and revenue forecasting."
    scores = score_resume_for_job(
        text,
        {"experience": [{"role": "Enterprise Account Executive"}]},
        "Enterprise Account Executive",
        "Own prospecting, negotiation, and revenue forecasting.",
    )

    assert scores.education_score == 0
    assert scores.skills_score == 0
    assert scores.overall_score == 100
