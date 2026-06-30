import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_default_max_upload_mb_is_10():
    settings = get_settings()
    assert settings.max_upload_mb == 10


def test_env_overrides_max_upload_mb(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "25")
    get_settings.cache_clear()
    try:
        assert get_settings().max_upload_mb == 25
    finally:
        get_settings.cache_clear()


def test_production_requires_secret_key_override():
    with pytest.raises(ValidationError):
        Settings(app_env="production")  # still using the default dev secret


def test_production_rejects_default_db_credentials():
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            app_secret_key="a-sufficiently-long-random-production-secret",
        )  # secret overridden, but DB creds are still the default


def test_production_with_real_secrets_is_valid():
    settings = Settings(
        app_env="production",
        app_secret_key="a-sufficiently-long-random-production-secret",
        database_url="postgresql+psycopg://realuser:realpass@db:5432/jobgoblin",
    )
    assert settings.app_env == "production"
