"""Request/response models for the auth endpoints.

A minimal email-format check is done locally (with a regex) so we do not need to
pull in the optional ``email-validator`` dependency that Pydantic's ``EmailStr``
requires. Emails are normalised to lowercase elsewhere (the route layer) before
they touch the database.
"""

import re
import uuid

from pydantic import BaseModel, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str) -> str:
    value = value.strip()
    if not _EMAIL_RE.match(value):
        raise ValueError("invalid email address")
    return value


class RegisterRequest(BaseModel):
    email: str
    password: str
    invite_token: str

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        return _validate_email(value)


class LoginRequest(BaseModel):
    email: str
    password: str

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


class MfaCodeRequest(BaseModel):
    """A 6-digit TOTP code submitted for enrollment verification or challenge."""

    code: str


class AuthResult(UserPublic):
    """Primary-auth result. Extends :class:`UserPublic` (so ``email``/``id`` stay
    top-level for existing callers) with the MFA next-step flags.

    - ``mfa_required``: TOTP is enabled; only an mfa_pending token was issued and
      the client must call ``/auth/mfa/challenge`` to obtain a session. In this
      case the user fields are NOT populated (no session yet) — only the flag.
    - ``mfa_enrollment_required``: a full session was set, but the user has not
      enrolled a second factor yet and should be guided to ``/auth/mfa/enroll``.
    """

    mfa_required: bool = False
    mfa_enrollment_required: bool = False


class MfaEnrollResponse(BaseModel):
    """Enrollment payload: the secret, its provisioning URI, and a QR image."""

    secret: str
    provisioning_uri: str
    qr_data_uri: str
