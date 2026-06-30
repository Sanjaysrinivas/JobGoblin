"""Authentication endpoints: register, login, logout, me.

Session is a signed JWT carried in an HTTP-only, Secure, SameSite=Lax cookie.
Same-origin in production (behind Caddy), so no CORS / cross-site concerns.
Emails are stored and looked up lowercased.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core import security
from app.core.config import get_settings
from app.core.database import get_session
from app.models import InviteToken, User
from app.schemas.auth import LoginRequest, RegisterRequest, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _set_session_cookie(response: Response, user: User) -> None:
    token = security.create_access_token(str(user.id))
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> User:
    invite = session.exec(
        select(InviteToken).where(InviteToken.token == payload.invite_token)
    ).first()
    if (
        invite is None
        or invite.used_by is not None
        or invite.expires_at <= datetime.now(UTC)
    ):
        raise _error(status.HTTP_400_BAD_REQUEST, "Invalid or expired invite", "invalid_invite")

    email = payload.email.strip().lower()
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing is not None:
        raise _error(status.HTTP_409_CONFLICT, "Email already registered", "email_taken")

    user = User(
        email=email,
        password_hash=security.hash_password(payload.password),
        display_name=email.split("@", 1)[0],
    )
    session.add(user)
    session.flush()  # assign user.id before marking the invite

    invite.used_by = user.id
    session.add(invite)
    session.commit()
    session.refresh(user)

    _set_session_cookie(response, user)
    return user


@router.post("/login", response_model=UserPublic)
def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> User:
    email = payload.email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not security.verify_password(payload.password, user.password_hash):
        raise _error(
            status.HTTP_401_UNAUTHORIZED, "Invalid email or password", "invalid_credentials"
        )

    _set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserPublic)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user
