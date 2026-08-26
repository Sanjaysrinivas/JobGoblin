"""Cover-letter draft generation.

The service creates editable local drafts only. It does not submit
applications, send email, or perform any external action.
"""

from app.models import Job, Resume
from app.models.enums import CoverLetterTone
from app.services.ai_provider import AIProvider
from app.services.grounding import normalized_phrase, source_excerpts

_SYSTEM = (
    "Select verbatim evidence from a resume for a cover-letter draft. Return "
    "only exact excerpts present in the supplied resume. Never rewrite or invent facts."
)

_EVIDENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "evidence_quotes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["evidence_quotes"],
}


async def generate_cover_letter(
    resume: Resume,
    job: Job,
    tone: CoverLetterTone,
    provider: AIProvider,
    *,
    resume_text: str | None = None,
    parsed_resume: dict | None = None,
) -> str:
    """Compose an editable draft from source-validated resume excerpts."""
    text = resume_text if resume_text is not None else (resume.extracted_text or "")
    candidates = source_excerpts(text)
    prompt = (
        "Choose up to three exact, verbatim resume excerpts that are most relevant "
        "to this job. Do not paraphrase.\n\n"
        f"Company: {job.company_name}\n"
        f"Job title: {job.title}\n"
        f"Job description:\n{job.description}\n\n"
        f"Resume text:\n{text}"
    )
    try:
        payload = await provider.generate_json(prompt, _EVIDENCE_SCHEMA, system=_SYSTEM)
    except Exception:
        payload = {}
    requested = payload.get("evidence_quotes", []) if isinstance(payload, dict) else []
    requested_keys = {normalized_phrase(item) for item in requested if isinstance(item, str)}
    evidence = [item for item in candidates if normalized_phrase(item) in requested_keys][:3]
    if not evidence:
        evidence = candidates[:2]

    greeting = "Hello Hiring Team," if tone == CoverLetterTone.friendly else "Dear Hiring Team,"
    introduction = {
        CoverLetterTone.professional: (
            f"I am writing to apply for the {job.title} role at {job.company_name}."
        ),
        CoverLetterTone.friendly: (
            f"I would be glad to be considered for the {job.title} role at {job.company_name}."
        ),
        CoverLetterTone.concise: f"I am applying for {job.title} at {job.company_name}.",
        CoverLetterTone.enthusiastic: (
            f"I am excited to apply for the {job.title} role at {job.company_name}."
        ),
    }[tone]
    paragraphs = [greeting, introduction]
    if evidence:
        paragraphs.append(
            "Relevant experience from my resume includes:\n"
            + "\n".join(f"- {item}" for item in evidence)
        )
    if tone != CoverLetterTone.concise:
        paragraphs.append(
            "I would welcome the opportunity to discuss how this background "
            "could support the role."
        )
    closing = (
        "Best,\n[Your name]"
        if tone == CoverLetterTone.friendly
        else "Sincerely,\n[Your name]"
    )
    paragraphs.append(closing)
    return "\n\n".join(paragraphs)
