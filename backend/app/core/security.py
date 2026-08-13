"""Password hashing (argon2id) and JWT session tokens (python-jose).

This module is the foundation other features depend on; keep it small and
importable. It must never log secrets, passwords, or token contents.
"""

from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import get_settings

# argon2id is the default type for argon2-cffi's PasswordHasher.
_ph = PasswordHasher()

# Re-exported for callers that decode tokens directly (e.g. tests, deps).
JWT_ALGORITHM = get_settings().jwt_algorithm


def hash_password(password: str) -> str:
    """Return an argon2id hash (includes a random salt + parameters)."""
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its argon2id hash. Never raises."""
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# Token "type" claim values. A full session token carries no ``typ`` (kept
# backwards compatible with previously issued cookies); the intermediate
# MFA-pending token carries ``typ=mfa_pending`` so it can never be mistaken for
# — or used as — a real session.
_MFA_PENDING_TYP = "mfa_pending"


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT whose ``sub`` claim is the user id."""
    settings = get_settings()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expire = datetime.now(UTC) + expires_delta
    claims = {"sub": subject, "exp": expire}
    return jwt.encode(claims, settings.app_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Decode a session JWT and return its subject.

    Raises ``JWTError`` if invalid/expired, if the subject is missing, or if the
    token is actually an MFA-pending token (which must not unlock a session).
    """
    settings = get_settings()
    claims = jwt.decode(token, settings.app_secret_key, algorithms=[settings.jwt_algorithm])
    if claims.get("typ") == _MFA_PENDING_TYP:
        raise JWTError("MFA-pending token cannot be used as a session token")
    subject = claims.get("sub")
    if subject is None:
        raise JWTError("Token is missing the subject claim")
    return str(subject)


def create_mfa_pending_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a short-lived token marking a primary-auth'd, MFA-not-yet-passed user.

    It carries ``typ=mfa_pending`` and is only accepted by
    ``decode_mfa_pending_token`` — never by ``decode_access_token``.
    """
    settings = get_settings()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.mfa_pending_token_expire_minutes)
    expire = datetime.now(UTC) + expires_delta
    claims = {"sub": subject, "exp": expire, "typ": _MFA_PENDING_TYP}
    return jwt.encode(claims, settings.app_secret_key, algorithm=settings.jwt_algorithm)


def decode_mfa_pending_token(token: str) -> str:
    """Decode an MFA-pending token and return its subject.

    Raises ``JWTError`` if invalid/expired, missing a subject, or not an
    MFA-pending token (e.g. a real session token is presented).
    """
    settings = get_settings()
    claims = jwt.decode(token, settings.app_secret_key, algorithms=[settings.jwt_algorithm])
    if claims.get("typ") != _MFA_PENDING_TYP:
        raise JWTError("Not an MFA-pending token")
    subject = claims.get("sub")
    if subject is None:
        raise JWTError("Token is missing the subject claim")
    return str(subject)
