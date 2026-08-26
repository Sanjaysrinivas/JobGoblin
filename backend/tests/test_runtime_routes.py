from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models import User


def test_runtime_configuration_reports_server_values(session):
    from app.main import app

    user = User(email="runtime@example.com", password_hash="x", display_name="Runtime")
    session.add(user)
    session.commit()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        response = client.get("/api/runtime/configuration")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert set(response.json()) == {
        "ai_provider",
        "ai_model",
        "local_ai",
        "discovery_provider",
    }
