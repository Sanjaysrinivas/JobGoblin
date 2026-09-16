"""Stable identity for preventing duplicate saved jobs per user."""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import Job, User
from app.services.grounding import normalized_phrase

_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


class JobIdentityConflict(Exception):
    """Another job owned by this user already holds the identity."""


def find_duplicate_job(
    session: Session,
    user: User,
    dedupe_key: str,
    *,
    exclude_id=None,
) -> Job | None:
    """Return the user's existing job with this identity, if any."""
    query = select(Job).where(Job.user_id == user.id, Job.dedupe_key == dedupe_key)
    if exclude_id is not None:
        query = query.where(Job.id != exclude_id)
    return session.exec(query).first()


def persist_job(session: Session, job: Job) -> Job:
    """Flush an identity-bearing job write without owning the transaction.

    Translates uniqueness races (two writers passing the pre-check) into
    JobIdentityConflict instead of leaking an IntegrityError. The caller
    commits only after every related domain change is staged.
    """
    session.add(job)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise JobIdentityConflict("A job with this identity already exists") from exc
    return job


def canonical_job_url(value: str) -> str:
    raw = value.strip()
    try:
        parsed = urlsplit(raw)
        port_value = parsed.port
    except ValueError:
        return normalized_phrase(raw)
    if not parsed.hostname:
        return normalized_phrase(raw)
    host = (parsed.hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    port = f":{port_value}" if port_value else ""
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_QUERY_KEYS
        )
    )
    return urlunsplit(
        ((parsed.scheme or "https").casefold(), f"{host}{port}", parsed.path.rstrip("/"), query, "")
    )


def job_dedupe_key(
    source_url: str | None,
    company_name: str,
    title: str,
    location: str | None,
) -> str:
    if source_url:
        identity = f"url:{canonical_job_url(source_url)}"
    else:
        identity = "|".join(
            [
                "fields",
                normalized_phrase(company_name),
                normalized_phrase(title),
                normalized_phrase(location or ""),
            ]
        )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()
