"""AI provider abstraction (design.md Ãƒâ€šÃ‚Â§6).

A thin, swappable layer over a text/JSON generation engine. ``OllamaProvider``
talks to a local Ollama server; ``MockProvider`` returns deterministic, schema-
conforming data so tests and offline dev never touch a model.
"""

import json
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import get_settings
from app.core.observability import observe_llm_call

# System prompt guardrails applied to every call (design.md Ãƒâ€šÃ‚Â§6): no fabrication,
# explain reasoning, keep any resume output ATS-plain.
DEFAULT_SYSTEM = (
    "You are a careful resume and job-search assistant. Never fabricate facts. "
    "Only use information present in the provided text. Keep output plain and "
    "ATS-friendly. Respond exactly in the requested format."
)


class AIProvider(ABC):
    """Generates free text or schema-constrained JSON from a prompt."""

    @abstractmethod
    async def generate_text(self, prompt: str, *, system: str | None = None) -> str: ...

    @abstractmethod
    async def generate_json(
        self, prompt: str, schema: dict, *, system: str | None = None
    ) -> dict: ...


class OllamaProvider(AIProvider):
    """Backed by a local Ollama server via the async client.

    ``generate_json`` passes the JSON schema straight to Ollama's ``format``
    argument (structured outputs) with ``temperature: 0`` for determinism, then
    parses the model's message content.
    """

    def __init__(self) -> None:
        # Imported lazily so the package need not be importable in environments
        # that only ever use MockProvider.
        from ollama import AsyncClient

        settings = get_settings()
        self._client = AsyncClient(host=settings.ollama_base_url)
        self._model = settings.ollama_model

    async def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        system_text = system or DEFAULT_SYSTEM
        messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": prompt},
        ]
        with observe_llm_call(
            provider="ollama",
                model=self._model,
                operation="generate_text",
                prompt=prompt,
                system=system_text,
        ):
            response = await self._client.chat(
                model=self._model,
                messages=messages,
                options={"temperature": 0},
            )
        return response.message.content or ""

    async def generate_json(
        self, prompt: str, schema: dict, *, system: str | None = None
    ) -> dict:
        system_text = system or DEFAULT_SYSTEM
        messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": prompt},
        ]
        with observe_llm_call(
            provider="ollama",
                model=self._model,
                operation="generate_json",
                prompt=prompt,
                system=system_text,
                schema=schema,
        ):
            response = await self._client.chat(
                model=self._model,
                messages=messages,
                format=schema,
                options={"temperature": 0},
            )
        content = response.message.content or "{}"
        return json.loads(content)


def _sample_for_schema(schema: dict[str, Any]) -> Any:
    """Build a deterministic value conforming to a (subset of) JSON Schema.

    Supports the constructs the app uses: object/array/string/integer/number/
    boolean. Unknown types fall back to ``None``.
    """
    schema_type = schema.get("type")

    if schema_type == "object":
        props: dict[str, Any] = schema.get("properties", {})
        return {name: _sample_for_schema(sub) for name, sub in props.items()}

    if schema_type == "array":
        items = schema.get("items", {"type": "string"})
        # One representative element keeps output deterministic and non-empty.
        return [_sample_for_schema(items)]

    if schema_type == "string":
        return "sample"
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0.0
    if schema_type == "boolean":
        return False
    return None


class MockProvider(AIProvider):
    """Deterministic, dependency-free provider for tests and offline dev."""

    async def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        system_text = system or DEFAULT_SYSTEM
        with observe_llm_call(
            provider="mock",
                model="mock",
                operation="generate_text",
                prompt=prompt,
                system=system_text,
        ):
            return "This is a mock AI response."

    async def generate_json(
        self, prompt: str, schema: dict, *, system: str | None = None
    ) -> dict:
        system_text = system or DEFAULT_SYSTEM
        with observe_llm_call(
            provider="mock",
                model="mock",
                operation="generate_json",
                prompt=prompt,
                system=system_text,
                schema=schema,
        ):
            result = _sample_for_schema(schema)
            return result if isinstance(result, dict) else {}


def get_ai_provider() -> AIProvider:
    """Return the configured provider, keyed off ``settings.ai_provider``."""
    provider = get_settings().ai_provider.lower()
    if provider == "mock":
        return MockProvider()
    return OllamaProvider()
