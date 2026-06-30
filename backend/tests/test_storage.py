"""Tests for the file storage abstraction (design.md §9)."""

import uuid

import pytest

from app.core.storage import LocalStorage, get_storage


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(base_path=str(tmp_path))


async def test_save_and_load_roundtrips(storage):
    key = f"{uuid.uuid4()}/{uuid.uuid4()}.pdf"
    data = b"%PDF-1.4 hello"
    await storage.save(key, data, "application/pdf")
    assert await storage.load(key) == data


async def test_delete_removes_file(storage):
    key = f"{uuid.uuid4()}/{uuid.uuid4()}.txt"
    await storage.save(key, b"bye", "text/plain")
    await storage.delete(key)
    with pytest.raises(FileNotFoundError):
        await storage.load(key)


async def test_delete_missing_key_is_idempotent(storage):
    # Deleting a key that does not exist must not raise.
    await storage.delete("nope/missing.bin")


async def test_save_creates_nested_directories(storage, tmp_path):
    user = uuid.uuid4()
    key = f"{user}/{uuid.uuid4()}.docx"
    await storage.save(key, b"data", "application/octet-stream")
    assert (tmp_path / str(user)).is_dir()


async def test_key_traversal_is_rejected(storage):
    # Opaque keys only — a key escaping the base path must be refused.
    with pytest.raises(ValueError):
        await storage.save("../escape.txt", b"x", "text/plain")


def test_get_storage_returns_local_storage_by_default():
    assert isinstance(get_storage(), LocalStorage)
