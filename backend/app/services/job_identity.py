"""Stable identity for preventing duplicate saved jobs per user."""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.services.grounding import normalized_phrase

_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


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
