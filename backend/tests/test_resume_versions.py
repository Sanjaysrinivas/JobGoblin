import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.models import Resume, ResumeVersion, User
from tests.sample_docs import PDF_CONTENT_TYPE, make_pdf_bytes


@pytest.fixture(autouse=True)
def _mock_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("FILE_STORAGE_PATH", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def user(session) -> User:
    u = User(email="owner@example.com", password_hash="x", display_name="Owner")
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


@pytest.fixture
def client(session, user):
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _upload(client, text="Alice Engineer\nPython", filename="alice.pdf"):
    return client.post(
        "/api/resumes/upload",
        files={"file": (filename, make_pdf_bytes(text), PDF_CONTENT_TYPE)},
    )


def _other_resume(session) -> tuple[Resume, ResumeVersion]:
    other = User(email="other@example.com", password_hash="x", display_name="Other")
    session.add(other)
    session.commit()
    resume = Resume(
        user_id=other.id,
        title="secret",
        original_filename="secret.pdf",
        file_key="k",
        content_type=PDF_CONTENT_TYPE,
        file_size=1,
        extracted_text="source secret",
        parsed_json={"summary": "source"},
    )
    version = ResumeVersion(
        resume_id=resume.id,
        title="secret",
        extracted_text="version secret",
        parsed_json={"summary": "version"},
        is_current=True,
    )
    session.add(resume)
    session.add(version)
    session.commit()
    session.refresh(resume)
    session.refresh(version)
    return resume, version


def test_upload_creates_initial_current_version(client, session):
    resp = _upload(client, "Alice Engineer\nPython expert")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    version_id = uuid.UUID(body["current_version_id"])
    version = session.get(ResumeVersion, version_id)

    assert body["version_count"] == 1
    assert body["current_version"]["id"] == body["current_version_id"]
    assert version is not None
    assert version.resume_id == uuid.UUID(body["id"])
    assert version.is_current is True
    assert "Alice Engineer" in version.extracted_text
    assert version.parsed_json == body["parsed_json"]

    versions = client.get(f"/api/resumes/{body['id']}/versions")
    assert versions.status_code == 200
    assert [v["id"] for v in versions.json()] == [body["current_version_id"]]


def test_duplicate_edit_make_current_preserves_source_resume_facts(client, session):
    uploaded = _upload(client, "Original Source\nPython").json()
    resume = session.get(Resume, uuid.UUID(uploaded["id"]))
    source_text = resume.extracted_text
    source_json = resume.parsed_json

    duplicate = client.post(
        f"/api/resumes/{uploaded['id']}/versions",
        json={"source_version_id": uploaded["current_version_id"], "title": "Edited"},
    )
    assert duplicate.status_code == 201, duplicate.text
    edited_id = duplicate.json()["id"]

    patched = client.patch(
        f"/api/resumes/{uploaded['id']}/versions/{edited_id}",
        json={"extracted_text": "Edited version text", "parsed_json": {"summary": "Edited"}},
    )
    assert patched.status_code == 200
    assert patched.json()["extracted_text"] == "Edited version text"

    current = client.post(f"/api/resumes/{uploaded['id']}/versions/{edited_id}/make-current")
    assert current.status_code == 200
    assert current.json()["is_current"] is True

    detail = client.get(f"/api/resumes/{uploaded['id']}")
    assert detail.status_code == 200
    assert detail.json()["current_version_id"] == edited_id
    assert detail.json()["version_count"] == 2
    assert detail.json()["current_version"]["id"] == edited_id
    assert detail.json()["title"] == "Edited"
    assert detail.json()["extracted_text"] == "Edited version text"
    assert detail.json()["parsed_json"] == {"summary": "Edited"}

    session.refresh(resume)
    assert resume.extracted_text == source_text
    assert resume.parsed_json == source_json


def test_legacy_resume_patch_edits_current_version_not_source_facts(client, session):
    uploaded = _upload(client, "Source Facts\nPython").json()
    resume = session.get(Resume, uuid.UUID(uploaded["id"]))
    source_text = resume.extracted_text

    resp = client.patch(
        f"/api/resumes/{uploaded['id']}", json={"extracted_text": "legacy edit"}
    )
    assert resp.status_code == 200
    assert resp.json()["extracted_text"] == "legacy edit"

    session.refresh(resume)
    version = session.get(ResumeVersion, uuid.UUID(uploaded["current_version_id"]))
    assert resume.extracted_text == source_text
    assert version.extracted_text == "legacy edit"


def test_delete_last_version_is_rejected(client):
    uploaded = _upload(client).json()
    resp = client.delete(
        f"/api/resumes/{uploaded['id']}/versions/{uploaded['current_version_id']}"
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "last_resume_version"


def test_cross_user_version_access_returns_404(client, session):
    resume, version = _other_resume(session)

    list_resp = client.get(f"/api/resumes/{resume.id}/versions")
    patch_resp = client.patch(
        f"/api/resumes/{resume.id}/versions/{version.id}",
        json={"extracted_text": "mine now"},
    )
    make_current_resp = client.post(
        f"/api/resumes/{resume.id}/versions/{version.id}/make-current"
    )
    delete_resp = client.delete(f"/api/resumes/{resume.id}/versions/{version.id}")

    assert list_resp.status_code == 404
    assert patch_resp.status_code == 404
    assert make_current_resp.status_code == 404
    assert delete_resp.status_code == 404
