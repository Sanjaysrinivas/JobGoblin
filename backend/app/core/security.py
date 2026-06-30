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


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT whose ``sub`` claim is the user id."""
    settings = get_settings()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expire = datetime.now(UTC) + expires_delta
    claims = {"sub": subject, "exp": expire}
    return jwt.encode(claims, settings.app_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Decode a JWT and return its subject. Raises ``JWTError`` if invalid/expired."""
    settings = get_settings()
    claims = jwt.decode(token, settings.app_secret_key, algorithms=[settings.jwt_algorithm])
    subject = claims.get("sub")
    if subject is None:
        raise JWTError("Token is missing the subject claim")
    return str(subject)
