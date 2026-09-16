"""Tests for AI section parsing of resume text (design.md §8)."""

from app.services.ai_provider import MockProvider
from app.services.resume_parser import PARSED_RESUME_SCHEMA, parse_resume


class HallucinatingProvider(MockProvider):
    async def generate_json(self, prompt, schema, *, system=None):
        return {
            "summary": "Led Google teams and increased revenue by 300%.",
            "skills": ["Python", "Kubernetes"],
            "experience": [
                {"company": "Google", "role": "Director", "highlights": ["Grew revenue 300%"]}
            ],
            "education": [],
            "projects": [],
            "certifications": ["AWS Certified"],
        }


async def test_parse_resume_returns_all_sections():
    parsed = await parse_resume("Jane Doe, Python engineer", MockProvider())
    for key in (
        "summary",
        "skills",
        "experience",
        "education",
        "projects",
        "certifications",
    ):
        assert key in parsed
    assert isinstance(parsed["skills"], list)
    assert isinstance(parsed["experience"], list)


def test_schema_declares_expected_top_level_keys():
    props = PARSED_RESUME_SCHEMA["properties"]
    assert set(props) == {
        "summary",
        "skills",
        "experience",
        "education",
        "projects",
        "certifications",
    }


async def test_parse_resume_drops_facts_missing_from_source_text():
    parsed = await parse_resume(
        "Jane Doe\nPython engineer who built internal APIs.", HallucinatingProvider()
    )

    assert parsed["skills"] == ["Python"]
    assert parsed["experience"] == []
    assert parsed["certifications"] == []
    assert "Google" not in parsed["summary"]
