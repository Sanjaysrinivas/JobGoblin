"""Tests for TOTP helpers and the MFA-pending token (security module)."""

from datetime import timedelta

import pyotp
import pytest
from jose import JWTError

from app.core import totp
from app.core.security import (
    create_mfa_pending_token,
    decode_mfa_pending_token,
)


def test_generate_secret_is_usable_base32():
    secret = totp.generate_secret()
    # pyotp accepts it and produces a 6-digit code
    code = pyotp.TOTP(secret).now()
    assert len(code) == 6
    assert code.isdigit()


def test_provisioning_uri_contains_issuer_and_account():
    secret = totp.generate_secret()
    uri = totp.provisioning_uri(secret, account_name="user@example.com", issuer="JobGoblin")
    assert uri.startswith("otpauth://totp/")
    assert "issuer=JobGoblin" in uri
    assert "user%40example.com" in uri or "user@example.com" in uri


def test_qr_data_uri_is_png_base64():
    secret = totp.generate_secret()
    uri = totp.provisioning_uri(secret, account_name="u@e.com", issuer="JobGoblin")
    data_uri = totp.qr_data_uri(uri)
    assert data_uri.startswith("data:image/png;base64,")
    assert len(data_uri) > 100


def test_verify_code_accepts_current_and_rejects_wrong():
    secret = totp.generate_secret()
    valid = pyotp.TOTP(secret).now()
    assert totp.verify_code(secret, valid) is True
    assert totp.verify_code(secret, "000000") is False
    assert totp.verify_code(secret, "not-a-code") is False
    assert totp.verify_code(None, valid) is False


def test_match_timestep_returns_step_for_valid_code():
    secret = totp.generate_secret()
    valid = pyotp.TOTP(secret).now()
    step = totp.match_timestep(secret, valid)
    assert step is not None
    assert isinstance(step, int)


def test_match_timestep_returns_none_for_wrong_code():
    secret = totp.generate_secret()
    assert totp.match_timestep(secret, "000000") is None
    assert totp.match_timestep(secret, "not-a-code") is None
    assert totp.match_timestep(None, "123456") is None


def test_match_timestep_rejects_replay_at_or_below_last_step():
    secret = totp.generate_secret()
    valid = pyotp.TOTP(secret).now()
    step = totp.match_timestep(secret, valid)
    # Replaying the same code once its step has been consumed must be rejected.
    assert totp.match_timestep(secret, valid, last_timestep=step) is None
    # A future last_timestep also blocks it.
    assert totp.match_timestep(secret, valid, last_timestep=step + 1) is None
    # A lower last_timestep still admits it.
    assert totp.match_timestep(secret, valid, last_timestep=step - 1) == step


def test_mfa_pending_token_round_trip():
    token = create_mfa_pending_token("user-xyz")
    assert decode_mfa_pending_token(token) == "user-xyz"


def test_mfa_pending_token_rejects_expired():
    token = create_mfa_pending_token("u", expires_delta=timedelta(seconds=-1))
    with pytest.raises(JWTError):
        decode_mfa_pending_token(token)


def test_session_token_is_not_accepted_as_mfa_pending():
    from app.core.security import create_access_token

    session_token = create_access_token("u")
    with pytest.raises(JWTError):
        decode_mfa_pending_token(session_token)


def test_mfa_pending_token_is_not_accepted_as_session():
    from app.core.security import decode_access_token

    pending = create_mfa_pending_token("u")
    with pytest.raises(JWTError):
        decode_access_token(pending)
