"""Resume section parsing (design.md §8).

Given extracted plain text, ask the AI provider for a structured ``ParsedResume``
(summary, skills, experience, education, projects, certifications). The schema is
passed to ``generate_json`` so providers that support structured outputs (Ollama
``format``) constrain the model; MockProvider returns conforming canned data.

The shape mirrors the frontend contract in ``frontend/lib/types.ts``.
"""

from app.services.ai_provider import AIProvider

# JSON Schema for the structured parse. Kept flat and explicit so Ollama's
# structured-output ``format`` argument can enforce it.
PARSED_RESUME_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "skills": {"type": "array", "items": {"type": "string"}},
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "role": {"type": "string"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "highlights": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["company", "role", "highlights"],
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "institution": {"type": "string"},
                    "credential": {"type": "string"},
                    "year": {"type": "string"},
                },
                "required": ["institution", "credential"],
            },
        },
        "projects": {"type": "array", "items": {"type": "string"}},
        "certifications": {"type": "array", "items": {"type": "string"}},
    },
    # No top-level ``required``: the system prompt tells the model to omit any
    # section it cannot find, so the schema must permit a partial object. The
    # API layer defaults missing sections (see schemas.resume.ParsedResume).
}

_SYSTEM = (
    "You extract structured data from resume text. Use ONLY information present "
    "in the text — never invent companies, dates, or skills. Omit fields you "
    "cannot find. Return JSON matching the provided schema."
)


def _build_prompt(text: str) -> str:
    return (
        "Extract the following sections from this resume as JSON: a short summary, "
        "a flat list of skills, work experience (company, role, start, end, "
        "highlights), education (institution, credential, year), project names, "
        "and certifications.\n\nResume text:\n"
        f"{text}"
    )


async def parse_resume(text: str, provider: AIProvider) -> dict:
    """Parse ``text`` into structured resume sections via ``provider``."""
    return await provider.generate_json(
        _build_prompt(text), PARSED_RESUME_SCHEMA, system=_SYSTEM
    )
