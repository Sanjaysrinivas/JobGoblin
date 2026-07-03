"""Optional LLM observability hooks.

This module never imports logfire at module import time, so environments that
do not install it keep working.
"""

import hashlib
import importlib
import json
import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from time import perf_counter
from typing import Any

from app.core.config import get_settings

_lock = threading.Lock()
_configured = False
logger = logging.getLogger(__name__)


def _logfire() -> Any | None:
    if not get_settings().observability_enabled:
        return None
    try:
        logfire = importlib.import_module("logfire")
    except ImportError:
        return None

    global _configured
    if not _configured:
        with _lock:
            if not _configured:
                try:
                    logfire.configure()
                except Exception as exc:
                    logger.warning("Failed to configure logfire: %s", exc)
                    _configured = True
                    return None
                _configured = True
    return logfire


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _hash_schema(schema: dict[str, Any] | None) -> str | None:
    if not schema:
        return None
    encoded = json.dumps(schema, sort_keys=True, separators=(",", ":"), default=str)
    return _hash_text(encoded)


def llm_span_attributes(
    *,
    provider: str,
    model: str,
    operation: str,
    prompt: str,
    system: str,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        "llm.provider": provider,
        "llm.model": model,
        "llm.operation": operation,
        "llm.prompt_hash": _hash_text(prompt),
        "llm.prompt_length": len(prompt),
        "llm.system_length": len(system),
    }
    if schema:
        attrs["llm.schema_hash"] = _hash_schema(schema)
        if schema_name := schema.get("title") or schema.get("$id"):
            attrs["llm.schema_name"] = str(schema_name)
    return attrs


def _set_attribute(span: Any, name: str, value: Any) -> None:
    try:
        span.set_attribute(name, value)
    except Exception:
        pass


@contextmanager
def observe_llm_call(
    *,
    provider: str,
    model: str,
    operation: str,
    prompt: str,
    system: str,
    schema: dict[str, Any] | None = None,
) -> Iterator[None]:
    """Create a sanitized span around an LLM call when observability is enabled."""
    logfire = _logfire()
    if logfire is None:
        with nullcontext():
            yield
        return

    attrs = llm_span_attributes(
        provider=provider,
        model=model,
        operation=operation,
        prompt=prompt,
        system=system,
        schema=schema,
    )
    started = perf_counter()
    with logfire.span("llm.generate", **attrs) as span:
        try:
            yield
        except Exception as exc:
            _set_attribute(span, "llm.success", False)
            _set_attribute(span, "llm.error", type(exc).__name__)
            raise
        else:
            _set_attribute(span, "llm.success", True)
        finally:
            latency_ms = round((perf_counter() - started) * 1000, 2)
            _set_attribute(span, "llm.latency_ms", latency_ms)


def record_llm_fallback(
    *,
    provider: str,
    model: str,
    operation: str,
    reason: str,
) -> None:
    """Record sanitized fallback metadata without prompt or user text."""
    attrs = {
        "llm.provider": provider,
        "llm.model": model,
        "llm.operation": operation,
        "llm.fallback": True,
        "llm.fallback_reason": reason,
    }
    logger.info("LLM fallback used", extra={"llm": attrs})
    logfire = _logfire()
    if logfire is None:
        return
    try:
        with logfire.span("llm.fallback", **attrs):
            pass
    except Exception:
        logger.debug("Failed to record LLM fallback span", exc_info=True)
