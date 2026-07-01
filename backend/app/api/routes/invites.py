"""Admin invite-token management for private signup."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import InviteToken, User
from app.schemas.auth import InviteCreateRequest, InviteTokenPublic

router = APIRouter(prefix="/invites", tags=["invites"])


def _admin_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"detail": "Admin required", "code": "admin_required"},
    )


def _ensure_admin(user: User) -> None:
    if not user.is_admin:
        raise _admin_required()


def _new_unique_token(session: Session) -> str:
    for _ in range(5):
        token = secrets.token_urlsafe(32)
        existing = session.exec(select(InviteToken).where(InviteToken.token == token)).first()
        if existing is None:
            return token
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"detail": "Could not create invite token", "code": "invite_create_failed"},
    )


@router.get("", response_model=list[InviteTokenPublic])
def list_invites(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[InviteToken]:
    _ensure_admin(current_user)
    return list(
        session.exec(select(InviteToken).order_by(InviteToken.created_at.desc())).all()
    )


@router.post("", response_model=InviteTokenPublic, status_code=status.HTTP_201_CREATED)
def create_invite(
    payload: InviteCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> InviteToken:
    _ensure_admin(current_user)
    invite = InviteToken(
        token=_new_unique_token(session),
        created_by=current_user.id,
        expires_at=datetime.now(UTC) + timedelta(days=payload.expires_in_days),
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite
