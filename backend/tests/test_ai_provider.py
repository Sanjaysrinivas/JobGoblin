"""Tests for the AI provider abstraction (design.md §6).

These exercise MockProvider only; no Ollama is required.
"""

from app.services.ai_provider import MockProvider, OllamaProvider, get_ai_provider

PARSED_RESUME_SCHEMA = {
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
                    "highlights": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "education": {"type": "array", "items": {"type": "object"}},
        "projects": {"type": "array", "items": {"type": "string"}},
        "certifications": {"type": "array", "items": {"type": "string"}},
    },
}


async def test_mock_generate_text_is_deterministic():
    provider = MockProvider()
    a = await provider.generate_text("hello")
    b = await provider.generate_text("hello")
    assert isinstance(a, str) and a
    assert a == b


async def test_mock_generate_json_conforms_to_schema():
    provider = MockProvider()
    result = await provider.generate_json("parse this", PARSED_RESUME_SCHEMA)
    assert isinstance(result, dict)
    # Every declared property is present with the right Python type.
    assert isinstance(result["summary"], str)
    assert isinstance(result["skills"], list)
    assert isinstance(result["experience"], list)
    assert isinstance(result["projects"], list)
    # Nested object items follow their own sub-schema.
    if result["experience"]:
        assert isinstance(result["experience"][0]["company"], str)
        assert isinstance(result["experience"][0]["highlights"], list)


async def test_mock_generate_json_is_deterministic():
    provider = MockProvider()
    a = await provider.generate_json("x", PARSED_RESUME_SCHEMA)
    b = await provider.generate_json("x", PARSED_RESUME_SCHEMA)
    assert a == b


def test_get_ai_provider_mock(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AI_PROVIDER", "mock")
    assert isinstance(get_ai_provider(), MockProvider)
    get_settings.cache_clear()


def test_get_ai_provider_ollama(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    assert isinstance(get_ai_provider(), OllamaProvider)
    get_settings.cache_clear()
