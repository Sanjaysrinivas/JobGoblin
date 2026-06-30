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
