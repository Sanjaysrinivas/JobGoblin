import pytest
from sqlmodel import select

from app.core import security, startup
from app.core.config import Settings
from app.models import User


@pytest.fixture
def patch_settings(monkeypatch):
    def _apply(**overrides):
        base = dict(admin_email="", admin_password="")
        base.update(overrides)
        monkeypatch.setattr(startup, "get_settings", lambda: Settings(**base))

    return _apply


def test_seed_admin_noop_when_env_empty(session, patch_settings):
    patch_settings()
    assert startup.seed_admin(session=session) is None
    assert session.exec(select(User)).all() == []


def test_seed_admin_creates_admin(session, patch_settings):
    patch_settings(admin_email="Boss@Example.com", admin_password="bosspw123")
    admin = startup.seed_admin(session=session)
    assert admin is not None
    assert admin.is_admin is True
    assert admin.email == "boss@example.com"  # lowercased
    assert security.verify_password("bosspw123", admin.password_hash)


def test_seed_admin_idempotent(session, patch_settings):
    patch_settings(admin_email="boss@example.com", admin_password="bosspw123")
    first = startup.seed_admin(session=session)
    assert first is not None
    second = startup.seed_admin(session=session)
    assert second is None
    assert len(session.exec(select(User)).all()) == 1


def test_seed_admin_skips_when_other_admin_exists(session, patch_settings):
    session.add(
        User(
            email="existing-admin@example.com",
            password_hash=security.hash_password("x"),
            display_name="Existing",
            is_admin=True,
        )
    )
    session.commit()
    patch_settings(admin_email="boss@example.com", admin_password="bosspw123")
    assert startup.seed_admin(session=session) is None
