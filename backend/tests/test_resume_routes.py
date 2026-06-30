"""Integration tests for the resume endpoints (design.md §4.2).

Uses MockProvider (AI_PROVIDER=mock) and a temp file-storage directory so no
Ollama and no shared filesystem state are required. ``get_current_user`` and
``get_session`` are overridden to a seeded test user and the test DB session.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.models import Resume, User
from tests.sample_docs import (
    DOCX_CONTENT_TYPE,
    PDF_CONTENT_TYPE,
    make_docx_bytes,
    make_pdf_bytes,
)


@pytest.fixture(autouse=True)
def _mock_settings(tmp_path, monkeypatch):
    """Force MockProvider + a per-test storage dir, refreshing the cache."""
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("FILE_STORAGE_PATH", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def user(session) -> User:
    u = User(
        email="owner@example.com",
        password_hash="x",
        display_name="Owner",
    )
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


def _upload(client, *, data: bytes, filename: str, content_type: str):
    return client.post(
        "/api/resumes/upload",
        files={"file": (filename, data, content_type)},
    )


# ---------------------------------------------------------------- upload

def test_upload_pdf_extracts_and_parses(client, session):
    resp = _upload(
        client,
        data=make_pdf_bytes("Alice Engineer\nPython expert"),
        filename="alice.pdf",
        content_type=PDF_CONTENT_TYPE,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "alice"
    assert body["content_type"] == PDF_CONTENT_TYPE
    assert "Alice Engineer" in body["extracted_text"]
    # MockProvider returns a schema-conforming parse.
    assert body["parsed_json"] is not None
    assert "skills" in body["parsed_json"]


def test_upload_docx_extracts_and_parses(client):
    resp = _upload(
        client,
        data=make_docx_bytes("Bob Dev\nGo and Rust"),
        filename="bob.docx",
        content_type=DOCX_CONTENT_TYPE,
    )
    assert resp.status_code == 201, resp.text
    assert "Bob Dev" in resp.json()["extracted_text"]


def test_upload_rejects_unsupported_type(client):
    resp = _upload(
        client, data=b"hello", filename="notes.txt", content_type="text/plain"
    )
    assert resp.status_code == 415
    assert resp.json()["code"] == "unsupported_type"


def test_upload_rejects_oversized_file(client, monkeypatch):
    # Shrink the limit so a small file trips it without allocating megabytes.
    monkeypatch.setenv("MAX_UPLOAD_MB", "0")
    get_settings.cache_clear()
    # Re-bind the module-level settings the route captured at import.
    import app.api.routes.resumes as routes

    monkeypatch.setattr(routes, "settings", get_settings())
    resp = _upload(
        client,
        data=make_pdf_bytes("big"),
        filename="big.pdf",
        content_type=PDF_CONTENT_TYPE,
    )
    assert resp.status_code == 413
    assert resp.json()["code"] == "file_too_large"


def test_upload_corrupt_pdf_is_422(client):
    # A file claiming to be a PDF but with junk bytes -> 422, not 500.
    resp = _upload(
        client,
        data=b"this is not a pdf at all",
        filename="broken.pdf",
        content_type=PDF_CONTENT_TYPE,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "unprocessable_file"


def test_upload_succeeds_when_ai_parse_fails(client, monkeypatch):
    # The AI provider being down must NOT 500 the upload — the resume is saved
    # with parsed_json null and can be re-parsed later.
    import app.api.routes.resumes as routes
    from app.services.ai_provider import AIProvider

    class BrokenProvider(AIProvider):
        async def generate_text(self, prompt, *, system=None):
            raise RuntimeError("ollama down")

        async def generate_json(self, prompt, schema, *, system=None):
            raise RuntimeError("ollama down")

    monkeypatch.setattr(routes, "get_ai_provider", lambda: BrokenProvider())
    resp = _upload(
        client,
        data=make_pdf_bytes("Resilient\nPython"),
        filename="resilient.pdf",
        content_type=PDF_CONTENT_TYPE,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "Resilient" in body["extracted_text"]
    assert body["parsed_json"] is None


# ---------------------------------------------------------------- list / get

def test_list_returns_only_current_user(client, session, user):
    _upload(
        client,
        data=make_pdf_bytes("mine"),
        filename="mine.pdf",
        content_type=PDF_CONTENT_TYPE,
    )
    # Another user's resume must not appear.
    other = User(email="other@example.com", password_hash="x", display_name="Other")
    session.add(other)
    session.commit()
    session.add(
        Resume(
            user_id=other.id,
            title="theirs",
            original_filename="theirs.pdf",
            file_key="k",
            content_type=PDF_CONTENT_TYPE,
            file_size=1,
        )
    )
    session.commit()

    resp = client.get("/api/resumes")
    assert resp.status_code == 200
    titles = [r["title"] for r in resp.json()]
    assert titles == ["mine"]


def test_get_other_users_resume_is_404(client, session):
    other = User(email="o2@example.com", password_hash="x", display_name="O2")
    session.add(other)
    session.commit()
    r = Resume(
        user_id=other.id,
        title="secret",
        original_filename="s.pdf",
        file_key="k2",
        content_type=PDF_CONTENT_TYPE,
        file_size=1,
    )
    session.add(r)
    session.commit()
    session.refresh(r)

    resp = client.get(f"/api/resumes/{r.id}")
    assert resp.status_code == 404
    assert resp.json()["code"] == "resume_not_found"


def test_get_unknown_resume_is_404(client):
    resp = client.get(f"/api/resumes/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------- patch

def test_patch_title_and_default_toggle(client, session, user):
    a = _upload(
        client, data=make_pdf_bytes("a"), filename="a.pdf", content_type=PDF_CONTENT_TYPE
    ).json()
    b = _upload(
        client, data=make_pdf_bytes("b"), filename="b.pdf", content_type=PDF_CONTENT_TYPE
    ).json()

    # Make A default.
    r1 = client.patch(f"/api/resumes/{a['id']}", json={"is_default": True, "title": "Primary"})
    assert r1.status_code == 200
    assert r1.json()["is_default"] is True
    assert r1.json()["title"] == "Primary"

    # Now make B default — A must flip to non-default (one default per user).
    r2 = client.patch(f"/api/resumes/{b['id']}", json={"is_default": True})
    assert r2.status_code == 200
    assert r2.json()["is_default"] is True

    a_after = session.get(Resume, uuid.UUID(a["id"]))
    assert a_after.is_default is False


def test_patch_extracted_text(client):
    a = _upload(
        client, data=make_pdf_bytes("x"), filename="x.pdf", content_type=PDF_CONTENT_TYPE
    ).json()
    resp = client.patch(
        f"/api/resumes/{a['id']}", json={"extracted_text": "edited text"}
    )
    assert resp.status_code == 200
    assert resp.json()["extracted_text"] == "edited text"


# ---------------------------------------------------------------- re-parse

def test_reparse_updates_parsed_json(client):
    a = _upload(
        client, data=make_pdf_bytes("y"), filename="y.pdf", content_type=PDF_CONTENT_TYPE
    ).json()
    resp = client.post(f"/api/resumes/{a['id']}/parse")
    assert resp.status_code == 200
    assert resp.json()["parsed_json"] is not None


# ---------------------------------------------------------------- delete

def test_delete_removes_row_and_file(client, session, user):
    body = _upload(
        client, data=make_pdf_bytes("z"), filename="z.pdf", content_type=PDF_CONTENT_TYPE
    ).json()
    resume_id = uuid.UUID(body["id"])

    # The stored file exists on disk before delete.
    stored = session.get(Resume, resume_id)
    from pathlib import Path

    file_path = Path(get_settings().file_storage_path) / stored.file_key
    assert file_path.exists()

    resp = client.delete(f"/api/resumes/{resume_id}")
    assert resp.status_code == 204
    assert session.get(Resume, resume_id) is None
    assert not file_path.exists()


def test_delete_succeeds_when_file_removal_fails(client, session, monkeypatch):
    # Storage failure after the DB commit must not 500 — the row is the source
    # of truth and the delete still returns 204.
    body = _upload(
        client, data=make_pdf_bytes("d"), filename="d.pdf", content_type=PDF_CONTENT_TYPE
    ).json()
    resume_id = uuid.UUID(body["id"])

    import app.api.routes.resumes as routes

    class FlakyStorage:
        async def delete(self, key):
            raise OSError("storage backend down")

    monkeypatch.setattr(routes, "get_storage", lambda: FlakyStorage())
    resp = client.delete(f"/api/resumes/{resume_id}")
    assert resp.status_code == 204
    assert session.get(Resume, resume_id) is None


def test_delete_other_users_resume_is_404(client, session):
    other = User(email="o3@example.com", password_hash="x", display_name="O3")
    session.add(other)
    session.commit()
    r = Resume(
        user_id=other.id,
        title="nope",
        original_filename="n.pdf",
        file_key="k3",
        content_type=PDF_CONTENT_TYPE,
        file_size=1,
    )
    session.add(r)
    session.commit()
    session.refresh(r)
    resp = client.delete(f"/api/resumes/{r.id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------- export

def test_export_pdf_returns_pdf_bytes(client):
    body = _upload(
        client,
        data=make_pdf_bytes("Export Me\nPython"),
        filename="export.pdf",
        content_type=PDF_CONTENT_TYPE,
    ).json()
    resp = client.get(f"/api/resumes/{body['id']}/export.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    assert len(resp.content) > 500


def test_export_other_users_resume_is_404(client, session):
    other = User(email="o4@example.com", password_hash="x", display_name="O4")
    session.add(other)
    session.commit()
    r = Resume(
        user_id=other.id,
        title="x",
        original_filename="x.pdf",
        file_key="k4",
        content_type=PDF_CONTENT_TYPE,
        file_size=1,
    )
    session.add(r)
    session.commit()
    session.refresh(r)
    resp = client.get(f"/api/resumes/{r.id}/export.pdf")
    assert resp.status_code == 404
