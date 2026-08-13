"""Shared FastAPI dependencies for the API layer.

``get_current_user`` is the authentication foundation other features build on:
it reads the session cookie, decodes the JWT, and loads the user from the DB,
raising 401 if anything is missing or invalid.
"""

import uuid
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError
from sqlmodel import Session

from app.core import security
from app.core.config import get_settings
from app.core.database import get_session
from app.models import User

_settings = get_settings()


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"detail": "Not authenticated", "code": "not_authenticated"},
    )


def get_current_user(
    session: Annotated[Session, Depends(get_session)],
    jg_session: Annotated[
        str | None, Cookie(alias=_settings.session_cookie_name)
    ] = None,
) -> User:
    """Resolve the authenticated user from the session cookie, or 401."""
    if not jg_session:
        raise _unauthorized()
    try:
        subject = security.decode_access_token(jg_session)
        user_id = uuid.UUID(subject)
    except (JWTError, ValueError):
        raise _unauthorized() from None

    user = session.get(User, user_id)
    if user is None:
        raise _unauthorized()
    return user


def get_mfa_pending_user(
    session: Annotated[Session, Depends(get_session)],
    jg_mfa: Annotated[
        str | None, Cookie(alias=_settings.mfa_cookie_name)
    ] = None,
) -> User:
    """Resolve the user mid-MFA from the short-lived mfa_pending cookie, or 401.

    Used only by the second-factor challenge endpoint; a full session cookie is
    deliberately NOT accepted here, and vice versa.
    """
    if not jg_mfa:
        raise _unauthorized()
    try:
        subject = security.decode_mfa_pending_token(jg_mfa)
        user_id = uuid.UUID(subject)
    except (JWTError, ValueError):
        raise _unauthorized() from None

    user = session.get(User, user_id)
    if user is None:
        raise _unauthorized()
    return user
