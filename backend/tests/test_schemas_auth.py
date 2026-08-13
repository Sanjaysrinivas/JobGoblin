import uuid

import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, RegisterRequest, UserPublic


def test_register_request_fields():
    req = RegisterRequest(
        email="Person@Example.com", password="hunter2pw", invite_token="abc"
    )
    assert req.email == "Person@Example.com"
    assert req.password == "hunter2pw"
    assert req.invite_token == "abc"


def test_register_request_rejects_bad_email():
    with pytest.raises(ValidationError):
        RegisterRequest(email="not-an-email", password="hunter2pw", invite_token="abc")


def test_login_request_fields():
    req = LoginRequest(email="a@b.com", password="pw")
    assert req.email == "a@b.com"


def test_user_public_serialises_expected_fields():
    uid = uuid.uuid4()
    pub = UserPublic(id=uid, email="a@b.com", display_name="A", is_admin=False)
    dumped = pub.model_dump()
    assert dumped == {
        "id": uid,
        "email": "a@b.com",
        "display_name": "A",
        "is_admin": False,
    }
