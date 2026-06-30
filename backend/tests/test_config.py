from app.core.config import get_settings


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
