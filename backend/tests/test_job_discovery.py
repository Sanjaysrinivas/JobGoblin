import asyncio

import pytest

from app.models.enums import JobSource, WorkMode
from app.schemas.discovery import JobSearchPreferencesPayload
from app.services.ai_provider import MockProvider
from app.services.job_discovery import DiscoveredJob, rank_result_with_ai


class RankingProvider(MockProvider):
    def __init__(self) -> None:
        self.prompt = ""

    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None) -> dict:
        self.prompt = prompt
        return {"fit_score": 88, "fit_reason": "Strong fit from resume and saved-job context."}


class SlowProvider(MockProvider):
    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None) -> dict:
        await asyncio.sleep(1)
        return {"fit_score": 99, "fit_reason": "late"}


class FailingProvider(MockProvider):
    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None) -> dict:
        raise RuntimeError("offline")


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
async def test_rank_result_with_ai_falls_back_when_provider_fails():
    preferences = JobSearchPreferencesPayload(required_keywords=["Python"])

    score, reason = await rank_result_with_ai(_job(), preferences, FailingProvider())

    assert score > 0
    assert reason.startswith("Matched")


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
