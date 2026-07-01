"""Authentication endpoints: register, login, logout, me.

Session is a signed JWT carried in an HTTP-only, Secure, SameSite=Lax cookie.
Same-origin in production (behind Caddy), so no CORS / cross-site concerns.
Emails are stored and looked up lowercased.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session, select

from app.api.deps import get_current_user, get_mfa_pending_user
from app.core import allowlist, google_oauth, security, totp
from app.core.config import get_settings
from app.core.database import get_session
from app.core.ratelimit import auth_limit, limiter, mfa_limit
from app.models import InviteToken, User
from app.schemas.auth import (
    LoginRequest,
    MfaCodeRequest,
    MfaEnrollResponse,
    MfaRequiredResponse,
    PrimaryAuthResponse,
    RegisterRequest,
    SessionUserResponse,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": message, "code": code})


def _cookie_secure() -> bool:
    return settings.app_env.lower() != "development"


def _set_session_cookie(response: Response, user: User) -> None:
    token = security.create_access_token(str(user.id))
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def _set_mfa_pending_cookie(response: Response, user: User) -> None:
    """Issue the short-lived intermediate token (NOT a full session)."""
    token = security.create_mfa_pending_token(str(user.id))
    response.set_cookie(
        key=settings.mfa_cookie_name,
        value=token,
        max_age=settings.mfa_pending_token_expire_minutes * 60,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def _clear_mfa_pending_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.mfa_cookie_name,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def _complete_primary_auth(response: Response, user: User) -> PrimaryAuthResponse:
    """Apply the MFA gate after a successful primary auth (password or Google).

    - TOTP enabled  -> issue only the mfa_pending token; require a challenge.
      No user identity is returned until the second factor is verified.
    - TOTP not enabled -> set the full session and flag that enrollment is due.
    """
    if user.totp_enabled:
        _set_mfa_pending_cookie(response, user)
        return MfaRequiredResponse(mfa_required=True)
    _set_session_cookie(response, user)
    result = SessionUserResponse.model_validate(user)
    result.mfa_enrollment_required = True
    return result


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> User:
    # Lock the invite row so two concurrent registrations can't both observe
    # used_by is None and succeed against the same token.
    invite = session.exec(
        select(InviteToken)
        .where(InviteToken.token == payload.invite_token)
        .with_for_update()
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


@router.post("/login", response_model=PrimaryAuthResponse)
@limiter.limit(auth_limit)
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> PrimaryAuthResponse:
    email = payload.email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not security.verify_password(payload.password, user.password_hash):
        raise _error(
            status.HTTP_401_UNAUTHORIZED, "Invalid email or password", "invalid_credentials"
        )

    # Primary auth succeeded; apply the MFA gate (session vs. mfa_pending).
    return _complete_primary_auth(response, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserPublic)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


# --------------------------------------------------------------- Google OAuth


@router.get("/google/login")
async def google_login(request: Request):
    """Redirect the browser to Google's consent screen."""
    if not google_oauth.is_configured():
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Google sign-in is not configured",
            "google_not_configured",
        )
    return await google_oauth.build_authorization_redirect(request)


@router.get("/google/callback", response_model=PrimaryAuthResponse)
@limiter.limit(auth_limit)
async def google_callback(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> PrimaryAuthResponse:
    """Handle Google's callback: verify identity, allowlist, link/create user, MFA gate."""
    if not google_oauth.is_configured():
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Google sign-in is not configured",
            "google_not_configured",
        )
    try:
        raw_email, sub = await google_oauth.fetch_verified_identity(request)
    except Exception:
        raise _error(
            status.HTTP_400_BAD_REQUEST, "Google sign-in failed", "google_auth_failed"
        ) from None

    email = raw_email.strip().lower()
    if not allowlist.is_allowed(email):
        raise _error(status.HTTP_403_FORBIDDEN, "This email is not allowed", "not_allowlisted")

    # Look up by google_sub first, then link an existing email account, else create.
    user = session.exec(select(User).where(User.google_sub == sub)).first()
    if user is None:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            user = User(
                email=email,
                # OAuth-only account: no usable password (login path rejects it).
                password_hash="!",
                display_name=email.split("@", 1)[0],
                google_sub=sub,
            )
            session.add(user)
        elif user.google_sub is None:
            # First Google sign-in for an existing email/password account: link it.
            user.google_sub = sub
            session.add(user)
        else:
            # The email maps to an account already linked to a DIFFERENT Google
            # sub. Never silently re-link - that's an account-takeover hazard.
            raise _error(
                status.HTTP_409_CONFLICT,
                "This account is already linked to a different Google identity",
                "google_sub_conflict",
            )
        session.commit()
        session.refresh(user)

    return _complete_primary_auth(response, user)


# ----------------------------------------------------------------- TOTP / MFA


@router.get("/mfa/enroll", response_model=MfaEnrollResponse)
def mfa_enroll(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> MfaEnrollResponse:
    """Generate (or reissue) a TOTP secret and return its provisioning URI + QR.

    Enrollment is only allowed while TOTP is not yet enabled.
    """
    if current_user.totp_enabled:
        raise _error(
            status.HTTP_409_CONFLICT, "MFA is already enabled", "mfa_already_enabled"
        )

    secret = totp.generate_secret()
    current_user.totp_secret = secret
    session.add(current_user)
    session.commit()

    uri = totp.provisioning_uri(
        secret, account_name=current_user.email, issuer=settings.totp_issuer
    )
    return MfaEnrollResponse(
        secret=secret, provisioning_uri=uri, qr_data_uri=totp.qr_data_uri(uri)
    )


@router.post("/mfa/verify", response_model=UserPublic)
@limiter.limit(mfa_limit)
def mfa_verify(
    request: Request,
    payload: MfaCodeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    """Confirm enrollment: validate the code and flip ``totp_enabled`` to True."""
    if not current_user.totp_secret:
        raise _error(
            status.HTTP_400_BAD_REQUEST, "Start enrollment first", "mfa_not_enrolled"
        )
    step = totp.match_timestep(
        current_user.totp_secret, payload.code, last_timestep=current_user.last_totp_timestep
    )
    if step is None:
        raise _error(status.HTTP_400_BAD_REQUEST, "Invalid code", "invalid_code")

    current_user.totp_enabled = True
    current_user.last_totp_timestep = step  # consume the step (replay protection)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.post("/mfa/challenge", response_model=SessionUserResponse)
@limiter.limit(mfa_limit)
def mfa_challenge(
    request: Request,
    payload: MfaCodeRequest,
    response: Response,
    pending_user: Annotated[User, Depends(get_mfa_pending_user)],
    session: Annotated[Session, Depends(get_session)],
) -> SessionUserResponse:
    """Second-factor gate: verify the code, then issue the full session cookie."""
    step = totp.match_timestep(
        pending_user.totp_secret, payload.code, last_timestep=pending_user.last_totp_timestep
    )
    if step is None:
        raise _error(status.HTTP_400_BAD_REQUEST, "Invalid code", "invalid_code")

    pending_user.last_totp_timestep = step  # consume the step (replay protection)
    session.add(pending_user)
    session.commit()
    session.refresh(pending_user)

    _set_session_cookie(response, pending_user)
    _clear_mfa_pending_cookie(response)
    return SessionUserResponse.model_validate(pending_user)
