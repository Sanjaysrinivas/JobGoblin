"""Tests for AI section parsing of resume text (design.md §8)."""

from app.services.ai_provider import MockProvider
from app.services.resume_parser import PARSED_RESUME_SCHEMA, parse_resume


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
