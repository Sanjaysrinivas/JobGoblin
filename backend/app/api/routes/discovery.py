"""Job discovery endpoints.

Discovery finds and ranks candidate jobs, but never applies or contacts anyone.
Users explicitly save selected results into normal Jobs.
"""

import asyncio
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.models import (
    DiscoveryResultStatus,
    DiscoveryRunStatus,
    Job,
    JobSearchPreferences,
    JobSearchResult,
    JobSearchRun,
    Profile,
    Resume,
    ResumeVersion,
    User,
)
from app.schemas.discovery import (
    JobSearchPreferencesOut,
    JobSearchPreferencesPayload,
    JobSearchResultOut,
    JobSearchResultUpdate,
    JobSearchRunCreate,
    JobSearchRunOut,
)
from app.schemas.job import JobOut
from app.services.ai_provider import get_ai_provider
from app.services.job_discovery import (
    build_query,
    normalize_discovery_provider,
    rank_result_with_ai,
    search_jobs,
    validate_discovery_country,
)

router = APIRouter(prefix="/discovery", tags=["discovery"])


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _preferences_payload(model: JobSearchPreferences | None) -> JobSearchPreferencesPayload:
    if model is None:
        return JobSearchPreferencesPayload()
    return JobSearchPreferencesPayload(
        target_countries=model.target_countries or [],
        target_locations=model.target_locations or [],
        desired_titles=model.desired_titles or [],
        seniority=model.seniority,
        industries=model.industries or [],
        required_keywords=model.required_keywords or [],
        optional_keywords=model.optional_keywords or [],
        excluded_keywords=model.excluded_keywords or [],
        visa_sponsorship_required=model.visa_sponsorship_required,
        blocked_companies=model.blocked_companies or [],
        work_mode=model.work_mode,
    )


def _get_preferences(session: Session, user_id: uuid.UUID) -> JobSearchPreferences | None:
    return session.exec(
        select(JobSearchPreferences).where(JobSearchPreferences.user_id == user_id)
    ).first()


def _profile_terms(profile: Profile | None) -> list[str]:
    if profile is None:
        return []
    terms: list[str] = []
    if profile.headline:
        terms.append(profile.headline)
    for item in (profile.experience or [])[:2]:
        if isinstance(item, dict) and item.get("role"):
            terms.append(str(item["role"]))
    terms.extend((profile.skills or [])[:8])

    cleaned: list[str] = []
    seen = set()
    for term in terms:
        text = term.strip()
        key = text.lower()
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
    return cleaned[:10]


def _format_context_value(value: object) -> str:
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                fields = [
                    str(item.get(key) or "").strip()
                    for key in ("role", "company", "credential", "institution")
                ]
                highlights = item.get("highlights")
                if isinstance(highlights, list):
                    fields.extend(str(h).strip() for h in highlights[:3])
                text = " - ".join(field for field in fields if field)
            else:
                text = str(item).strip()
            if text:
                parts.append(text)
        return "; ".join(parts)
    if isinstance(value, dict):
        return "; ".join(
            f"{key}: {text}" for key, raw in value.items() if (text := _format_context_value(raw))
        )
    return str(value or "").strip()


def _resume_context(session: Session, user_id: uuid.UUID) -> str:
    resume = session.exec(
        select(Resume)
        .where(Resume.user_id == user_id)
        .order_by(Resume.is_default.desc(), Resume.created_at.desc())
    ).first()
    if resume is None:
        return ""
    version = session.exec(
        select(ResumeVersion).where(
            ResumeVersion.resume_id == resume.id, ResumeVersion.is_current.is_(True)
        )
    ).first()
    parsed = version.parsed_json if version else resume.parsed_json
    if isinstance(parsed, dict):
        parts = []
        for key in ("summary", "skills", "experience", "projects", "certifications"):
            text = _format_context_value(parsed.get(key))
            if text:
                parts.append(f"{key}: {text}")
        if parts:
            return "\n".join(parts)
    text = version.extracted_text if version else resume.extracted_text
    return (text or "").strip()


def _saved_job_terms(session: Session, user_id: uuid.UUID) -> list[str]:
    jobs = session.exec(
        select(Job).where(Job.user_id == user_id).order_by(Job.created_at.desc()).limit(10)
    ).all()
    terms: list[str] = []
    seen = set()
    for job in jobs:
        for term in (job.title, job.company_name):
            text = (term or "").strip()
            key = text.lower()
            if text and key not in seen:
                terms.append(text)
                seen.add(key)
    return terms[:20]


def _get_result(session: Session, user: User, result_id: uuid.UUID) -> JobSearchResult:
    result = session.exec(
        select(JobSearchResult).where(
            JobSearchResult.id == result_id,
            JobSearchResult.user_id == user.id,
        )
    ).first()
    if result is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Discovery result not found", "result_not_found")
    return result


def _dedupe_key(
    provider: str, source_url: str | None, company: str, title: str, location: str | None
) -> str:
    raw = source_url or "|".join([provider, company, title, location or ""])
    return raw.strip().lower()


def _discovery_error_message(provider: str, exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"{provider} discovery failed with HTTP {exc.response.status_code}."
    if isinstance(exc, httpx.RequestError):
        return f"{provider} discovery request failed: {type(exc).__name__}."
    return str(exc)


@router.get("/preferences", response_model=JobSearchPreferencesOut | None)
def get_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JobSearchPreferences | None:
    return _get_preferences(session, current_user.id)


@router.put("/preferences", response_model=JobSearchPreferencesOut)
def save_preferences(
    payload: JobSearchPreferencesPayload,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JobSearchPreferences:
    preferences = _get_preferences(session, current_user.id)
    if preferences is None:
        preferences = JobSearchPreferences(user_id=current_user.id)
    for field, value in payload.model_dump(mode="json").items():
        setattr(preferences, field, value)
    session.add(preferences)
    session.commit()
    session.refresh(preferences)
    return preferences


@router.get("/runs", response_model=list[JobSearchRunOut])
def list_runs(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[JobSearchRun]:
    return list(
        session.exec(
            select(JobSearchRun)
            .where(JobSearchRun.user_id == current_user.id)
            .order_by(JobSearchRun.created_at.desc())
        ).all()
    )


@router.post("/runs", response_model=JobSearchRunOut, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: JobSearchRunCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JobSearchRun:
    settings = get_settings()
    preferences = _preferences_payload(_get_preferences(session, current_user.id))
    profile = session.exec(select(Profile).where(Profile.user_id == current_user.id)).first()
    profile_terms = _profile_terms(profile)
    provider = payload.provider or settings.job_discovery_provider
    country = payload.country or (
        preferences.target_countries[0] if preferences.target_countries else "us"
    )
    try:
        provider = normalize_discovery_provider(provider)
        country = validate_discovery_country(provider, country)
    except ValueError as exc:
        code = "unsupported_provider" if "provider" in str(exc).lower() else "invalid_country"
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc), code) from exc
    location = payload.location or (
        preferences.target_locations[0] if preferences.target_locations else None
    )
    resume_context = _resume_context(session, current_user.id)
    saved_job_terms = _saved_job_terms(session, current_user.id)
    ai_provider = get_ai_provider()
    query = build_query(preferences, payload.query, profile_terms=profile_terms)
    run = JobSearchRun(
        user_id=current_user.id,
        provider=provider,
        status=DiscoveryRunStatus.pending,
        country=country,
        location=location,
        query=query,
        preferences_snapshot={
            **preferences.model_dump(mode="json"),
            "profile_terms": profile_terms,
            "saved_job_terms": saved_job_terms,
        },
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    try:
        raw_results = await search_jobs(
            provider=provider,
            country=country,
            location=location,
            query=query,
            results_per_page=payload.results_per_page,
        )
    except Exception as exc:
        run.status = DiscoveryRunStatus.failed
        run.error = _discovery_error_message(provider, exc)
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    candidates = []
    seen_dedupes: set[str] = set()
    for item in raw_results:
        dedupe = _dedupe_key(
            item.provider, item.source_url, item.company_name, item.title, item.location
        )
        if dedupe in seen_dedupes:
            continue
        seen_dedupes.add(dedupe)
        existing = session.exec(
            select(JobSearchResult).where(
                JobSearchResult.user_id == current_user.id,
                JobSearchResult.dedupe_key == dedupe,
            )
        ).first()
        if existing is None:
            candidates.append((item, dedupe))

    rankings = await asyncio.gather(
        *(
            rank_result_with_ai(
                item,
                preferences,
                ai_provider,
                profile_terms=profile_terms,
                resume_context=resume_context,
                saved_job_terms=saved_job_terms,
            )
            for item, _dedupe in candidates
        )
    )
    for (item, dedupe), (fit_score, fit_reason) in zip(candidates, rankings, strict=False):
        session.add(
            JobSearchResult(
                user_id=current_user.id,
                run_id=run.id,
                provider=item.provider,
                source=item.source,
                source_url=item.source_url,
                canonical_url=item.source_url,
                title=item.title,
                company_name=item.company_name,
                location=item.location,
                work_mode=item.work_mode,
                description=item.description,
                posted_at=item.posted_at,
                dedupe_key=dedupe,
                fit_score=fit_score,
                fit_reason=fit_reason,
            )
        )
    created = len(candidates)
    run.status = DiscoveryRunStatus.completed
    run.result_count = created
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


@router.get("/results", response_model=list[JobSearchResultOut])
def list_results(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    result_status: Annotated[DiscoveryResultStatus | None, Query(alias="status")] = None,
) -> list[JobSearchResult]:
    statement = select(JobSearchResult).where(JobSearchResult.user_id == current_user.id)
    if result_status is not None:
        statement = statement.where(JobSearchResult.status == result_status)
    return list(
        session.exec(
            statement.order_by(JobSearchResult.fit_score.desc(), JobSearchResult.created_at.desc())
        ).all()
    )


@router.patch("/results/{result_id}", response_model=JobSearchResultOut)
def update_result(
    result_id: uuid.UUID,
    payload: JobSearchResultUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JobSearchResult:
    result = _get_result(session, current_user, result_id)
    if (
        payload.status == DiscoveryResultStatus.saved
        and result.status != DiscoveryResultStatus.saved
    ):
        raise _error(
            status.HTTP_409_CONFLICT,
            "Use the save endpoint to mark discovery results as saved.",
            "use_save_endpoint",
        )
    if (
        result.status == DiscoveryResultStatus.saved
        and payload.status != DiscoveryResultStatus.saved
    ):
        raise _error(
            status.HTTP_409_CONFLICT, "Saved results cannot be unsaved here.", "result_saved"
        )
    result.status = payload.status
    session.add(result)
    session.commit()
    session.refresh(result)
    return result


@router.post(
    "/results/{result_id}/save", response_model=JobOut, status_code=status.HTTP_201_CREATED
)
def save_result_as_job(
    result_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Job:
    result = _get_result(session, current_user, result_id)
    if result.saved_job_id is not None:
        job = session.get(Job, result.saved_job_id)
        if job is not None and job.user_id == current_user.id:
            return job

    job = Job(
        user_id=current_user.id,
        company_name=result.company_name,
        title=result.title,
        location=result.location,
        work_mode=result.work_mode,
        source=result.source,
        source_url=result.source_url,
        description=result.description,
    )
    session.add(job)
    result.status = DiscoveryResultStatus.saved
    result.saved_job_id = job.id
    session.add(result)
    session.commit()
    session.refresh(job)
    return job
