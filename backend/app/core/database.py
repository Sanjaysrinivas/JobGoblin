"""SQLModel engine and the FastAPI session dependency."""

from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import get_settings

settings = get_settings()

# pool_pre_ping avoids handing out connections dropped by the DB/idle timeouts.
engine = create_engine(settings.database_url, pool_pre_ping=True)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session; closed automatically when the request ends."""
    with Session(engine) as session:
        yield session
