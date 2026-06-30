"""File storage abstraction (design.md §9).

Keys are opaque (``{user_id}/{uuid}{ext}``) and files are never served by raw
path. The MVP backend writes to a local directory (a mounted Docker volume in
production); the ``StorageBackend`` ABC keeps an S3/R2 backend a drop-in swap.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings


class StorageBackend(ABC):
    """Async object storage keyed by an opaque string."""

    @abstractmethod
    async def save(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    async def load(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...


class LocalStorage(StorageBackend):
    """Stores blobs as files under ``base_path``.

    ``content_type`` is accepted for interface parity with object stores (which
    persist it as metadata) but is not needed on a plain filesystem — the DB row
    is the source of truth for a resume's content type.
    """

    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path).resolve()

    def _resolve(self, key: str) -> Path:
        # Reject keys that try to escape the base directory (path traversal).
        target = (self._base / key).resolve()
        if target != self._base and self._base not in target.parents:
            raise ValueError(f"invalid storage key: {key!r}")
        return target

    async def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def load(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    async def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)


def get_storage() -> StorageBackend:
    """Return the configured storage backend (local only for the MVP)."""
    return LocalStorage(base_path=get_settings().file_storage_path)
