"""Email allowlist gate for the private tool.

Access via Google sign-in is restricted to a configured set of emails. An empty
allowlist admits nobody (fail-closed) — the operator must explicitly list the
addresses permitted to sign up/in with Google.
"""

from app.core.config import Settings, get_settings


def is_allowed(email: str, settings: Settings | None = None) -> bool:
    """Return True only if ``email`` is in the configured allowlist (case-insensitive)."""
    settings = settings or get_settings()
    allowed = settings.allowed_email_set
    if not allowed:
        return False
    return email.strip().lower() in allowed
