import os

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  — import to populate SQLModel.metadata

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://test:test@localhost:5433/test"
)


@pytest.fixture(autouse=True)
def _reset_settings():
    """Restore mutable auth settings + clear rate-limit state around each test.

    Several auth tests mutate the cached Settings instance (allowlist, Google
    creds, rate-limit strings) in place; snapshot and restore them so tests stay
    isolated. The slowapi limiter shares an in-process counter store keyed by IP
    (all tests share the TestClient IP), so reset it too or limits leak across
    tests and cause spurious 429s.
    """
    from app.core.config import get_settings
    from app.core.ratelimit import limiter

    limiter.reset()
    s = get_settings()
    keys = (
        "allowed_emails",
        "google_client_id",
        "google_client_secret",
        "auth_rate_limit",
        "mfa_rate_limit",
        "rate_limit_enabled",
    )
    saved = {k: getattr(s, k) for k in keys}
    yield
    for k, v in saved.items():
        setattr(s, k, v)
    limiter.reset()


@pytest.fixture(scope="session")
def engine():
    """Create the schema once for the whole test session."""
    eng = create_engine(TEST_DATABASE_URL)
    SQLModel.metadata.create_all(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session(engine):
    """A session per test; tables are truncated afterwards for isolation.

    TRUNCATE (rather than a rolled-back transaction) keeps tests isolated even
    when the code under test calls ``session.commit()``, while avoiding the cost
    of recreating the schema for every test.
    """
    with Session(engine) as s:
        yield s

    tables = ", ".join(t.name for t in SQLModel.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
