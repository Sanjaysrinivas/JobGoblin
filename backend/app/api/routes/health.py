from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe - does not touch the database."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness() -> dict[str, str]:
    """Readiness probe that verifies the database accepts a trivial query."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"detail": "database unavailable", "code": "database_unavailable"},
        ) from exc
    return {"status": "ok", "database": "ok"}
