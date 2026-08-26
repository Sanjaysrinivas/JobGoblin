"""Shared normalization and boundary-aware matching for job and resume text."""

import re
import unicodedata

TERM_ALIASES: dict[str, frozenset[str]] = {
    "api": frozenset(
        {
            "api",
            "apis",
            "application programming interface",
            "application programming interfaces",
        }
    ),
    "cd": frozenset({"cd", "continuous delivery", "continuous deployment"}),
    "ci": frozenset({"ci", "continuous integration"}),
    "javascript": frozenset({"javascript", "js"}),
    "kubernetes": frozenset({"kubernetes", "k8s"}),
    "machine learning": frozenset({"machine learning", "ml"}),
    "postgresql": frozenset({"postgresql", "postgres"}),
    "typescript": frozenset({"typescript", "ts"}),
}


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.translate(str.maketrans({"–": "-", "—": "-", "‑": "-"}))
    return re.sub(r"\s+", " ", normalized).strip()


def tokens(text: str) -> list[str]:
    """Return Unicode-aware tokens without consuming sentence punctuation."""
    return re.findall(r"(?u)(?:\.\w+|\w+(?:[+#]{1,2}|[.-]\w+)*)", normalize_text(text))


def canonical_term(term: str) -> str:
    normalized = normalize_text(term).strip(".,;:!?()[]{}\"'")
    for canonical, variants in TERM_ALIASES.items():
        if normalized in variants:
            return canonical
    return normalized


def term_variants(term: str) -> frozenset[str]:
    canonical = canonical_term(term)
    return TERM_ALIASES.get(canonical, frozenset({canonical}))


def contains_term(text: str, term: str) -> bool:
    if not canonical_term(term):
        return False
    normalized = normalize_text(text)
    return any(
        re.search(r"(?<!\w)" + re.escape(variant) + r"(?!\w)", normalized)
        for variant in term_variants(term)
    )


def _segments(text: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?])\s+|[\r\n;]+", text) if part.strip()]


def _unsupported_mention(segment: str, variant: str) -> bool:
    normalized = normalize_text(segment)
    pattern = re.compile(r"(?<!\w)" + re.escape(variant) + r"(?!\w)")
    for match in pattern.finditer(normalized):
        before = normalized[max(0, match.start() - 80) : match.start()]
        after = normalized[match.end() : match.end() + 50]
        if re.search(
            r"\b(?:no|without|lacks?|lacking)\W+(?:\w+\W+){0,5}$",
            before,
        ):
            continue
        if re.search(
            r"\b(?:not|never|cannot|can't|unable to|do not|does not)\b"
            r"(?:\W+\w+){0,5}\W*$",
            before,
        ):
            continue
        if re.search(
            r"\b(?:learning|learn|interested in|aspiring to)\b"
            r"(?:\W+\w+){0,4}\W*$",
            before,
        ):
            continue
        if re.match(
            r"\W*(?:\w+\W+){0,2}(?:is|are|was|were)?\W*(?:not (?:available|offered|provided|"
            r"required|supported)|unavailable)\b",
            after,
        ):
            continue
        return False
    return True


def contains_supported_term(text: str, term: str) -> bool:
    """Match a term only when at least one mention is asserted as present experience."""
    for segment in _segments(text):
        for variant in term_variants(term):
            if contains_term(segment, variant) and not _unsupported_mention(segment, variant):
                return True
    return False


def is_optional_or_negated_requirement(text: str) -> bool:
    normalized = normalize_text(text)
    return bool(
        re.search(
            r"\b(?:nice to have|preferred|optional|bonus|not required|"
            r"no [^.]{0,60} required|does not require|do not require)\b",
            normalized,
        )
    )
