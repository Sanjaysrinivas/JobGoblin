import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.core.config import get_settings
from app.core.database import get_session
from app.main import app
from app.models import InviteToken, User

COOKIE = get_settings().session_cookie_name


def _login_and_carry_cookie(client, email, password):
    """Log in and copy the session cookie onto the client.

    This keeps tests independent of httpx cookie-jar behavior across
    Secure/non-Secure modes.
    """
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.cookies.get(COOKIE)
    if token is None:
        # parse from Set-Cookie header (Secure cookies aren't put in resp.cookies over http)
        import re

        m = re.search(rf"{COOKIE}=([^;]+)", resp.headers.get("set-cookie", ""))
        token = m.group(1) if m else None
    client.cookies.set(COOKIE, token)
    return resp


@pytest.fixture
def client(session):
    """TestClient whose DB dependency yields the test session."""
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_admin(session) -> User:
    admin = User(
        email="admin@jobgoblin.test",
        password_hash=security.hash_password("adminpw"),
        display_name="Admin",
        is_admin=True,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


def _make_invite(session, created_by: uuid.UUID, *, token="invite-123", expired=False,
                 used_by=None) -> InviteToken:
    expires_at = datetime.now(UTC) + (
        timedelta(days=-1) if expired else timedelta(days=7)
    )
    invite = InviteToken(
        token=token, created_by=created_by, used_by=used_by, expires_at=expires_at
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite


# ---------------------------------------------------------------- register

def test_register_success_with_valid_invite(client, session):
    admin = _make_admin(session)
    _make_invite(session, admin.id)

    resp = client.post(
        "/api/auth/register",
        json={"email": "New@Example.com", "password": "hunter2pw",
              "invite_token": "invite-123"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "new@example.com"  # lowercased
    assert body["is_admin"] is False
    assert "id" in body
    assert COOKIE in resp.headers["set-cookie"].lower()

    # token marked used + user persisted
    invite = session.get(InviteToken, _make_invite_id(session, "invite-123"))
    assert invite.used_by is not None


def _make_invite_id(session, token):
    from sqlmodel import select
    return session.exec(select(InviteToken).where(InviteToken.token == token)).one().id


def test_register_rejects_invalid_invite(client, session):
    _make_admin(session)
    resp = client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "hunter2pw",
              "invite_token": "does-not-exist"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_invite"


def test_register_rejects_used_invite(client, session):
    admin = _make_admin(session)
    _make_invite(session, admin.id, token="used-tok", used_by=admin.id)
    resp = client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "hunter2pw",
              "invite_token": "used-tok"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_invite"


def test_register_rejects_expired_invite(client, session):
    admin = _make_admin(session)
    _make_invite(session, admin.id, token="exp-tok", expired=True)
    resp = client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "hunter2pw",
              "invite_token": "exp-tok"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_invite"


def test_register_duplicate_email_conflict(client, session):
    admin = _make_admin(session)
    _make_invite(session, admin.id, token="tok-a")
    _make_invite(session, admin.id, token="tok-b")
    first = client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "hunter2pw",
              "invite_token": "tok-a"},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/auth/register",
        json={"email": "DUP@example.com", "password": "hunter2pw",
              "invite_token": "tok-b"},
    )
    assert second.status_code == 409
    assert second.json()["code"] == "email_taken"


# ---------------------------------------------------------------- login

def test_login_success_sets_cookie(client, session):
    user = User(
        email="login@example.com",
        password_hash=security.hash_password("rightpw1"),
        display_name="Login",
    )
    session.add(user)
    session.commit()

    resp = client.post(
        "/api/auth/login",
        json={"email": "Login@example.com", "password": "rightpw1"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "login@example.com"
    set_cookie = resp.headers["set-cookie"].lower()
    assert COOKIE in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "secure" not in set_cookie


def test_cookie_secure_is_case_insensitive():
    from app.api.routes import auth as auth_routes

    settings = get_settings()
    settings.app_env = "DEVELOPMENT"
    assert auth_routes._cookie_secure() is False

    settings.app_env = "Production"
    assert auth_routes._cookie_secure() is True


def test_login_wrong_password_unauthorized(client, session):
    user = User(
        email="login2@example.com",
        password_hash=security.hash_password("rightpw1"),
        display_name="Login2",
    )
    session.add(user)
    session.commit()
    resp = client.post(
        "/api/auth/login",
        json={"email": "login2@example.com", "password": "wrongpw"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_credentials"


def test_login_unknown_email_unauthorized(client, session):
    resp = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_credentials"


# ---------------------------------------------------------------- /me + logout

def test_me_authenticated_returns_user(client, session):
    user = User(
        email="me@example.com",
        password_hash=security.hash_password("rightpw1"),
        display_name="Me",
    )
    session.add(user)
    session.commit()
    _login_and_carry_cookie(client, "me@example.com", "rightpw1")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


def test_me_unauthenticated_unauthorized(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authenticated"


def test_me_with_token_for_deleted_user_unauthorized(client, session):
    # craft a valid token for a user id that does not exist
    token = security.create_access_token(str(uuid.uuid4()))
    client.cookies.set(COOKIE, token)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_token_missing_sub_unauthorized(client, session):
    # a validly-signed token that has no `sub` claim must yield 401, not 500
    from jose import jwt

    token = jwt.encode(
        {"foo": "bar"},
        get_settings().app_secret_key,
        algorithm=get_settings().jwt_algorithm,
    )
    client.cookies.set(COOKIE, token)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authenticated"


def test_logout_clears_cookie(client, session):
    user = User(
        email="out@example.com",
        password_hash=security.hash_password("rightpw1"),
        display_name="Out",
    )
    session.add(user)
    session.commit()
    _login_and_carry_cookie(client, "out@example.com", "rightpw1")
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 204
    set_cookie = resp.headers["set-cookie"].lower()
    assert COOKIE in set_cookie
    # cookie deletion is signalled by an empty value / expiry in the past
    assert ('max-age=0' in set_cookie) or ('expires=' in set_cookie)
