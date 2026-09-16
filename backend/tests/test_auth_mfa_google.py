"""Tests for Google OAuth login/signup, the email allowlist gate, and TOTP MFA.

Google's token exchange is never hit over the network: we monkeypatch the
service's identity resolver to return a fake verified (email, sub).
"""

import pyotp
import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.core.config import get_settings
from app.core.database import get_session
from app.main import app
from app.models import User

settings = get_settings()
SESSION_COOKIE = settings.session_cookie_name
MFA_COOKIE = settings.mfa_cookie_name


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _carry(client, resp, cookie_name):
    """Mirror a response cookie onto the client explicitly."""
    import re

    m = re.search(rf"{cookie_name}=([^;]+)", resp.headers.get("set-cookie", ""))
    if m and m.group(1):
        client.cookies.set(cookie_name, m.group(1))
        return m.group(1)
    return None


def _make_user(session, email, *, password="rightpw1", totp_secret=None, totp_enabled=False):
    user = User(
        email=email,
        password_hash=security.hash_password(password),
        display_name=email.split("@", 1)[0],
        totp_secret=totp_secret,
        totp_enabled=totp_enabled,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# ------------------------------------------------------------------ allowlist


def _configure_google():
    get_settings().google_client_id = "test-client-id"
    get_settings().google_client_secret = "test-secret"


def test_google_callback_rejects_non_allowlisted(client, monkeypatch):
    _configure_google()
    get_settings().allowed_emails = "allowed@example.com"

    from app.core import google_oauth

    async def fake_identity(request):
        return ("intruder@example.com", "google-sub-1")

    monkeypatch.setattr(google_oauth, "fetch_verified_identity", fake_identity)

    resp = client.get("/api/auth/google/callback?code=x&state=y", follow_redirects=False)
    assert resp.status_code == 403
    assert resp.json()["code"] == "not_allowlisted"


def test_google_callback_creates_user_and_sets_session(client, session, monkeypatch):
    _configure_google()
    get_settings().allowed_emails = "newgoogle@example.com"

    from app.core import google_oauth

    async def fake_identity(request):
        return ("NewGoogle@example.com", "google-sub-2")

    monkeypatch.setattr(google_oauth, "fetch_verified_identity", fake_identity)

    resp = client.get("/api/auth/google/callback?code=x&state=y", follow_redirects=False)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mfa_enrollment_required"] is True
    assert body["email"] == "newgoogle@example.com"
    assert SESSION_COOKIE in resp.headers.get("set-cookie", "").lower()

    from sqlmodel import select

    created = session.exec(select(User).where(User.google_sub == "google-sub-2")).one()
    assert created.email == "newgoogle@example.com"


def test_google_callback_existing_totp_user_only_sets_mfa_pending(client, session, monkeypatch):
    _configure_google()
    get_settings().allowed_emails = "gmfa@example.com"
    secret = pyotp.random_base32()
    _make_user(session, "gmfa@example.com", totp_secret=secret, totp_enabled=True)
    # mark google_sub via a second login path: create with google_sub
    u = session.exec(__import__("sqlmodel").select(User)).first()  # noqa
    u.google_sub = "google-sub-3"
    session.add(u)
    session.commit()

    from app.core import google_oauth

    async def fake_identity(request):
        return ("gmfa@example.com", "google-sub-3")

    monkeypatch.setattr(google_oauth, "fetch_verified_identity", fake_identity)

    resp = client.get("/api/auth/google/callback?code=x&state=y", follow_redirects=False)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mfa_required"] is True
    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert MFA_COOKIE in set_cookie
    # no full session cookie issued yet
    assert SESSION_COOKIE not in set_cookie


def test_google_login_redirects(client, monkeypatch):
    get_settings().google_client_id = "test-client-id"
    get_settings().google_client_secret = "test-secret"

    from starlette.responses import RedirectResponse

    from app.core import google_oauth

    async def fake_redirect(request):
        return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?client_id=test")

    monkeypatch.setattr(google_oauth, "build_authorization_redirect", fake_redirect)

    resp = client.get("/api/auth/google/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "accounts.google.com" in resp.headers["location"]


# ------------------------------------------------------------------ MFA enroll


def test_mfa_enroll_returns_secret_and_qr(client, session):
    user = _make_user(session, "enroll@example.com")
    token = security.create_access_token(str(user.id))
    client.cookies.set(SESSION_COOKIE, token)

    resp = client.post("/api/auth/mfa/enroll")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "secret" in body and len(body["secret"]) > 10
    assert body["provisioning_uri"].startswith("otpauth://totp/")
    assert body["qr_data_uri"].startswith("data:image/png;base64,")

    session.refresh(user)
    assert user.totp_secret == body["secret"]
    assert user.totp_enabled is False
    assert client.post("/api/auth/mfa/enroll").json()["secret"] == body["secret"]


def test_mfa_enroll_conflict_when_already_enabled(client, session):
    secret = pyotp.random_base32()
    user = _make_user(session, "already@example.com", totp_secret=secret, totp_enabled=True)
    token = security.create_access_token(str(user.id))
    client.cookies.set(SESSION_COOKIE, token)

    resp = client.post("/api/auth/mfa/enroll")
    assert resp.status_code == 409
    assert resp.json()["code"] == "mfa_already_enabled"


def test_mfa_verify_enables_totp(client, session):
    secret = pyotp.random_base32()
    user = _make_user(session, "verify@example.com", totp_secret=secret, totp_enabled=False)
    token = security.create_access_token(str(user.id))
    client.cookies.set(SESSION_COOKIE, token)

    code = pyotp.TOTP(secret).now()
    resp = client.post("/api/auth/mfa/verify", json={"code": code})
    assert resp.status_code == 200, resp.text

    session.refresh(user)
    assert user.totp_enabled is True


def test_mfa_verify_rejects_wrong_code(client, session):
    secret = pyotp.random_base32()
    user = _make_user(session, "verifybad@example.com", totp_secret=secret, totp_enabled=False)
    token = security.create_access_token(str(user.id))
    client.cookies.set(SESSION_COOKIE, token)

    resp = client.post("/api/auth/mfa/verify", json={"code": "000000"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_code"

    session.refresh(user)
    assert user.totp_enabled is False


# ------------------------------------------------------------------ login + MFA gate


def test_password_login_with_totp_enabled_returns_mfa_pending(client, session):
    secret = pyotp.random_base32()
    _make_user(session, "pwmfa@example.com", totp_secret=secret, totp_enabled=True)

    resp = client.post(
        "/api/auth/login", json={"email": "pwmfa@example.com", "password": "rightpw1"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mfa_required"] is True
    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert MFA_COOKIE in set_cookie
    assert SESSION_COOKIE not in set_cookie
    assert "secure" not in set_cookie


def test_password_login_without_totp_sets_session_and_flags_enrollment(client, session):
    _make_user(session, "pwnomfa@example.com")
    resp = client.post(
        "/api/auth/login", json={"email": "pwnomfa@example.com", "password": "rightpw1"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mfa_enrollment_required"] is True
    # A session response carries the user, not the mfa_required flag (review #2).
    assert "mfa_required" not in body
    assert body["email"] == "pwnomfa@example.com"
    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert SESSION_COOKIE in set_cookie


def test_mfa_challenge_completes_login(client, session):
    secret = pyotp.random_base32()
    user = _make_user(session, "challenge@example.com", totp_secret=secret, totp_enabled=True)

    # step 1: primary auth -> mfa pending cookie
    resp = client.post(
        "/api/auth/login", json={"email": "challenge@example.com", "password": "rightpw1"}
    )
    _carry(client, resp, MFA_COOKIE)

    # step 2: challenge with valid code -> full session
    code = pyotp.TOTP(secret).now()
    resp2 = client.post("/api/auth/mfa/challenge", json={"code": code})
    assert resp2.status_code == 200, resp2.text
    body = resp2.json()
    assert body["email"] == "challenge@example.com"
    set_cookie = resp2.headers.get("set-cookie", "").lower()
    assert SESSION_COOKIE in set_cookie

    # the new session cookie authenticates /me
    _carry(client, resp2, SESSION_COOKIE)
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == str(user.id)


def test_mfa_challenge_rejects_wrong_code(client, session):
    secret = pyotp.random_base32()
    _make_user(session, "challengebad@example.com", totp_secret=secret, totp_enabled=True)
    resp = client.post(
        "/api/auth/login", json={"email": "challengebad@example.com", "password": "rightpw1"}
    )
    _carry(client, resp, MFA_COOKIE)

    resp2 = client.post("/api/auth/mfa/challenge", json={"code": "000000"})
    assert resp2.status_code == 400
    assert resp2.json()["code"] == "invalid_code"


def test_mfa_challenge_without_pending_cookie_unauthorized(client, session):
    resp = client.post("/api/auth/mfa/challenge", json={"code": "123456"})
    assert resp.status_code == 401


def test_session_cookie_not_accepted_as_mfa_pending(client, session):
    """A full session token presented on the mfa challenge must be rejected."""
    user = _make_user(session, "sessmix@example.com")
    token = security.create_access_token(str(user.id))
    client.cookies.set(MFA_COOKIE, token)
    resp = client.post("/api/auth/mfa/challenge", json={"code": "123456"})
    assert resp.status_code == 401


# ----------------------------------------------- google_sub conflict (review #5)


def test_google_callback_rejects_conflicting_google_sub(client, session, monkeypatch):
    """An email already linked to a DIFFERENT google_sub must not be re-linked."""
    _configure_google()
    get_settings().allowed_emails = "linked@example.com"
    user = _make_user(session, "linked@example.com")
    user.google_sub = "original-sub"
    session.add(user)
    session.commit()

    from app.core import google_oauth

    async def fake_identity(request):
        return ("linked@example.com", "ATTACKER-sub")

    monkeypatch.setattr(google_oauth, "fetch_verified_identity", fake_identity)

    resp = client.get("/api/auth/google/callback?code=x&state=y", follow_redirects=False)
    assert resp.status_code == 409
    assert resp.json()["code"] == "google_sub_conflict"

    session.refresh(user)
    assert user.google_sub == "original-sub"  # unchanged


def test_google_callback_links_unset_google_sub(client, session, monkeypatch):
    """An existing email/password account with no google_sub gets linked."""
    _configure_google()
    get_settings().allowed_emails = "tolink@example.com"
    user = _make_user(session, "tolink@example.com")
    assert user.google_sub is None

    from app.core import google_oauth

    async def fake_identity(request):
        return ("tolink@example.com", "fresh-sub")

    monkeypatch.setattr(google_oauth, "fetch_verified_identity", fake_identity)

    resp = client.get("/api/auth/google/callback?code=x&state=y", follow_redirects=False)
    assert resp.status_code == 200, resp.text
    session.refresh(user)
    assert user.google_sub == "fresh-sub"


# -------------------------------------------- TOTP replay protection (review #6)


def test_mfa_challenge_rejects_replayed_code(client, session):
    """A code consumed by a successful challenge cannot be reused."""
    secret = pyotp.random_base32()
    _make_user(session, "replay@example.com", totp_secret=secret, totp_enabled=True)

    # primary auth -> mfa pending cookie
    resp = client.post(
        "/api/auth/login", json={"email": "replay@example.com", "password": "rightpw1"}
    )
    _carry(client, resp, MFA_COOKIE)
    code = pyotp.TOTP(secret).now()

    first = client.post("/api/auth/mfa/challenge", json={"code": code})
    assert first.status_code == 200, first.text

    # Re-authenticate (new pending cookie) and replay the SAME code.
    resp2 = client.post(
        "/api/auth/login", json={"email": "replay@example.com", "password": "rightpw1"}
    )
    _carry(client, resp2, MFA_COOKIE)
    replay = client.post("/api/auth/mfa/challenge", json={"code": code})
    assert replay.status_code == 400
    assert replay.json()["code"] == "invalid_code"


def test_mfa_verify_then_challenge_rejects_same_code(client, session):
    """A code used to enroll cannot be replayed on the immediate challenge."""
    secret = pyotp.random_base32()
    user = _make_user(session, "enrollreplay@example.com", totp_secret=secret, totp_enabled=False)
    token = security.create_access_token(str(user.id))
    client.cookies.set(SESSION_COOKIE, token)

    code = pyotp.TOTP(secret).now()
    verify = client.post("/api/auth/mfa/verify", json={"code": code})
    assert verify.status_code == 200, verify.text

    session.refresh(user)
    assert user.last_totp_timestep is not None

    # Now log in (TOTP enabled) and try the same code on the challenge.
    client.cookies.clear()
    resp = client.post(
        "/api/auth/login", json={"email": "enrollreplay@example.com", "password": "rightpw1"}
    )
    _carry(client, resp, MFA_COOKIE)
    replay = client.post("/api/auth/mfa/challenge", json={"code": code})
    assert replay.status_code == 400
    assert replay.json()["code"] == "invalid_code"


# --------------------------------------------------- rate limiting (review #1)


def test_login_rate_limited(client, session):
    """Exceeding the per-IP login limit yields a 429 with the standard envelope."""
    _make_user(session, "rl@example.com")
    get_settings().auth_rate_limit = "3/minute"
    try:
        codes = [
            client.post(
                "/api/auth/login", json={"email": "rl@example.com", "password": "wrongpw"}
            ).status_code
            for _ in range(5)
        ]
    finally:
        get_settings().auth_rate_limit = "20/minute"

    assert 429 in codes
    # the first few are 401 (bad password), then 429 once the limit trips
    assert codes[0] == 401


def test_mfa_challenge_rate_limited(client, session):
    secret = pyotp.random_base32()
    _make_user(session, "rlmfa@example.com", totp_secret=secret, totp_enabled=True)
    resp = client.post(
        "/api/auth/login", json={"email": "rlmfa@example.com", "password": "rightpw1"}
    )
    _carry(client, resp, MFA_COOKIE)

    get_settings().mfa_rate_limit = "2/minute"
    try:
        codes = [
            client.post("/api/auth/mfa/challenge", json={"code": "000000"}).status_code
            for _ in range(4)
        ]
    finally:
        get_settings().mfa_rate_limit = "10/minute"

    assert 429 in codes


# ----------------------------------- fail-closed email_verified (review #4)


class _FakeGoogleClient:
    """Minimal stand-in for the Authlib client used by fetch_verified_identity."""

    def __init__(self, userinfo):
        self._userinfo = userinfo

    async def authorize_access_token(self, request):
        return {"userinfo": self._userinfo}


@pytest.mark.parametrize(
    "userinfo",
    [
        {"email": "u@example.com", "sub": "s1"},  # email_verified missing
        {"email": "u@example.com", "sub": "s1", "email_verified": False},
        {"email": "u@example.com", "sub": "s1", "email_verified": "false"},
        {"sub": "s1", "email_verified": True},  # no email
        {"email": "u@example.com", "email_verified": True},  # no sub
    ],
)
async def test_fetch_verified_identity_fails_closed(monkeypatch, userinfo):
    from app.core import google_oauth

    monkeypatch.setattr(google_oauth, "_client", lambda: _FakeGoogleClient(userinfo))
    with pytest.raises(ValueError):
        await google_oauth.fetch_verified_identity(request=None)


@pytest.mark.parametrize("verified", [True, "true", "True"])
async def test_fetch_verified_identity_accepts_verified(monkeypatch, verified):
    from app.core import google_oauth

    userinfo = {"email": "Ok@example.com", "sub": "s9", "email_verified": verified}
    monkeypatch.setattr(google_oauth, "_client", lambda: _FakeGoogleClient(userinfo))
    email, sub = await google_oauth.fetch_verified_identity(request=None)
    assert email == "Ok@example.com"
    assert sub == "s9"
