from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import health as health_routes
from app.main import app

client = TestClient(app)


class ReadyConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement):
        self.statement = statement


class ReadyEngine:
    def connect(self):
        return ReadyConnection()


class BrokenEngine:
    def connect(self):
        raise SQLAlchemyError("database down")


def test_health_returns_ok():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_does_not_touch_database(monkeypatch):
    monkeypatch.setattr(health_routes, "engine", BrokenEngine())

    resp = client.get("/api/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_returns_ok_when_database_accepts_query(monkeypatch):
    monkeypatch.setattr(health_routes, "engine", ReadyEngine())

    resp = client.get("/api/health/ready")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


def test_ready_returns_503_when_database_unavailable(monkeypatch):
    monkeypatch.setattr(health_routes, "engine", BrokenEngine())

    resp = client.get("/api/health/ready")

    assert resp.status_code == 503
    assert resp.json() == {"detail": "database unavailable", "code": "database_unavailable"}


def test_cors_allows_frontend_origin_in_dev():
    resp = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
