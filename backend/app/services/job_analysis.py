"""Resume-to-job analysis service.

The deterministic portion is intentionally simple and stable: extract job terms,
match them against resume text and parsed skills, then compute weighted category
contributions that add up to the persisted overall estimate. AI is used only for
the explanatory narrative and recommendations.
"""

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz

from app.core.config import get_settings
from app.models import Job, Resume
from app.services.ai_provider import AIProvider
from app.services.text_matching import (
    canonical_term,
    contains_supported_term,
    contains_term,
    is_optional_or_negated_requirement,
    normalize_text,
    term_variants,
    tokens,
)

KEYWORD_WEIGHT = 35
SKILLS_WEIGHT = 30
EXPERIENCE_WEIGHT = 20
ROLE_WEIGHT = 10
EDUCATION_WEIGHT = 5
FORMATTING_WEIGHT = 0

MAX_KEYWORDS = 20
FUZZY_THRESHOLD = 88

ANALYSIS_NARRATIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string"},
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["explanation", "recommendations"],
}

_SYSTEM = (
    "You explain resume-to-job fit. Do not fabricate experience, skills, "
    "education, credentials, employers, or dates. Base recommendations only on "
    "the provided resume text, job text, and deterministic score summary."
)

_STOPWORDS = {
    "a",
    "about",
    "ability",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "candidate",
    "company",
    "excellent",
    "experience",
    "has",
    "ideal",
    "include",
    "including",
    "for",
    "from",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "the",
    "their",
    "into",
    "join",
    "key",
    "knowledge",
    "looking",
    "minimum",
    "motivated",
    "must",
    "position",
    "preferred",
    "required",
    "requirements",
    "responsibilities",
    "role",
    "skills",
    "team",
    "this",
    "to",
    "through",
    "strong",
    "we",
    "will",
    "working",
    "with",
    "years",
    "you",
    "your",
}

_KNOWN_SKILLS = (
    "python",
    "fastapi",
    "django",
    "flask",
    "sql",
    "postgresql",
    "mysql",
    "redis",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "gcp",
    "terraform",
    "react",
    "typescript",
    "javascript",
    "node",
    "api",
    "rest",
    "graphql",
    "pytest",
    "ci",
    "cd",
    "git",
    "linux",
    "machine learning",
    "data pipelines",
    "leadership",
    "mentoring",
    "agile",
    "lean-agile",
    "project management",
    "project lifecycle",
    "stakeholder engagement",
    "change management",
    "risk management",
    "status reporting",
    "business needs",
    "process optimization",
    "ai",
    "artificial intelligence",
    "llm",
    "excel",
    "pivot tables",
    "powerpoint",
    "copilot",
)

_ROLE_TERMS = {
    "backend",
    "frontend",
    "fullstack",
    "full",
    "stack",
    "platform",
    "data",
    "engineer",
    "developer",
    "manager",
    "lead",
    "senior",
    "principal",
    "qa",
    "ui",
    "ux",
    "pm",
    "it",
    "hr",
    "dev",
    "ops",
}

_EDUCATION_TERMS = {
    "associate",
    "degree",
    "bachelor",
    "bachelors",
    "bsc",
    "doctorate",
    "doctoral",
    "master",
    "masters",
    "msc",
    "phd",
    "computer science",
    "education",
}

@dataclass(frozen=True)
class DeterministicScores:
    keyword_score: int
    skills_score: int
    experience_score: int
    role_score: int
    education_score: int
    formatting_score: int
    matched_keywords: list[str]
    missing_keywords: list[str]

    @property
    def overall_score(self) -> int:
        return (
            self.keyword_score
            + self.skills_score
            + self.experience_score
            + self.role_score
            + self.education_score
            + self.formatting_score
        )


@dataclass(frozen=True)
class JobAnalysisResult:
    overall_score: int
    keyword_score: int
    skills_score: int
    experience_score: int
    role_score: int
    education_score: int
    formatting_score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    recommendations: list[str]
    explanation: str


GUIDANCE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Project management",
        (
            "project management",
            "project lifecycle",
            "agile",
            "lean-agile",
            "risk management",
            "dependencies",
            "stakeholder engagement",
            "status reporting",
            "deliverables",
            "scope",
        ),
    ),
    (
        "AI and data",
        (
            "ai",
            "artificial intelligence",
            "llm",
            "machine learning",
            "data",
            "data quality",
            "data analysis",
            "analytics",
            "automation",
        ),
    ),
    (
        "Tools",
        (
            "python",
            "sql",
            "excel",
            "pivot tables",
            "powerpoint",
            "word",
            "copilot",
            "power bi",
            "tableau",
            "databricks",
        ),
    ),
    (
        "Business change",
        (
            "business needs",
            "change management",
            "adoption",
            "process optimization",
            "operational efficiency",
            "communication",
            "presentation",
        ),
    ),
    (
        "Education and logistics",
        (
            "degree",
            "bachelor",
            "master",
            "english",
            "luxembourg",
            "hybrid",
        ),
    ),
)


def fit_label(score: int) -> str:
    if score >= 75:
        return "Strong match"
    if score >= 45:
        return "Stretch match"
    return "Weak match"


def application_readiness(score: int, missing_keywords: list[str]) -> str:
    has_missing_skill = any(canonical_term(term) in _KNOWN_SKILLS for term in missing_keywords)
    if score >= 75 and len(missing_keywords) <= 3 and not has_missing_skill:
        return "Ready to apply"
    if score >= 45:
        return "Needs tailoring"
    return "Not ready"


def keyword_checklist(
    resume_text: str,
    parsed_resume: dict | None,
    job_title: str,
    job_description: str,
) -> list[dict[str, object]]:
    job_text = _core_job_text(job_title, job_description)
    candidates = _resume_candidates(resume_text, parsed_resume)
    groups: list[dict[str, object]] = []
    for label, terms in GUIDANCE_GROUPS:
        required = [term for term in terms if _contains_term(job_text, term)]
        if not required:
            continue
        matched = [term for term in required if _matches_term(term, resume_text, candidates)]
        missing = [term for term in required if term not in matched]
        groups.append({"label": label, "matched": matched, "missing": missing})
    return groups


def readiness_steps(
    score: int,
    checklist: list[dict[str, object]],
) -> list[str]:
    steps: list[str] = []
    if score < 75:
        steps.append("Tailor the resume before applying.")
    for group in checklist:
        missing = group["missing"]
        if isinstance(missing, list) and missing:
            shown = ", ".join(str(item) for item in missing[:3])
            steps.append(f"Verify and add truthful evidence for {group['label']}: {shown}.")
    return steps[:5] or ["Review the final resume and apply."]


def rewrite_suggestions(
    checklist: list[dict[str, object]],
    matched_keywords: list[str],
    missing_keywords: list[str],
) -> list[dict[str, object]]:
    matched = ", ".join(matched_keywords[:5]) or "the strongest matched evidence"
    suggestions = [
        {
            "section": "Summary",
            "action": "Position the candidate around the target role.",
            "prompt": f"Rewrite the summary to connect {matched} to the job's business outcome.",
            "verify_before_adding": missing_keywords[:5],
        },
        {
            "section": "Experience",
            "action": "Move delivery and stakeholder bullets higher.",
            "prompt": (
                "Reframe existing bullets around project delivery, business needs, "
                "adoption, and measurable impact."
            ),
            "verify_before_adding": [],
        },
    ]
    missing_by_group = [
        f"{group['label']}: {', '.join(str(item) for item in group['missing'][:3])}"
        for group in checklist
        if isinstance(group["missing"], list) and group["missing"]
    ]
    if missing_by_group:
        suggestions.append(
            {
                "section": "ATS checklist",
                "action": "Fill only truthful gaps.",
                "prompt": (
                    "Add missing terms only where the resume can prove them with real "
                    "experience."
                ),
                "verify_before_adding": missing_by_group[:5],
            }
        )
    return suggestions


def _normalize_text(text: str) -> str:
    return normalize_text(text)


def _tokens(text: str) -> list[str]:
    return tokens(text)


def _meaningful_tokens(text: str) -> list[str]:
    meaningful: list[str] = []
    for token in _tokens(text):
        canonical = canonical_term(token)
        if len(canonical) >= 3 and canonical not in _STOPWORDS and not canonical.isdigit():
            meaningful.append(canonical)
    return meaningful


def _ngrams(tokens: list[str], size: int) -> set[str]:
    return {" ".join(tokens[i : i + size]) for i in range(max(0, len(tokens) - size + 1))}


def _term_variants(term: str) -> set[str]:
    return set(term_variants(term))


def _contains_term(text: str, term: str) -> bool:
    return contains_term(text, term)


def _core_job_text(job_title: str, job_description: str) -> str:
    segments = re.split(r"(?<=[.!?])\s+|[\r\n;]+", job_description)
    required = [
        segment
        for segment in segments
        if segment.strip() and not is_optional_or_negated_requirement(segment)
    ]
    return "\n".join([job_title, *required])


def extract_job_keywords(job_text: str, *, max_keywords: int = MAX_KEYWORDS) -> list[str]:
    """Return stable job keywords, preferring known skills before general terms."""
    normalized = _normalize_text(job_text)
    found: list[str] = [skill for skill in _KNOWN_SKILLS if _contains_term(normalized, skill)]

    tokens = _meaningful_tokens(normalized)
    counts = Counter(tokens)
    first_seen = {}
    for index, token in enumerate(tokens):
        first_seen.setdefault(token, index)
    ranked = sorted(counts, key=lambda token: (-counts[token], first_seen[token], token))

    for token in ranked:
        if token not in found:
            found.append(token)
        if len(found) >= max_keywords:
            break

    return found[:max_keywords]


def _parsed_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(_parsed_strings(item))
        return strings
    if isinstance(value, dict):
        strings = []
        for item in value.values():
            strings.extend(_parsed_strings(item))
        return strings
    return []


def _resume_candidates(resume_text: str, parsed_resume: dict | None) -> set[str]:
    terms = set(_meaningful_tokens(resume_text))
    terms.update(_ngrams(_meaningful_tokens(resume_text), 2))
    terms.update(_ngrams(_meaningful_tokens(resume_text), 3))
    if parsed_resume:
        for value in _parsed_strings(parsed_resume):
            terms.update(_meaningful_tokens(value))
            normalized = _normalize_text(value)
            if normalized:
                terms.add(normalized)
    return terms


def _matches_term(term: str, resume_text: str, candidates: set[str]) -> bool:
    if contains_supported_term(resume_text, term):
        return True
    variants = _term_variants(term)
    if any(
        variant in candidates and not _contains_term(resume_text, variant)
        for variant in variants
    ):
        return True
    for variant in variants:
        variant_length = len(variant)
        max_diff = max(1, int(variant_length * 0.15))
        eligible_candidates = [
            candidate
            for candidate in candidates
            if abs(len(candidate) - variant_length) <= max_diff
            and (
                not _contains_term(resume_text, candidate)
                or contains_supported_term(resume_text, candidate)
            )
        ]
        if any(
            fuzz.ratio(variant, candidate) >= FUZZY_THRESHOLD for candidate in eligible_candidates
        ):
            return True
    return False


def _weighted_score(weight: int, matched: int, total: int) -> int:
    if total <= 0:
        return 0
    return round(weight * (matched / total))


def _skills_in(text: str) -> list[str]:
    normalized = _normalize_text(text)
    return [skill for skill in _KNOWN_SKILLS if _contains_term(normalized, skill)]


def _score_experience(job_text: str, resume_text: str, parsed_resume: dict | None) -> int:
    has_parsed_experience = bool(parsed_resume and parsed_resume.get("experience"))
    has_resume_experience = has_parsed_experience or bool(
        re.search(r"\b(experience|developed|built|implemented|led|managed)\b", resume_text, re.I)
    )
    job_role_terms = (set(_meaningful_tokens(job_text)) & _ROLE_TERMS) | set(_skills_in(job_text))
    if not job_role_terms:
        return 0

    candidates = _resume_candidates(resume_text, parsed_resume)
    matched = sum(1 for term in job_role_terms if _matches_term(term, resume_text, candidates))
    role_overlap = matched / len(job_role_terms)
    base = 0.35 if has_resume_experience else 0.15
    return round(EXPERIENCE_WEIGHT * min(1.0, base + (0.65 * role_overlap)))


def _score_role(job_title: str, resume_text: str, parsed_resume: dict | None) -> int:
    title_terms = [
        term
        for term in _tokens(job_title)
        if term in _ROLE_TERMS or (len(term) >= 4 and term not in _STOPWORDS)
    ]
    candidates = _resume_candidates(resume_text, parsed_resume)
    matched = sum(1 for term in title_terms if _matches_term(term, resume_text, candidates))
    return _weighted_score(ROLE_WEIGHT, matched, len(title_terms))


def _score_education(job_text: str, resume_text: str, parsed_resume: dict | None) -> int:
    job_mentions_education = any(_contains_term(job_text, term) for term in _EDUCATION_TERMS)
    if not job_mentions_education:
        return 0

    parsed_education = parsed_resume.get("education") if parsed_resume else None
    evidence_text = "\n".join([resume_text, *_parsed_strings(parsed_education)])
    levels = {
        "degree": 1,
        "associate": 1,
        "bachelor": 2,
        "bachelors": 2,
        "bsc": 2,
        "master": 3,
        "masters": 3,
        "msc": 3,
        "phd": 4,
        "doctorate": 4,
        "doctoral": 4,
    }
    required_levels = [level for term, level in levels.items() if _contains_term(job_text, term)]
    evidence_levels = [
        level for term, level in levels.items() if _contains_term(evidence_text, term)
    ]

    if required_levels and (not evidence_levels or max(evidence_levels) < max(required_levels)):
        return 0
    if _contains_term(job_text, "computer science") and not _contains_term(
        evidence_text, "computer science"
    ):
        return 0
    if required_levels:
        return EDUCATION_WEIGHT
    return EDUCATION_WEIGHT if parsed_education or _contains_term(evidence_text, "education") else 0


def _score_formatting(resume_text: str, parsed_resume: dict | None) -> int:
    return FORMATTING_WEIGHT


def score_resume_for_job(
    resume_text: str,
    parsed_resume: dict | None,
    job_title: str,
    job_description: str,
) -> DeterministicScores:
    """Compute deterministic weighted scores and keyword matches."""
    job_text = _core_job_text(job_title, job_description)
    job_keywords = extract_job_keywords(job_text)
    candidates = _resume_candidates(resume_text, parsed_resume)

    matched_keywords = [
        keyword for keyword in job_keywords if _matches_term(keyword, resume_text, candidates)
    ]
    missing_keywords = [keyword for keyword in job_keywords if keyword not in matched_keywords]

    job_skills = _skills_in(job_text)
    matched_skills = [
        skill for skill in job_skills if _matches_term(skill, resume_text, candidates)
    ]

    return DeterministicScores(
        keyword_score=_weighted_score(KEYWORD_WEIGHT, len(matched_keywords), len(job_keywords)),
        skills_score=_weighted_score(SKILLS_WEIGHT, len(matched_skills), len(job_skills)),
        experience_score=_score_experience(job_text, resume_text, parsed_resume),
        role_score=_score_role(job_title, resume_text, parsed_resume),
        education_score=_score_education(job_text, resume_text, parsed_resume),
        formatting_score=_score_formatting(resume_text, parsed_resume),
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
    )


def _fallback_recommendations(missing_keywords: list[str]) -> list[str]:
    if not missing_keywords:
        return ["Keep the resume focused on the strongest matching experience."]
    shown = ", ".join(missing_keywords[:5])
    return [f"Add truthful context for relevant missing job terms: {shown}."]


def _clean_recommendations(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _build_prompt(
    resume_text: str,
    job: Job,
    scores: DeterministicScores,
) -> str:
    return (
        "Explain this resume-to-job match as an estimate and provide concise, "
        "truthful recommendations.\n\n"
        f"Job title: {job.title}\n"
        f"Company: {job.company_name}\n"
        f"Overall estimate: {scores.overall_score}/100\n"
        "Category contributions: "
        f"keywords {scores.keyword_score}/{KEYWORD_WEIGHT}, "
        f"skills {scores.skills_score}/{SKILLS_WEIGHT}, "
        f"experience {scores.experience_score}/{EXPERIENCE_WEIGHT}, "
        f"role {scores.role_score}/{ROLE_WEIGHT}, "
        f"education {scores.education_score}/{EDUCATION_WEIGHT}, "
        f"formatting {scores.formatting_score}/{FORMATTING_WEIGHT}.\n"
        f"Matched keywords: {', '.join(scores.matched_keywords) or 'none'}\n"
        f"Missing keywords: {', '.join(scores.missing_keywords) or 'none'}\n\n"
        f"Resume text:\n{resume_text}\n\n"
        f"Job description:\n{job.description}"
    )


async def analyze_resume_for_job(
    resume: Resume,
    job: Job,
    provider: AIProvider,
    *,
    resume_text: str | None = None,
    parsed_resume: dict | None = None,
) -> JobAnalysisResult:
    """Run deterministic scoring, then request AI explanation/recommendations."""
    text = resume_text if resume_text is not None else (resume.extracted_text or "")
    parsed = resume.parsed_json if parsed_resume is None else parsed_resume
    scores = score_resume_for_job(
        text,
        parsed,
        job.title,
        job.description,
    )
    try:
        narrative = await provider.generate_json(
            _build_prompt(text, job, scores),
            ANALYSIS_NARRATIVE_SCHEMA,
            system=_SYSTEM,
        )
    except Exception:
        narrative = {}
    recommendations = _clean_recommendations(narrative.get("recommendations"))
    explanation = str(narrative.get("explanation") or "").strip()

    if not recommendations:
        recommendations = _fallback_recommendations(scores.missing_keywords)
    if not explanation:
        explanation = (
            f"Estimated match is {scores.overall_score}/100 based on deterministic "
            "keyword, skill, experience, role, education, and formatting checks."
        )

    return JobAnalysisResult(
        overall_score=scores.overall_score,
        keyword_score=scores.keyword_score,
        skills_score=scores.skills_score,
        experience_score=scores.experience_score,
        role_score=scores.role_score,
        education_score=scores.education_score,
        formatting_score=scores.formatting_score,
        matched_keywords=scores.matched_keywords,
        missing_keywords=scores.missing_keywords,
        recommendations=recommendations,
        explanation=explanation,
    )


def provider_metadata(provider: AIProvider) -> tuple[str, str]:
    """Return stable provider/model metadata for persisted analysis rows."""
    settings = get_settings()
    provider_name = settings.ai_provider.lower()
    if provider_name == "mock":
        return "mock", "mock"
    return provider_name, str(getattr(provider, "_model", settings.ollama_model))
