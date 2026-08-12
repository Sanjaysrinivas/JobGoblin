import asyncio

import pytest

from app.models.enums import JobSource, WorkMode
from app.schemas.discovery import JobSearchPreferencesPayload
from app.services.ai_provider import MockProvider
from app.services.job_discovery import (
    DiscoveredJob,
    _from_adzuna,
    rank_result,
    rank_result_with_ai,
    search_jobs,
)


class RankingProvider(MockProvider):
    def __init__(self) -> None:
        self.prompt = ""

    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None) -> dict:
        self.prompt = prompt
        return {"fit_score": 88, "fit_reason": "Strong fit from resume and saved-job context."}


class FloatScoreProvider(MockProvider):
    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None) -> dict:
        return {"fit_score": "85.5", "fit_reason": "Float-like score parsed."}


class BadPayloadProvider(MockProvider):
    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None):
        return None


class SlowProvider(MockProvider):
    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None) -> dict:
        await asyncio.sleep(1)
        return {"fit_score": 99, "fit_reason": "late"}


class FailingProvider(MockProvider):
    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None) -> dict:
        raise RuntimeError("offline")


def test_rank_result_explains_location_work_mode_and_visa():
    preferences = JobSearchPreferencesPayload(
        desired_titles=["Platform Engineer"],
        required_keywords=["Python"],
        target_locations=["Remote"],
        visa_sponsorship_required=True,
        work_mode=WorkMode.remote,
    )

    score, reason = rank_result(
        _job("Build Python APIs. Visa sponsorship available."),
        preferences,
    )

    assert score > 0
    assert "work mode matches remote" in reason
    assert "location matches Remote" in reason
    assert "visa sponsorship is mentioned" in reason


def test_rank_result_blocks_required_constraints():
    score, reason = rank_result(
        _job("Build Python APIs."),
        JobSearchPreferencesPayload(required_keywords=["Kubernetes"]),
    )
    assert score == 0
    assert reason == "Blocked by missing required keyword: Kubernetes."

    score, reason = rank_result(
        _job("Build Python APIs."),
        JobSearchPreferencesPayload(target_locations=["London"]),
    )
    assert score == 0
    assert reason == "Blocked by location requirement."

    onsite = _job("Build Python APIs.")
    onsite.work_mode = WorkMode.onsite
    score, reason = rank_result(onsite, JobSearchPreferencesPayload(work_mode=WorkMode.remote))
    assert score == 0
    assert reason == "Blocked by work mode requirement."

    score, reason = rank_result(
        _job("Build Python APIs."),
        JobSearchPreferencesPayload(visa_sponsorship_required=True),
    )
    assert score == 0
    assert reason == "Blocked by visa sponsorship requirement."


def test_rank_result_uses_whole_word_matching():
    score, _reason = rank_result(
        _job("Build Django APIs."),
        JobSearchPreferencesPayload(excluded_keywords=["go"]),
    )

    assert score > 0


def test_from_adzuna_infers_remote_work_mode():
    job = _from_adzuna(
        {
            "title": "AI Engineer 100% REMOTE",
            "company": {"display_name": "Example Co"},
            "location": {"area": ["Poland"]},
            "description": "Build LLM workflows.",
        }
    )

    assert job.work_mode == WorkMode.remote


@pytest.mark.asyncio
async def test_search_jobs_rejects_bad_country_code():
    with pytest.raises(ValueError, match="2-letter"):
        await search_jobs(
            provider="mock",
            country="u1",
            location=None,
            query="python",
            results_per_page=1,
        )


@pytest.mark.asyncio
async def test_mock_search_urls_are_unique_per_query():
    first = await search_jobs(
        provider="mock",
        country="it",
        location="Italy",
        query="data analyst",
        results_per_page=10,
    )
    second = await search_jobs(
        provider="mock",
        country="it",
        location="Italy",
        query="software engineer",
        results_per_page=10,
    )

    assert {job.source_url for job in first}.isdisjoint(job.source_url for job in second)


def _job(description: str = "Build Python APIs with PostgreSQL.") -> DiscoveredJob:
    return DiscoveredJob(
        provider="mock",
        source=JobSource.other,
        source_url="https://example.com/job",
        title="Platform Engineer",
        company_name="Example Co",
        location="Remote",
        work_mode=WorkMode.remote,
        description=description,
    )


@pytest.mark.asyncio
async def test_rank_result_with_ai_uses_provider_payload_and_context():
    provider = RankingProvider()
    preferences = JobSearchPreferencesPayload(
        desired_titles=["Platform Engineer"],
        required_keywords=["Python"],
        target_locations=["Remote"],
        work_mode=WorkMode.remote,
    )

    score, reason = await rank_result_with_ai(
        _job(),
        preferences,
        provider,
        profile_terms=["Kubernetes"],
        resume_context="Python and Kubernetes platform work.",
        saved_job_terms=["Backend Engineer"],
    )

    assert score == 88
    assert reason == "Strong fit from resume and saved-job context."
    assert "Python and Kubernetes platform work" in provider.prompt
    assert "Backend Engineer" in provider.prompt


@pytest.mark.asyncio
async def test_rank_result_with_ai_falls_back_when_provider_fails(monkeypatch):
    fallbacks = []
    monkeypatch.setattr(
        "app.services.job_discovery.record_llm_fallback",
        lambda **attrs: fallbacks.append(attrs),
    )
    preferences = JobSearchPreferencesPayload(required_keywords=["Python"])

    score, reason = await rank_result_with_ai(_job(), preferences, FailingProvider())

    assert score > 0
    assert reason.startswith("Matched")
    assert fallbacks[-1]["operation"] == "discovery.rank_json"
    assert fallbacks[-1]["reason"] == "RuntimeError"


@pytest.mark.asyncio
async def test_rank_result_with_ai_keeps_blocked_result_at_zero():
    preferences = JobSearchPreferencesPayload(blocked_companies=["Example Co"])

    score, reason = await rank_result_with_ai(_job(), preferences, RankingProvider())

    assert score == 0
    assert reason == "Blocked by company or excluded keyword."


@pytest.mark.asyncio
async def test_rank_result_with_ai_falls_back_when_provider_times_out():
    preferences = JobSearchPreferencesPayload(required_keywords=["Python"])

    score, reason = await rank_result_with_ai(
        _job(), preferences, SlowProvider(), timeout_seconds=0.01
    )

    assert score > 0
    assert reason.startswith("Matched")


@pytest.mark.asyncio
async def test_rank_result_with_ai_parses_float_like_scores():
    preferences = JobSearchPreferencesPayload(required_keywords=["Python"])

    score, reason = await rank_result_with_ai(_job(), preferences, FloatScoreProvider())

    assert score == 85
    assert reason == "Float-like score parsed."


@pytest.mark.asyncio
async def test_rank_result_with_ai_falls_back_for_non_dict_payload():
    preferences = JobSearchPreferencesPayload(required_keywords=["Python"])

    score, reason = await rank_result_with_ai(_job(), preferences, BadPayloadProvider())

    assert score > 0
    assert reason.startswith("Matched")
