import os

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  — import to populate SQLModel.metadata

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://test:test@localhost:5433/test"
)


@pytest.fixture
def session():
    """A DB session against a freshly-created schema, dropped after each test."""
    engine = create_engine(TEST_DATABASE_URL)
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as s:
            yield s
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()
