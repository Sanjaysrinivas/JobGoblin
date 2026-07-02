"""Private profile-builder endpoints.

The profile is scoped to the authenticated user and stores only facts the user
entered or facts copied from one of that user's parsed resumes.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import Profile, Resume, User
from app.schemas.profile import ProfileOut, ProfileSeedRequest, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Profile not found", "profile_not_found")


def _resume_not_found() -> HTTPException:
    return _error(status.HTTP_404_NOT_FOUND, "Resume not found", "resume_not_found")


def _get_profile(session: Session, user_id: uuid.UUID) -> Profile | None:
    return session.exec(select(Profile).where(Profile.user_id == user_id)).first()


def _get_owned_resume(session: Session, user: User, resume_id: uuid.UUID) -> Resume:
    resume = session.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise _resume_not_found()
    return resume


def _apply_payload(profile: Profile, payload: ProfileUpdate) -> None:
    data = payload.model_dump(mode="json")
    for key, value in data.items():
        setattr(profile, key, value)


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _as_experience(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    items = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        company = str(raw.get("company") or "").strip()
        role = str(raw.get("role") or "").strip()
        if not company and not role:
            continue
        items.append(
            {
                "company": company,
                "role": role,
                "start": raw.get("start"),
                "end": raw.get("end"),
                "highlights": _as_string_list(raw.get("highlights")),
            }
        )
    return items


def _as_education(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    items = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        institution = str(raw.get("institution") or "").strip()
        credential = str(raw.get("credential") or "").strip()
        if not institution and not credential:
            continue
        items.append(
            {
                "institution": institution,
                "credential": credential,
                "year": raw.get("year"),
            }
        )
    return items


def _apply_parsed_sections(profile: Profile, parsed: dict) -> None:
    profile.summary = parsed.get("summary")
    profile.skills = _as_string_list(parsed.get("skills"))
    profile.experience = _as_experience(parsed.get("experience"))
    profile.education = _as_education(parsed.get("education"))
    profile.projects = _as_string_list(parsed.get("projects"))
    profile.certifications = _as_string_list(parsed.get("certifications"))


@router.get("", response_model=ProfileOut)
def get_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Profile:
    profile = _get_profile(session, current_user.id)
    if profile is None:
        raise _not_found()
    return profile


@router.put("", response_model=ProfileOut)
def save_profile(
    payload: ProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Profile:
    profile = _get_profile(session, current_user.id)
    if profile is None:
        profile = Profile(user_id=current_user.id)
    _apply_payload(profile, payload)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.post("/seed", response_model=ProfileOut)
def seed_profile_from_resume(
    payload: ProfileSeedRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Profile:
    resume = _get_owned_resume(session, current_user, payload.resume_id)
    if not isinstance(resume.parsed_json, dict):
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "Resume has no parsed profile sections.",
            "resume_not_parsed",
        )

    profile = _get_profile(session, current_user.id)
    if profile is None:
        profile = Profile(user_id=current_user.id)
    _apply_parsed_sections(profile, resume.parsed_json)
    profile.source_resume_id = resume.id
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    profile = _get_profile(session, current_user.id)
    if profile is None:
        raise _not_found()
    session.delete(profile)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)