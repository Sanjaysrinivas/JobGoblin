from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.core import security
from app.core.config import get_settings
from app.core.database import get_session
from app.main import app
from app.models import InviteToken, User

COOKIE = get_settings().session_cookie_name


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_user(session, *, email: str, is_admin: bool = False) -> User:
    user = User(
        email=email,
        password_hash=security.hash_password("rightpw1"),
        display_name=email.split("@", 1)[0],
        is_admin=is_admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _login(client, email: str) -> None:
    resp = client.post("/api/auth/login", json={"email": email, "password": "rightpw1"})
    token = resp.cookies.get(COOKIE)
    if token is None:
        import re

        match = re.search(rf"{COOKIE}=([^;]+)", resp.headers.get("set-cookie", ""))
        token = match.group(1) if match else None
    client.cookies.set(COOKIE, token)


def test_create_invite_requires_auth(client):
    resp = client.post("/api/invites", json={"expires_in_days": 7})

    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authenticated"


def test_create_invite_forbids_non_admin(client, session):
    user = _make_user(session, email="user@example.com")
    _login(client, user.email)

    resp = client.post("/api/invites", json={"expires_in_days": 7})

    assert resp.status_code == 403
    assert resp.json()["code"] == "admin_required"


def test_admin_can_create_and_list_invites(client, session):
    admin = _make_user(session, email="admin@example.com", is_admin=True)
    _login(client, admin.email)

    create = client.post("/api/invites", json={"expires_in_days": 14})

    assert create.status_code == 201, create.text
    created = create.json()
    assert created["token"]
    assert created["created_by"] == str(admin.id)
    assert created["used_by"] is None
    assert datetime.fromisoformat(created["expires_at"]) > datetime.now(UTC) + timedelta(days=13)

    listing = client.get("/api/invites")
    assert listing.status_code == 200
    assert [item["token"] for item in listing.json()] == [created["token"]]


def test_created_invite_allows_signup(client, session):
    admin = _make_user(session, email="admin@example.com", is_admin=True)
    _login(client, admin.email)
    invite_token = client.post("/api/invites", json={}).json()["token"]
    client.cookies.clear()

    resp = client.post(
        "/api/auth/register",
        json={
            "email": "new@example.com",
            "password": "hunter2pw",
            "invite_token": invite_token,
        },
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["email"] == "new@example.com"
    invite = session.exec(select(InviteToken).where(InviteToken.token == invite_token)).one()
    assert invite.used_by is not None
