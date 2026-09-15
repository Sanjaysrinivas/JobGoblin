"""Small, deterministic helpers for keeping AI output tied to source text."""

import re
from typing import Any


def normalized_phrase(value: str) -> str:
    return " ".join(re.findall(r"[\w+#.-]+", value.casefold()))


def is_source_supported(value: object, source_text: str) -> bool:
    if not isinstance(value, str):
        return False
    candidate = normalized_phrase(value)
    return bool(candidate) and candidate in normalized_phrase(source_text)


def source_excerpts(source_text: str, *, limit: int = 8) -> list[str]:
    """Return substantive source sentences/lines suitable for verbatim evidence."""
    excerpts: list[str] = []
    seen: set[str] = set()
    for item in re.split(r"(?<=[.!?])\s+|[\r\n]+", source_text):
        excerpt = re.sub(r"^\s*[-*\u2022]\s*", "", item).strip()
        key = normalized_phrase(excerpt)
        if len(key) < 20 or key in seen or "@" in excerpt:
            continue
        seen.add(key)
        excerpts.append(excerpt)
        if len(excerpts) >= limit:
            break
    return excerpts


def _supported_strings(value: Any, source_text: str) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if is_source_supported(item, source_text)]


def ground_parsed_resume(value: Any, source_text: str) -> dict:
    """Drop model-extracted resume facts that cannot be found in the upload."""
    payload = value if isinstance(value, dict) else {}
    excerpts = source_excerpts(source_text, limit=2)
    summary = str(payload.get("summary") or "").strip()
    if not is_source_supported(summary, source_text):
        summary = " ".join(excerpts)[:500]

    experience: list[dict] = []
    for raw in payload.get("experience", []) if isinstance(payload.get("experience"), list) else []:
        if not isinstance(raw, dict):
            continue
        company = str(raw.get("company") or "").strip()
        role = str(raw.get("role") or "").strip()
        if not company or not role:
            continue
        if not is_source_supported(company, source_text) or not is_source_supported(
            role, source_text
        ):
            continue
        item: dict[str, Any] = {
            "company": company,
            "role": role,
            "highlights": _supported_strings(raw.get("highlights"), source_text),
        }
        for field in ("start", "end"):
            field_value = str(raw.get(field) or "").strip()
            if is_source_supported(field_value, source_text):
                item[field] = field_value
        experience.append(item)

    education: list[dict] = []
    for raw in payload.get("education", []) if isinstance(payload.get("education"), list) else []:
        if not isinstance(raw, dict):
            continue
        institution = str(raw.get("institution") or "").strip()
        credential = str(raw.get("credential") or "").strip()
        if not institution or not credential:
            continue
        if not is_source_supported(institution, source_text) or not is_source_supported(
            credential, source_text
        ):
            continue
        item = {"institution": institution, "credential": credential}
        year = str(raw.get("year") or "").strip()
        if is_source_supported(year, source_text):
            item["year"] = year
        education.append(item)

    return {
        "summary": summary,
        "skills": _supported_strings(payload.get("skills"), source_text),
        "experience": experience,
        "education": education,
        "projects": _supported_strings(payload.get("projects"), source_text),
        "certifications": _supported_strings(payload.get("certifications"), source_text),
    }
