import os

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  — import to populate SQLModel.metadata

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://test:test@localhost:5433/test"
)


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
