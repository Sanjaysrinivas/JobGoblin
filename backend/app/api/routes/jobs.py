"""Authenticated CRUD endpoints for jobs.

All reads and writes are scoped to the current user. Cross-user access returns
404 so job existence is not leaked.
"""

import ipaddress
import re
import socket
import uuid
from html.parser import HTMLParser
from typing import Annotated
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.api.routes.analysis import analysis_response
from app.core.database import get_session
from app.core.observability import record_llm_fallback
from app.models import Job, JobAnalysis, Resume, ResumeVersion, User
from app.schemas.analysis import JobAnalysisOut
from app.schemas.job import JobCreate, JobImportRequest, JobOut, JobUpdate
from app.schemas.resume import ResumeVersionOut, TailoredResumeDraftCreate
from app.services.ai_provider import AIProvider, get_ai_provider, provider_name
from app.services.job_identity import (
    JobIdentityConflict,
    find_duplicate_job,
    job_dedupe_key,
    persist_job,
)
from app.services.tailored_resumes import create_tailored_draft

router = APIRouter(prefix="/jobs", tags=["jobs"])


_AI_JOB_IMPORT_SYSTEM = (
    "You extract structured fields from job postings for a private job-search workspace. "
    "Use only the supplied text. Return JSON only. Use null for unknown optional fields."
)

_AI_JOB_IMPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string"},
        "title": {"type": "string"},
        "location": {"type": "string"},
        "work_mode": {"type": "string"},
        "source": {"type": "string"},
        "source_url": {"type": "string"},
        "description": {"type": "string"},
        "salary_min": {"type": "integer"},
        "salary_max": {"type": "integer"},
        "currency": {"type": "string"},
        "priority": {"type": "string"},
    },
    "required": ["company_name", "title", "description"],
}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        if tag in {"p", "br", "li", "div", "section", "article", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            text = data.strip()
            if text:
                self.parts.append(text)


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Job not found", "job_not_found")


def _normalise_space(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def _source_from_url(url: str | None):
    if not url:
        return "other"
    host = urlparse(url).netloc.lower()
    if "linkedin." in host:
        return "linkedin"
    if "indeed." in host:
        return "indeed"
    return "company_site"


def _work_mode(text: str) -> str:
    lower = text.lower()
    if "hybrid" in lower:
        return "hybrid"
    if any(term in lower for term in ("remote", "work from home", "wfh")):
        return "remote"
    if any(term in lower for term in ("on-site", "onsite", "office based")):
        return "onsite"
    return "unknown"


def _clean_optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.lower() in {"sample", "null", "none", "unknown", "n/a"}:
        return None
    return text


def _clean_enum(value: object, allowed: set[str], default: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else default


def _clean_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(float(str(value).replace(",", "").strip()))
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _salary_from_text(text: str) -> tuple[int | None, int | None, str | None]:
    salary_lines = [
        line
        for line in text.splitlines()
        if re.search(r"\b(salary|compensation|gross|annual|base)\b|[€$£]", line, flags=re.I)
    ]
    blob = "\n".join(salary_lines[:8])
    currency = None
    if "€" in blob or re.search(r"\beur\b", blob, flags=re.I):
        currency = "EUR"
    elif "£" in blob or re.search(r"\bgbp\b", blob, flags=re.I):
        currency = "GBP"
    elif "$" in blob or re.search(r"\busd\b", blob, flags=re.I):
        currency = "USD"
    numbers = []
    for raw in re.findall(r"(?<!\d)(\d{2,3}(?:[.,]\d{3})+|\d{5,6})(?!\d)", blob):
        cleaned = int(re.sub(r"[.,]", "", raw))
        if cleaned >= 1000:
            numbers.append(cleaned)
    if not numbers:
        return None, None, currency
    if len(numbers) == 1:
        return numbers[0], None, currency
    return min(numbers), max(numbers), currency


def _reject_private_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use an http(s) job URL.", "bad_url")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Could not resolve URL.", "bad_url"
        ) from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "URL points to a private network address.",
                "bad_url",
            )
    return parsed.geturl()


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return _normalise_space("\n".join(parser.parts))


def _trim_job_text(text: str) -> str:
    start_markers = (
        "about the role",
        "job description",
        "about the job",
        "the role",
        "main responsibilities",
    )
    end_markers = (
        "our application process",
        "similar job",
        "share this job",
        "recommended jobs",
    )
    lower = text.lower()
    start = min((lower.find(marker) for marker in start_markers if marker in lower), default=-1)
    end = -1
    if start >= 0:
        end = min(
            (
                lower.find(marker, start + 20)
                for marker in end_markers
                if lower.find(marker, start + 20) >= 0
            ),
            default=-1,
        )
    if start >= 0 and end > start:
        prelude = text[max(0, start - 800) : start]
        marker = prelude.lower().rfind("find a job")
        if marker >= 0:
            prelude = prelude[marker:]
        trimmed = prelude + text[start:end]
    elif start >= 0:
        trimmed = text[start:]
    else:
        trimmed = text
    return _normalise_space(trimmed)


async def _fetch_job_url(url: str) -> tuple[str, str]:
    current = _reject_private_url(url)
    headers = {"User-Agent": "JobGoblin/0.1 (+local job import)"}
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        for _ in range(4):
            response = await client.get(current, headers=headers)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    break
                current = _reject_private_url(urljoin(current, location))
                continue
            response.raise_for_status()
            text = _trim_job_text(_html_to_text(response.text))
            if len(text) < 200:
                raise _error(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "Could not extract enough job text from this URL. "
                    "Paste the posting text instead.",
                    "url_not_parseable",
                )
            return text[:50000], current
    raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Too many redirects.", "bad_url")


def _heuristic_job_payload(text: str, source_url: str | None) -> dict:
    lines = [line.strip(" -|") for line in text.splitlines() if line.strip()]
    title = lines[0] if lines else "Untitled role"
    company = "Unknown company"
    for line in lines[:12]:
        match = re.search(r"\bat\s+(.+)$", line, flags=re.I)
        if match:
            company = match.group(1).strip()
            break
    if company == "Unknown company" and len(lines) > 1:
        company = lines[1]
    location = None
    for line in lines[:25]:
        if re.search(r"\((hybrid|remote|on-site|onsite)\)", line, flags=re.I):
            location = line[:255]
            break
        if re.search(r"\b(location|city|based in)\b", line, flags=re.I):
            location = re.sub(r"^\s*(location|city)\s*:\s*", "", line, flags=re.I)[:255]
            break
    salary_min, salary_max, currency = _salary_from_text(text)
    return {
        "company_name": company[:255],
        "title": title[:255],
        "location": location,
        "work_mode": _work_mode(text),
        "source": _source_from_url(source_url),
        "source_url": source_url,
        "description": text,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "currency": currency,
        "priority": "medium",
    }


async def _ai_job_payload(text: str, source_url: str | None, provider: AIProvider) -> dict:
    try:
        payload = await provider.generate_json(
            (
                "Extract the job fields from this posting. Preserve the useful full job "
                "description. Allowed work_mode: remote, hybrid, onsite, unknown. "
                "Allowed source: linkedin, company_site, indeed, referral, recruiter, other. "
                "Allowed priority: low, medium, high. Infer salary_min/salary_max/currency only "
                "when explicitly present.\n\n"
                f"Source URL: {source_url or 'none'}\n\nPosting:\n{text[:12000]}"
            ),
            _AI_JOB_IMPORT_SCHEMA,
            system=_AI_JOB_IMPORT_SYSTEM,
        )
    except Exception as exc:
        record_llm_fallback(
            provider=provider_name(provider),
            model=str(getattr(provider, "_model", provider_name(provider))),
            operation="jobs.import_json",
            reason=type(exc).__name__,
        )
        return {}
    return payload if isinstance(payload, dict) else {}


def _merged_job_payload(text: str, source_url: str | None, ai_payload: dict) -> JobCreate:
    fallback = _heuristic_job_payload(text, source_url)
    ai_description = _clean_optional_string(ai_payload.get("description"))
    description = text
    if ai_description and len(ai_description) >= min(800, len(text) // 2):
        description = ai_description
    merged = {
        **fallback,
        "company_name": (
            _clean_optional_string(ai_payload.get("company_name")) or fallback["company_name"]
        ),
        "title": _clean_optional_string(ai_payload.get("title")) or fallback["title"],
        "location": _clean_optional_string(ai_payload.get("location")) or fallback["location"],
        "work_mode": (
            fallback["work_mode"]
            if fallback["work_mode"] != "unknown"
            else _clean_enum(
                ai_payload.get("work_mode"),
                {"remote", "hybrid", "onsite", "unknown"},
                fallback["work_mode"],
            )
        ),
        "source": _clean_enum(
            ai_payload.get("source"),
            {"linkedin", "company_site", "indeed", "referral", "recruiter", "other"},
            fallback["source"],
        ),
        "source_url": _clean_optional_string(ai_payload.get("source_url")) or source_url,
        "description": description,
        "salary_min": _clean_int(ai_payload.get("salary_min")) or fallback["salary_min"],
        "salary_max": _clean_int(ai_payload.get("salary_max")) or fallback["salary_max"],
        "currency": _clean_optional_string(ai_payload.get("currency")) or fallback["currency"],
        "priority": _clean_enum(ai_payload.get("priority"), {"low", "medium", "high"}, "medium"),
    }
    if merged["source_url"] is None:
        merged["source_url"] = source_url
    _validate_salary_range(merged["salary_min"], merged["salary_max"])
    return JobCreate(**merged)


def _get_owned_job(session: Session, user: User, job_id: uuid.UUID) -> Job:
    job = session.exec(select(Job).where(Job.id == job_id, Job.user_id == user.id)).first()
    if job is None:
        raise _not_found()
    return job


def _resume_not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Resume not found", "resume_not_found")


def _version_not_found() -> HTTPException:
    return _error(
        status.HTTP_404_NOT_FOUND,
        "Resume version not found",
        "resume_version_not_found",
    )


def _get_owned_resume(session: Session, user: User, resume_id: uuid.UUID) -> Resume:
    resume = session.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise _resume_not_found()
    return resume


def _get_source_version(
    session: Session,
    resume: Resume,
    source_version_id: uuid.UUID | None,
) -> ResumeVersion | None:
    if source_version_id is not None:
        version = session.get(ResumeVersion, source_version_id)
        if version is None or version.resume_id != resume.id:
            raise _version_not_found()
        return version
    return session.exec(
        select(ResumeVersion)
        .where(
            ResumeVersion.resume_id == resume.id,
            ResumeVersion.is_current == True,  # noqa: E712 - SQLAlchemy expression
        )
        .order_by(ResumeVersion.updated_at.desc())
    ).first()


def _validate_salary_range(salary_min: int | None, salary_max: int | None) -> None:
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "salary_min must be less than or equal to salary_max",
            "invalid_salary_range",
        )


@router.get("", response_model=list[JobOut])
def list_jobs(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[Job]:
    return list(
        session.exec(
            select(Job).where(Job.user_id == current_user.id).order_by(Job.created_at.desc())
        ).all()
    )


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Job:
    _validate_salary_range(payload.salary_min, payload.salary_max)
    dedupe_key = job_dedupe_key(
        payload.source_url, payload.company_name, payload.title, payload.location
    )
    if find_duplicate_job(session, current_user, dedupe_key):
        raise _error(status.HTTP_409_CONFLICT, "This job is already saved", "job_exists")
    job = Job(user_id=current_user.id, dedupe_key=dedupe_key, **payload.model_dump())
    try:
        return persist_job(session, job)
    except JobIdentityConflict as exc:
        raise _error(status.HTTP_409_CONFLICT, "This job is already saved", "job_exists") from exc


@router.post("/import", response_model=JobCreate)
async def import_job(
    payload: JobImportRequest,
    _current_user: Annotated[User, Depends(get_current_user)],
) -> JobCreate:
    source_url = payload.content if payload.mode == "url" else None
    text = payload.content
    if payload.mode == "url":
        text, source_url = await _fetch_job_url(payload.content)
    ai_payload = await _ai_job_payload(text, source_url, get_ai_provider())
    return _merged_job_payload(text, source_url, ai_payload)


@router.post(
    "/{job_id}/resume-drafts",
    response_model=ResumeVersionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_resume_draft(
    job_id: uuid.UUID,
    payload: TailoredResumeDraftCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> ResumeVersion:
    job = _get_owned_job(session, current_user, job_id)
    resume = _get_owned_resume(session, current_user, payload.resume_id)
    source = _get_source_version(session, resume, payload.source_version_id)
    return await create_tailored_draft(
        session,
        current_user,
        job,
        resume,
        source,
        get_ai_provider(),
        title=payload.title,
    )


@router.get("/{job_id}/resume-drafts", response_model=list[ResumeVersionOut])
def list_resume_drafts(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ResumeVersion]:
    job = _get_owned_job(session, current_user, job_id)
    return list(
        session.exec(
            select(ResumeVersion)
            .join(Resume, Resume.id == ResumeVersion.resume_id)
            .where(
                Resume.user_id == current_user.id,
                ResumeVersion.job_id == job.id,
            )
            .order_by(ResumeVersion.updated_at.desc())
        ).all()
    )


@router.get("/{job_id}/analysis", response_model=list[JobAnalysisOut])
def list_job_analyses(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict]:
    _get_owned_job(session, current_user, job_id)
    analyses = session.exec(
        select(JobAnalysis)
        .where(JobAnalysis.job_id == job_id, JobAnalysis.user_id == current_user.id)
        .order_by(JobAnalysis.created_at.desc())
    )
    return [analysis_response(session, analysis) for analysis in analyses]


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Job:
    return _get_owned_job(session, current_user, job_id)


@router.patch("/{job_id}", response_model=JobOut)
def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Job:
    job = _get_owned_job(session, current_user, job_id)
    updates = payload.model_dump(exclude_unset=True)
    _validate_salary_range(
        updates.get("salary_min", job.salary_min),
        updates.get("salary_max", job.salary_max),
    )
    identity = {
        "source_url": updates.get("source_url", job.source_url),
        "company_name": updates.get("company_name", job.company_name),
        "title": updates.get("title", job.title),
        "location": updates.get("location", job.location),
    }
    dedupe_key = job_dedupe_key(**identity)
    if find_duplicate_job(session, current_user, dedupe_key, exclude_id=job.id):
        raise _error(status.HTTP_409_CONFLICT, "This job is already saved", "job_exists")
    for field, value in updates.items():
        setattr(job, field, value)
    job.dedupe_key = dedupe_key

    try:
        return persist_job(session, job)
    except JobIdentityConflict as exc:
        raise _error(status.HTTP_409_CONFLICT, "This job is already saved", "job_exists") from exc


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    job = _get_owned_job(session, current_user, job_id)
    session.delete(job)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
