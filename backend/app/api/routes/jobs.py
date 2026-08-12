"""Authenticated CRUD endpoints for jobs.

All reads and writes are scoped to the current user. Cross-user access returns
404 so job existence is not leaked.
"""

import copy
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.api.routes.analysis import analysis_response
from app.core.database import get_session
from app.core.observability import record_llm_fallback
from app.models import Job, JobAnalysis, Profile, Resume, ResumeVersion, User
from app.schemas.analysis import JobAnalysisOut
from app.schemas.job import JobCreate, JobOut, JobUpdate
from app.schemas.resume import ResumeVersionOut, TailoredResumeDraftCreate
from app.services.ai_provider import AIProvider, get_ai_provider

router = APIRouter(prefix="/jobs", tags=["jobs"])

_AI_TAILORING_SYSTEM = (
    "You tailor resume copies for a private job-search workspace. Never invent "
    "skills, employers, credentials, dates, education, projects, metrics, or "
    "experience. Use only facts present in the supplied resume/profile context. "
    "Return JSON only."
)

_AI_TAILORING_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "skills": {"type": "array", "items": {"type": "string"}},
        "change_notes": {"type": "array", "items": {"type": "string"}},
    },
}


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Job not found", "job_not_found")


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


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _dicts(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _contains(text: str, value: str) -> bool:
    return value.casefold() in text.casefold()


def _provider_name(provider: AIProvider) -> str:
    return provider.__class__.__name__.replace("Provider", "").lower()


def _latest_analysis(
    session: Session,
    user: User,
    job: Job,
    resume: Resume,
) -> JobAnalysis | None:
    return session.exec(
        select(JobAnalysis)
        .where(
            JobAnalysis.user_id == user.id,
            JobAnalysis.job_id == job.id,
            JobAnalysis.resume_id == resume.id,
        )
        .order_by(JobAnalysis.created_at.desc())
    ).first()


def _ai_tailoring_prompt(
    job: Job,
    source_text: str,
    source_json: dict,
    matched: list[str],
    missing: list[str],
) -> str:
    return (
        "Create a concise tailored resume copy for this job. Rewrite only the "
        "summary and reorder existing skills. Do not add terms listed under "
        "'verify before adding' unless the resume context already proves them.\n\n"
        f"Job: {job.title} at {job.company_name}\n"
        f"Job description:\n{job.description[:4000]}\n\n"
        f"Existing matched evidence: {', '.join(matched) or 'none'}\n"
        f"Verify before adding: {', '.join(missing) or 'none'}\n\n"
        f"Resume text:\n{source_text[:5000]}\n\n"
        f"Parsed resume JSON:\n{source_json}"
    )


async def _ai_tailoring(
    provider: AIProvider,
    job: Job,
    source_text: str,
    source_json: dict,
    matched: list[str],
    missing: list[str],
) -> dict | None:
    try:
        payload = await provider.generate_json(
            _ai_tailoring_prompt(job, source_text, source_json, matched, missing),
            _AI_TAILORING_SCHEMA,
            system=_AI_TAILORING_SYSTEM,
        )
    except Exception as exc:
        record_llm_fallback(
            provider=_provider_name(provider),
            model=str(getattr(provider, "_model", _provider_name(provider))),
            operation="resume.tailor_json",
            reason=type(exc).__name__,
        )
        return None
    return payload if isinstance(payload, dict) else None


def _apply_ai_tailoring(
    source_json: dict,
    payload: dict | None,
    *,
    matched: list[str],
    missing: list[str],
    changes: list[dict],
    diff: list[dict],
) -> bool:
    if not payload:
        return False
    applied = False
    current_summary = source_json.get("summary")
    summary = str(payload.get("summary") or "").strip()
    if (
        summary
        and summary.casefold() != "sample"
        and isinstance(current_summary, str)
        and summary != current_summary
        and not any(_contains(summary, term) for term in missing)
    ):
        source_json["summary"] = summary
        changes.append(
            {
                "section": "summary",
                "action": "ai_rewrite",
                "why": "AI rewrote the summary using existing resume evidence.",
                "evidence": matched[:5],
            }
        )
        diff.append({"section": "summary", "before": current_summary, "after": summary})
        applied = True

    current_skills = _strings(source_json.get("skills"))
    by_key = {skill.casefold(): skill for skill in current_skills}
    ai_skills = [
        by_key[item.casefold()]
        for item in _strings(payload.get("skills"))
        if item.casefold() in by_key
    ]
    reordered = _unique([*ai_skills, *current_skills])
    if reordered and reordered != current_skills:
        source_json["skills"] = reordered
        changes.append(
            {
                "section": "skills",
                "action": "ai_reorder_existing_skills",
                "why": "AI reordered only skills already present in the source resume.",
                "evidence": ai_skills[:8],
            }
        )
        diff.append({"section": "skills", "before": current_skills, "after": reordered})
        applied = True
    return applied


async def _tailored_resume_json(
    session: Session,
    user: User,
    job: Job,
    resume: Resume,
    source: ResumeVersion | None,
    provider: AIProvider,
) -> tuple[dict, str]:
    source_json = copy.deepcopy(source.parsed_json if source else resume.parsed_json) or {}
    if not isinstance(source_json, dict):
        source_json = {}
    source_title = source.title if source else resume.title
    source_text = source.extracted_text if source else resume.extracted_text
    source_text = source_text or ""
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    analysis = _latest_analysis(session, user, job, resume)

    resume_skills = _strings(source_json.get("skills"))
    profile_skills = _strings(profile.skills if profile else None)
    profile_projects = _strings(profile.projects if profile else None)
    profile_certifications = _strings(profile.certifications if profile else None)
    profile_experience = _dicts(profile.experience if profile else None)
    all_skills = _unique([*resume_skills, *profile_skills])
    job_text = f"{job.title}\n{job.company_name}\n{job.description}"
    analysis_matches = _strings(analysis.matched_keywords if analysis else None)
    source_blob = "\n".join(
        [
            source_text,
            str(source_json.get("summary") or ""),
            "\n".join(all_skills),
            "\n".join(profile_projects),
            "\n".join(profile_certifications),
        ]
    )
    matched = _unique(
        [
            item
            for item in [*analysis_matches, *all_skills]
            if _contains(job_text, item) and _contains(source_blob, item)
        ]
    )[:10]
    missing = [
        item
        for item in _strings(analysis.missing_keywords if analysis else None)
        if not _contains(source_blob, item)
    ][:10]

    changes: list[dict] = []
    diff: list[dict] = []
    summary = source_json.get("summary")
    if isinstance(summary, str) and summary.strip() and matched:
        after = f"{summary.strip()}\nFocus for this role: {', '.join(matched[:4])}."
        source_json["summary"] = after
        changes.append(
            {
                "section": "summary",
                "action": "append_focus",
                "why": (
                    "Uses only existing resume/profile terms that also appear in the job "
                    "or stored analysis."
                ),
                "evidence": matched[:4],
            }
        )
        diff.append({"section": "summary", "before": summary, "after": after})

    if resume_skills and matched:
        reordered = _unique([*matched, *resume_skills])
        if reordered != resume_skills:
            source_json["skills"] = reordered
            changes.append(
                {
                    "section": "skills",
                    "action": "move_matching_existing_skills_first",
                    "why": (
                        "Prioritizes skills already present in the resume/profile and relevant "
                        "to the job text."
                    ),
                    "evidence": matched,
                }
            )
            diff.append({"section": "skills", "before": resume_skills, "after": reordered})

    highlight_matches: list[dict] = []
    for item in [*_dicts(source_json.get("experience")), *profile_experience]:
        highlights = _strings(item.get("highlights"))
        matched_highlights = [
            highlight
            for highlight in highlights
            if any(_contains(highlight, term) for term in matched)
        ]
        if matched_highlights:
            highlight_matches.append(
                {
                    "company": item.get("company"),
                    "role": item.get("role"),
                    "highlights": matched_highlights[:2],
                }
            )
    if highlight_matches:
        changes.append(
            {
                "section": "experience",
                "action": "emphasize_existing_matching_bullets",
                "why": "These bullets already exist and overlap with the job or stored analysis.",
                "evidence": highlight_matches[:5],
            }
        )

    if missing:
        changes.append(
            {
                "section": "gaps",
                "action": "verify_before_adding",
                "why": "These job/analysis terms were not found in resume/profile text.",
                "evidence": missing,
            }
        )

    ai_payload = await _ai_tailoring(provider, job, source_text, source_json, matched, missing)
    ai_applied = _apply_ai_tailoring(
        source_json,
        ai_payload,
        matched=matched,
        missing=missing,
        changes=changes,
        diff=diff,
    )

    source_json["tailored_for"] = {
        "job_id": str(job.id),
        "title": job.title,
        "company_name": job.company_name,
    }
    source_json["tailoring"] = {
        "source": {
            "resume_id": str(resume.id),
            "source_version_id": str(source.id) if source else None,
            "source_version_title": source_title,
            "profile_id": str(profile.id) if profile else None,
            "analysis_id": str(analysis.id) if analysis else None,
        },
        "grounding": {
            "rule": (
                "Generated from stored resume/profile/job/analysis text only; missing "
                "terms are not added as skills or credentials."
            ),
            "matched_existing_terms": matched,
            "job_terms_not_added": missing,
        },
        "ai": {
            "provider": _provider_name(provider),
            "status": "applied" if ai_applied else "fallback",
        },
        "suggested_changes": changes,
        "diff": diff,
    }

    notes = [
        "",
        "",
        "Tailoring notes (grounded)",
        f"Target role: {job.title} at {job.company_name}",
    ]
    if matched:
        notes.append("Existing evidence to emphasize:")
        notes.extend(f"- {item}" for item in matched[:8])
    if missing:
        notes.append("Verify before adding:")
        notes.extend(f"- {item}" for item in missing[:8])
    return source_json, source_text + "\n".join(notes)

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
    job = Job(user_id=current_user.id, **payload.model_dump())
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


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
    source_title = source.title if source else resume.title
    parsed_json, extracted_text = await _tailored_resume_json(
        session, current_user, job, resume, source, get_ai_provider()
    )
    draft = ResumeVersion(
        resume_id=resume.id,
        job_id=job.id,
        source_version_id=source.id if source else None,
        title=payload.title or f"{source_title} - {job.company_name} {job.title}",
        extracted_text=extracted_text,
        parsed_json=parsed_json,
        is_current=False,
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft


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
    for field, value in updates.items():
        setattr(job, field, value)

    session.add(job)
    session.commit()
    session.refresh(job)
    return job


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
