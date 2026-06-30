"""Rate limiting for brute-forceable auth endpoints (slowapi).

The limits are returned by callables so they're read from settings on every
request — this lets the limit be tuned at runtime and overridden in tests, and
honours ``rate_limit_enabled`` (an effectively-unlimited bucket when disabled).

The limiter is keyed by client IP. Exceeding a limit yields a 429 in the app's
standard ``{detail, code}`` error envelope.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings

# Effectively no limit; used when rate limiting is turned off.
_UNLIMITED = "1000000/minute"


def auth_limit() -> str:
    """Per-IP limit for password login + Google callback."""
    s = get_settings()
    return s.auth_rate_limit if s.rate_limit_enabled else _UNLIMITED


def mfa_limit() -> str:
    """Tighter per-IP limit for the MFA code endpoints (small search space)."""
    s = get_settings()
    return s.mfa_rate_limit if s.rate_limit_enabled else _UNLIMITED


limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Emit the standard error envelope on a 429."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many requests; slow down", "code": "rate_limited"},
    )
