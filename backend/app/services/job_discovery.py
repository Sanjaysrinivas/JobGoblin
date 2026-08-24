"""Job discovery provider and ranking helpers."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.observability import record_llm_fallback
from app.models.enums import JobSource, WorkMode
from app.schemas.discovery import JobSearchPreferencesPayload, normalize_country_code
from app.services.ai_provider import AIProvider


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


SUPPORTED_DISCOVERY_PROVIDERS = {"mock", "adzuna"}
ADZUNA_COUNTRIES = {
    "at",
    "au",
    "be",
    "br",
    "ca",
    "ch",
    "de",
    "es",
    "fr",
    "gb",
    "in",
    "it",
    "mx",
    "nl",
    "nz",
    "pl",
    "sg",
    "us",
    "za",
}
COUNTRY_NAMES = {
    "at": "austria",
    "au": "australia",
    "be": "belgium",
    "br": "brazil",
    "ca": "canada",
    "ch": "switzerland",
    "de": "germany",
    "es": "spain",
    "fr": "france",
    "gb": "united kingdom",
    "in": "india",
    "it": "italy",
    "mx": "mexico",
    "nl": "netherlands",
    "nz": "new zealand",
    "pl": "poland",
    "sg": "singapore",
    "us": "united states",
    "za": "south africa",
}
BROAD_LOCATION_TERMS = {
    "africa",
    "any",
    "anywhere",
    "asia",
    "asia pacific",
    "europe",
    "global",
    "north america",
    "remote",
    "south america",
    "worldwide",
}


def normalize_discovery_provider(provider: str) -> str:
    text = provider.strip().lower()
    if text not in SUPPORTED_DISCOVERY_PROVIDERS:
        raise ValueError(f"Unsupported discovery provider: {provider}")
    return text


def validate_discovery_country(provider: str, country: str) -> str:
    code = normalize_country_code(country)
    if code is None:
        raise ValueError("Country is required")
    if provider == "adzuna" and code not in ADZUNA_COUNTRIES:
        raise ValueError(f"Country '{code}' is not supported by Adzuna discovery")
    return code


def normalize_search_location(country: str, location: str | None) -> str | None:
    if location is None:
        return None
    text = location.strip()
    if not text:
        return None
    key = re.sub(r"\s+", " ", text.lower())
    country_code = normalize_country_code(country)
    if key in BROAD_LOCATION_TERMS or key == country_code or key == COUNTRY_NAMES.get(country_code):
        return None
    return text


def _contains_term(text: str, term: str) -> bool:
    needle = term.strip().lower()
    if not needle:
        return False
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", text.lower()) is not None


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(_contains_term(text, term) for term in terms)


def build_query(
    preferences: JobSearchPreferencesPayload,
    override: str | None = None,
    *,
    profile_terms: list[str] | None = None,
    resume_terms: list[str] | None = None,
) -> str:
    if override:
        return override.strip()
    parts = [*preferences.desired_titles[:3], preferences.seniority or ""]
    parts.extend(preferences.required_keywords[:5])
    parts.extend(preferences.optional_keywords[:3])
    parts.extend((profile_terms or [])[:6])
    parts.extend((resume_terms or [])[:6])
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
    haystack = f"{result.title} {result.company_name} {result.location or ''} {result.description}"
    blocked = [c for c in preferences.blocked_companies if _contains_term(result.company_name, c)]
    excluded = [word for word in preferences.excluded_keywords if _contains_term(haystack, word)]
    if blocked or excluded:
        return 0, "Blocked by company or excluded keyword."

    missing_required = [
        word for word in preferences.required_keywords if not _contains_term(haystack, word)
    ]
    if missing_required:
        return 0, f"Blocked by missing required keyword: {missing_required[0]}."

    location = result.location or ""
    location_matches = [
        loc for loc in preferences.target_locations if _contains_term(location, loc)
    ]
    if preferences.target_locations and not location_matches:
        return 0, "Blocked by location requirement."

    if (
        preferences.work_mode != WorkMode.unknown
        and result.work_mode != WorkMode.unknown
        and result.work_mode != preferences.work_mode
    ):
        return 0, "Blocked by work mode requirement."

    if preferences.visa_sponsorship_required and not _contains_any(
        haystack, ["visa", "sponsor", "sponsorship"]
    ):
        return 0, "Blocked by visa sponsorship requirement."

    score = 35
    matched: list[str] = []
    details: list[str] = []
    for word in [*preferences.required_keywords, *preferences.optional_keywords]:
        if _contains_term(haystack, word):
            matched.append(word)
    score += min(35, len(set(w.lower() for w in matched)) * 7)

    profile_matches = [term for term in (profile_terms or []) if _contains_term(haystack, term)]
    score += min(15, len(set(term.lower() for term in profile_matches)) * 3)
    matched.extend(profile_matches[:3])

    if preferences.work_mode != WorkMode.unknown:
        if result.work_mode == preferences.work_mode:
            score += 10
            details.append(f"work mode matches {preferences.work_mode.value}")
        elif result.work_mode == WorkMode.unknown:
            details.append("work mode is not specified by the provider")

    if location_matches:
        score += 10
        details.append(f"location matches {location_matches[0]}")

    title_matches = [
        title for title in preferences.desired_titles if _contains_term(result.title, title)
    ]
    if title_matches:
        score += 10
        details.append(f"title matches {title_matches[0]}")

    if preferences.visa_sponsorship_required:
        score += 5
        details.append("visa sponsorship is mentioned")

    score = max(0, min(100, score))
    parts = []
    if matched:
        parts.append("matched " + ", ".join(matched[:5]))
    parts.extend(details[:4])
    reason = "; ".join(parts) if parts else "Matched saved search preferences."
    return score, reason[:1].upper() + reason[1:]


_AI_RANKING_SYSTEM = (
    "You rank discovered jobs for a private job-search workspace. Use only the "
    "provided preferences, profile/resume facts, saved-job history, and job text. "
    "Never invent experience, credentials, employers, or application claims."
)

_AI_RANKING_SCHEMA = {
    "type": "object",
    "properties": {
        "fit_score": {"type": "integer"},
        "fit_reason": {"type": "string"},
    },
    "required": ["fit_score", "fit_reason"],
}


def _clean_ai_score(value: object, fallback: int) -> int:
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return fallback


def _build_ai_ranking_prompt(
    result: DiscoveredJob,
    preferences: JobSearchPreferencesPayload,
    base_score: int,
    base_reason: str,
    *,
    profile_terms: list[str] | None,
    resume_context: str | None,
    saved_job_terms: list[str] | None,
) -> str:
    return (
        "Review this discovered job and return JSON with fit_score 0-100 and "
        "a concise fit_reason. Keep the score near the deterministic estimate "
        "unless the provided user facts clearly support a change.\n\n"
        f"Deterministic estimate: {base_score}/100 - {base_reason}\n"
        "Preferences:\n"
        f"- titles: {', '.join(preferences.desired_titles) or 'none'}\n"
        f"- required keywords: {', '.join(preferences.required_keywords) or 'none'}\n"
        f"- optional keywords: {', '.join(preferences.optional_keywords) or 'none'}\n"
        f"- excluded keywords: {', '.join(preferences.excluded_keywords) or 'none'}\n"
        f"- work mode: {preferences.work_mode.value}\n"
        f"- target locations: {', '.join(preferences.target_locations) or 'none'}\n"
        f"Profile terms: {', '.join(profile_terms or []) or 'none'}\n"
        f"Saved job history terms: {', '.join(saved_job_terms or []) or 'none'}\n"
        f"Resume/profile context:\n{(resume_context or 'none')[:2000]}\n\n"
        "Discovered job:\n"
        f"Title: {result.title}\n"
        f"Company: {result.company_name}\n"
        f"Location: {result.location or 'unknown'}\n"
        f"Work mode: {result.work_mode.value}\n"
        f"Description:\n{result.description[:3000]}"
    )


def _ai_provider_name(provider: AIProvider) -> str:
    return provider.__class__.__name__.replace("Provider", "").lower()


def _record_ranking_fallback(provider: AIProvider, reason: str) -> None:
    provider_name = _ai_provider_name(provider)
    record_llm_fallback(
        provider=provider_name,
        model=str(getattr(provider, "_model", provider_name)),
        operation="discovery.rank_json",
        reason=reason,
    )


async def rank_result_with_ai(
    result: DiscoveredJob,
    preferences: JobSearchPreferencesPayload,
    provider: AIProvider,
    *,
    profile_terms: list[str] | None = None,
    resume_context: str | None = None,
    saved_job_terms: list[str] | None = None,
    timeout_seconds: float = 20.0,
) -> tuple[int, str]:
    base_score, base_reason = rank_result(result, preferences, profile_terms=profile_terms)
    if base_score == 0:
        return base_score, base_reason

    try:
        payload = await asyncio.wait_for(
            provider.generate_json(
                _build_ai_ranking_prompt(
                    result,
                    preferences,
                    base_score,
                    base_reason,
                    profile_terms=profile_terms,
                    resume_context=resume_context,
                    saved_job_terms=saved_job_terms,
                ),
                _AI_RANKING_SCHEMA,
                system=_AI_RANKING_SYSTEM,
            ),
            timeout=timeout_seconds,
        )
        if not isinstance(payload, dict):
            _record_ranking_fallback(provider, "invalid_payload")
            return base_score, base_reason
        reason = str(payload.get("fit_reason") or "").strip()
        if not reason or reason == "sample":
            _record_ranking_fallback(provider, "empty_reason")
            return base_score, base_reason
        return _clean_ai_score(payload.get("fit_score"), base_score), reason
    except TimeoutError:
        _record_ranking_fallback(provider, "timeout")
        return base_score, base_reason
    except Exception as exc:
        _record_ranking_fallback(provider, type(exc).__name__)
        return base_score, base_reason


async def search_jobs(
    *,
    provider: str,
    country: str,
    location: str | None,
    query: str,
    results_per_page: int,
) -> list[DiscoveredJob]:
    provider = normalize_discovery_provider(provider)
    country = validate_discovery_country(provider, country)
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
    slug = _mock_slug(country, place, query)
    return [
        DiscoveredJob(
            provider="mock",
            source=JobSource.other,
            source_url=f"https://example.com/jobs/mock-{slug}-platform-engineer",
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
            source_url=f"https://example.com/jobs/mock-{slug}-backend-engineer",
            title="Backend Developer",
            company_name="Example Systems",
            location=place,
            work_mode=WorkMode.hybrid,
            description="Build backend services, integrations, auth flows, CI, and data pipelines.",
        ),
    ]


def _mock_slug(country: str, location: str, query: str) -> str:
    raw = f"{country}-{location}-{query}".lower()
    slug = "".join(char if char.isalnum() else "-" for char in raw).strip("-")
    return "-".join(part for part in slug.split("-") if part)[:120] or "search"


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
    title = item.get("title") or "Untitled role"
    description = item.get("description") or "No description provided."
    display_location = ", ".join(area) if area else location.get("display_name")
    return DiscoveredJob(
        provider="adzuna",
        source=JobSource.other,
        source_url=item.get("redirect_url"),
        title=title,
        company_name=company.get("display_name") or "Unknown company",
        location=display_location,
        work_mode=_infer_work_mode(title, description, display_location),
        description=description,
        posted_at=posted_at,
    )


def _infer_work_mode(title: str, description: str, location: str | None) -> WorkMode:
    haystack = f"{title} {description} {location or ''}".lower()
    if _contains_any(haystack, ["remote", "work from home", "wfh", "zdalna", "zdalnie"]):
        return WorkMode.remote
    if _contains_any(haystack, ["hybrid", "hybrydowa", "hybrydowo"]):
        return WorkMode.hybrid
    if _contains_any(haystack, ["onsite", "on-site", "office based", "biuro"]):
        return WorkMode.onsite
    return WorkMode.unknown
