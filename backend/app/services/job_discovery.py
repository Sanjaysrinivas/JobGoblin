"""Job discovery provider and ranking helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.enums import JobSource, WorkMode
from app.schemas.discovery import JobSearchPreferencesPayload


@dataclass
class DiscoveredJob:
    provider: str
    source: JobSource
    source_url: str | None
    title: str
    company_name: str
    location: str | None
    work_mode: WorkMode
    description: str
    posted_at: datetime | None = None


def build_query(
    preferences: JobSearchPreferencesPayload,
    override: str | None = None,
    *,
    profile_terms: list[str] | None = None,
) -> str:
    if override:
        return override.strip()
    parts = [*preferences.desired_titles[:3], preferences.seniority or ""]
    parts.extend(preferences.required_keywords[:5])
    parts.extend(preferences.optional_keywords[:3])
    parts.extend((profile_terms or [])[:6])
    if preferences.work_mode != WorkMode.unknown:
        parts.append(preferences.work_mode.value)
    query = " ".join(part for part in parts if part).strip()
    return query or "software engineer"


def rank_result(
    result: DiscoveredJob,
    preferences: JobSearchPreferencesPayload,
    *,
    profile_terms: list[str] | None = None,
) -> tuple[int, str]:
    haystack = (
        f"{result.title} {result.company_name} {result.location or ''} {result.description}".lower()
    )
    blocked = [c for c in preferences.blocked_companies if c.lower() in result.company_name.lower()]
    excluded = [word for word in preferences.excluded_keywords if word.lower() in haystack]
    if blocked or excluded:
        return 0, "Blocked by company or excluded keyword."

    score = 35
    matched: list[str] = []
    for word in [*preferences.required_keywords, *preferences.optional_keywords]:
        if word.lower() in haystack:
            matched.append(word)
    score += min(35, len(set(w.lower() for w in matched)) * 7)

    profile_matches = [term for term in (profile_terms or []) if term.lower() in haystack]
    score += min(15, len(set(term.lower() for term in profile_matches)) * 3)
    matched.extend(profile_matches[:3])

    if preferences.work_mode != WorkMode.unknown and result.work_mode == preferences.work_mode:
        score += 10
    if any(loc.lower() in (result.location or "").lower() for loc in preferences.target_locations):
        score += 10
    if any(title.lower() in result.title.lower() for title in preferences.desired_titles):
        score += 10

    score = max(0, min(100, score))
    reason = "Matched " + ", ".join(matched[:5]) if matched else "Matched saved search preferences."
    return score, reason


async def search_jobs(
    *,
    provider: str,
    country: str,
    location: str | None,
    query: str,
    results_per_page: int,
) -> list[DiscoveredJob]:
    if provider == "mock":
        return _mock_results(country=country, location=location, query=query)
    if provider == "adzuna":
        return await _adzuna_results(
            country=country,
            location=location,
            query=query,
            results_per_page=results_per_page,
        )
    raise ValueError(f"Unsupported discovery provider: {provider}")


def _mock_results(*, country: str, location: str | None, query: str) -> list[DiscoveredJob]:
    place = location or country.upper()
    return [
        DiscoveredJob(
            provider="mock",
            source=JobSource.other,
            source_url="https://example.com/jobs/mock-platform-engineer",
            title=f"{query.title()} Engineer",
            company_name="Mock Hiring Co",
            location=place,
            work_mode=WorkMode.remote,
            description=(
                f"Role in {place} focused on {query}, Python, APIs, Docker, and PostgreSQL."
            ),
        ),
        DiscoveredJob(
            provider="mock",
            source=JobSource.other,
            source_url="https://example.com/jobs/mock-backend-engineer",
            title="Backend Developer",
            company_name="Example Systems",
            location=place,
            work_mode=WorkMode.hybrid,
            description="Build backend services, integrations, auth flows, CI, and data pipelines.",
        ),
    ]


async def _adzuna_results(
    *,
    country: str,
    location: str | None,
    query: str,
    results_per_page: int,
) -> list[DiscoveredJob]:
    settings = get_settings()
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        raise RuntimeError("ADZUNA_APP_ID and ADZUNA_APP_KEY are required for Adzuna discovery.")

    url = f"{settings.adzuna_base_url.rstrip('/')}/jobs/{country}/search/1"
    params = {
        "app_id": settings.adzuna_app_id,
        "app_key": settings.adzuna_app_key,
        "what": query,
        "results_per_page": results_per_page,
        "content-type": "application/json",
    }
    if location:
        params["where"] = location

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, params=params, headers={"Accept": "application/json"})
        response.raise_for_status()
    data = response.json()
    return [_from_adzuna(item) for item in data.get("results", [])]


def _from_adzuna(item: dict[str, Any]) -> DiscoveredJob:
    company = item.get("company") or {}
    location = item.get("location") or {}
    area = location.get("area") or []
    created = item.get("created")
    posted_at = None
    if isinstance(created, str):
        try:
            posted_at = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            posted_at = None
    return DiscoveredJob(
        provider="adzuna",
        source=JobSource.other,
        source_url=item.get("redirect_url"),
        title=item.get("title") or "Untitled role",
        company_name=company.get("display_name") or "Unknown company",
        location=", ".join(area) if area else location.get("display_name"),
        work_mode=WorkMode.unknown,
        description=item.get("description") or "No description provided.",
        posted_at=posted_at,
    )
