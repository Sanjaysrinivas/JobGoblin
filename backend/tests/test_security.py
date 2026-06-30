from datetime import UTC, datetime, timedelta

import pytest
from jose import JWTError

from app.core import security


def test_password_hash_verify_round_trip():
    hashed = security.hash_password("s3cret-pass")
    assert hashed != "s3cret-pass"
    assert hashed.startswith("$argon2id$")
    assert security.verify_password("s3cret-pass", hashed) is True
    assert security.verify_password("wrong-pass", hashed) is False


def test_hash_password_is_salted():
    assert security.hash_password("same") != security.hash_password("same")


def test_jwt_encode_decode_round_trip():
    token = security.create_access_token("user-123")
    assert security.decode_access_token(token) == "user-123"


def test_jwt_rejects_tampered_token():
    token = security.create_access_token("user-123")
    with pytest.raises(JWTError):
        security.decode_access_token(token + "tamper")


def test_jwt_rejects_expired_token():
    token = security.create_access_token(
        "user-123", expires_delta=timedelta(seconds=-1)
    )
    with pytest.raises(JWTError):
        security.decode_access_token(token)


def test_jwt_decode_rejects_token_without_subject():
    from jose import jwt

    from app.core.config import get_settings

    token = jwt.encode(
        {"foo": "bar"},
        get_settings().app_secret_key,
        algorithm=security.JWT_ALGORITHM,
    )
    with pytest.raises(JWTError):
        security.decode_access_token(token)


def test_jwt_decode_returns_subject():
    token = security.create_access_token("abc")
    # also sanity check it carries an exp claim in the future
    from jose import jwt

    from app.core.config import get_settings

    claims = jwt.decode(
        token, get_settings().app_secret_key, algorithms=[security.JWT_ALGORITHM]
    )
    assert claims["sub"] == "abc"
    assert datetime.fromtimestamp(claims["exp"], tz=UTC) > datetime.now(UTC)
