"""Request/response models for the auth endpoints.

A minimal email-format check is done locally (with a regex) so we do not need to
pull in the optional ``email-validator`` dependency that Pydantic's ``EmailStr``
requires. Emails are normalised to lowercase elsewhere (the route layer) before
they touch the database.
"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str) -> str:
    value = value.strip()
    if not _EMAIL_RE.match(value):
        raise ValueError("invalid email address")
    return value


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    invite_token: str | None = None

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        return _validate_email(value)

    @field_validator("invite_token")
    @classmethod
    def _check_invite_token(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        return _validate_email(value)


class UserPublic(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool

    model_config = {"from_attributes": True}


class InviteCreateRequest(BaseModel):
    expires_in_days: int = Field(default=7, ge=1, le=90)


class InviteTokenPublic(BaseModel):
    id: uuid.UUID
    token: str
    created_by: uuid.UUID
    used_by: uuid.UUID | None
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class MfaCodeRequest(BaseModel):
    """A 6-digit TOTP code submitted for enrollment verification or challenge."""

    code: str


class SessionUserResponse(UserPublic):
    """Returned when a full session cookie was set.

    Carries the authenticated user plus ``mfa_enrollment_required``: true when a
    session was granted but the user has no second factor yet and should be
    guided to ``/auth/mfa/enroll``.
    """

    mfa_enrollment_required: bool = False


class MfaRequiredResponse(BaseModel):
    """Returned when primary auth succeeded but a second factor is pending.

    No user identity is exposed (no session has been granted yet); only the
    ``mfa_required`` flag. The client must call ``/auth/mfa/challenge``.
    """

    mfa_required: bool = True


# A primary-auth call resolves to exactly one of these two shapes.
PrimaryAuthResponse = SessionUserResponse | MfaRequiredResponse


class MfaEnrollResponse(BaseModel):
    """Enrollment payload: the secret, its provisioning URI, and a QR image."""

    secret: str
    provisioning_uri: str
    qr_data_uri: str
