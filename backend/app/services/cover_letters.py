"""Cover-letter draft generation.

The service creates editable local drafts only. It does not submit
applications, send email, or perform any external action.
"""

from app.models import Job, Resume
from app.models.enums import CoverLetterTone
from app.services.ai_provider import AIProvider

_SYSTEM = (
    "You write careful cover-letter drafts for job seekers. Never fabricate "
    "skills, employers, credentials, dates, education, projects, or experience. "
    "Use only facts present in the provided resume and job text. The output is "
    "an editable draft only; do not claim the application was submitted or any "
    "message was sent. Keep the language ATS-friendly and plain."
)


def _tone_instruction(tone: CoverLetterTone) -> str:
    return {
        CoverLetterTone.professional: "Use a polished professional tone.",
        CoverLetterTone.friendly: "Use a warm, friendly tone while staying concise.",
        CoverLetterTone.concise: "Use a concise tone and keep the draft brief.",
        CoverLetterTone.enthusiastic: "Use an enthusiastic tone without exaggerating facts.",
    }[tone]


def _resume_context(resume: Resume) -> str:
    parts = [resume.extracted_text or ""]
    if resume.parsed_json:
        parts.append(str(resume.parsed_json))
    return "\n\n".join(part for part in parts if part.strip()).strip()


async def generate_cover_letter(
    resume: Resume,
    job: Job,
    tone: CoverLetterTone,
    provider: AIProvider,
    *,
    resume_text: str | None = None,
    parsed_resume: dict | None = None,
) -> str:
    """Generate a grounded, editable draft for the owned resume/job pair."""
    context = (
        _resume_context(resume)
        if resume_text is None and parsed_resume is None
        else "\n\n".join(
            part
            for part in (resume_text or "", str(parsed_resume) if parsed_resume else "")
            if part.strip()
        ).strip()
    )
    prompt = (
        "Create a cover-letter draft grounded only in the supplied resume and "
        "job posting. If a qualification is not supported by the resume, omit "
        "it or phrase it conservatively. Do not invent achievements or facts.\n\n"
        f"Tone: {_tone_instruction(tone)}\n"
        f"Company: {job.company_name}\n"
        f"Job title: {job.title}\n"
        f"Job description:\n{job.description}\n\n"
        f"Resume text and parsed context:\n{context}"
    )
    return (await provider.generate_text(prompt, system=_SYSTEM)).strip()