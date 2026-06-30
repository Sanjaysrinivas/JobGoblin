from sqlmodel import Session

from app.core import database


def test_get_session_yields_session():
    gen = database.get_session()
    s = next(gen)
    try:
        assert isinstance(s, Session)
    finally:
        gen.close()


def test_engine_uses_configured_database_url():
    from app.core.config import get_settings

    assert str(database.engine.url).startswith("postgresql")
    # database_url from settings drives the engine
    assert get_settings().database_url.split("://")[0] in str(database.engine.url)
