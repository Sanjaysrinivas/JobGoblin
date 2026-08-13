import json
import sys
from types import ModuleType

from app.core import observability
from app.core.config import get_settings
from app.core.observability import llm_span_attributes, record_llm_fallback
from app.services.ai_provider import MockProvider


class _FakeSpan:
    def __init__(self, record):
        self.record = record

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def set_attribute(self, name, value):
        self.record["attrs"][name] = value


class _FakeLogfire(ModuleType):
    def __init__(self):
        super().__init__("logfire")
        self.configured = 0
        self.spans = []

    def configure(self):
        self.configured += 1

    def span(self, name, **attrs):
        record = {"name": name, "attrs": dict(attrs)}
        self.spans.append(record)
        return _FakeSpan(record)


def test_llm_span_attributes_are_metadata_only():
    attrs = llm_span_attributes(
        provider="ollama",
        model="qwen",
        operation="generate_json",
        prompt="raw resume prompt secret",
        system="raw system secret",
        schema={
            "title": "ResumeParseResult",
            "type": "object",
            "properties": {"summary": {"type": "string"}},
        },
    )

    serialized = json.dumps(attrs)
    assert attrs["llm.prompt_length"] == len("raw resume prompt secret")
    assert attrs["llm.system_length"] == len("raw system secret")
    assert len(attrs["llm.prompt_hash"]) == 16
    assert len(attrs["llm.schema_hash"]) == 16
    assert attrs["llm.schema_name"] == "ResumeParseResult"
    assert "raw resume prompt secret" not in serialized
    assert "raw system secret" not in serialized
    assert "summary" not in serialized


async def test_mock_provider_observability_uses_sanitized_span(monkeypatch):
    fake_logfire = _FakeLogfire()
    monkeypatch.setitem(sys.modules, "logfire", fake_logfire)
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "true")
    monkeypatch.setattr(observability, "_configured", False)
    get_settings.cache_clear()

    try:
        result = await MockProvider().generate_text(
            "raw profile prompt secret",
            system="raw system secret",
        )
    finally:
        get_settings.cache_clear()
        observability._configured = False

    assert result == "This is a mock AI response."
    assert fake_logfire.configured == 1
    assert len(fake_logfire.spans) == 1

    span = fake_logfire.spans[0]
    attrs = span["attrs"]
    serialized = json.dumps(span)
    assert span["name"] == "llm.generate"
    assert attrs["llm.provider"] == "mock"
    assert attrs["llm.operation"] == "generate_text"
    assert "llm.latency_ms" in attrs
    assert "raw profile prompt secret" not in serialized
    assert "raw system secret" not in serialized


def test_record_llm_fallback_is_metadata_only(monkeypatch):
    fake_logfire = _FakeLogfire()
    monkeypatch.setitem(sys.modules, "logfire", fake_logfire)
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "true")
    monkeypatch.setattr(observability, "_configured", False)
    get_settings.cache_clear()

    try:
        record_llm_fallback(
            provider="ollama",
            model="qwen",
            operation="discovery.rank_json",
            reason="timeout",
        )
    finally:
        get_settings.cache_clear()
        observability._configured = False

    assert fake_logfire.spans[-1]["name"] == "llm.fallback"
    attrs = fake_logfire.spans[-1]["attrs"]
    assert attrs == {
        "llm.provider": "ollama",
        "llm.model": "qwen",
        "llm.operation": "discovery.rank_json",
        "llm.fallback": True,
        "llm.fallback_reason": "timeout",
    }
