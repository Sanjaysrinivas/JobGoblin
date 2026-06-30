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
    """Mirror a Secure cookie from a response onto the client (TestClient is http)."""
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

    from app.core import google_oauth

    def fake_url(state):
        return "https://accounts.google.com/o/oauth2/v2/auth?client_id=test"

    monkeypatch.setattr(google_oauth, "build_authorization_url", fake_url)

    resp = client.get("/api/auth/google/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "accounts.google.com" in resp.headers["location"]


# ------------------------------------------------------------------ MFA enroll

def test_mfa_enroll_returns_secret_and_qr(client, session):
    user = _make_user(session, "enroll@example.com")
    token = security.create_access_token(str(user.id))
    client.cookies.set(SESSION_COOKIE, token)

    resp = client.get("/api/auth/mfa/enroll")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "secret" in body and len(body["secret"]) > 10
    assert body["provisioning_uri"].startswith("otpauth://totp/")
    assert body["qr_data_uri"].startswith("data:image/png;base64,")

    session.refresh(user)
    assert user.totp_secret == body["secret"]
    assert user.totp_enabled is False


def test_mfa_enroll_conflict_when_already_enabled(client, session):
    secret = pyotp.random_base32()
    user = _make_user(session, "already@example.com", totp_secret=secret, totp_enabled=True)
    token = security.create_access_token(str(user.id))
    client.cookies.set(SESSION_COOKIE, token)

    resp = client.get("/api/auth/mfa/enroll")
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


def test_password_login_without_totp_sets_session_and_flags_enrollment(client, session):
    _make_user(session, "pwnomfa@example.com")
    resp = client.post(
        "/api/auth/login", json={"email": "pwnomfa@example.com", "password": "rightpw1"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mfa_enrollment_required"] is True
    assert body["mfa_required"] is False
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
