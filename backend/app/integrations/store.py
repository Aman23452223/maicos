"""File-backed JSON store for connector data.

Used by the local / in-memory CRM, Email, and Calendar connectors so
the "real system was updated" property can be observed on disk and
survives a process restart. In production each connector swaps this
for a real provider SDK; the interface is identical.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Generic, TypeVar

T = TypeVar("T")


class JsonStore(Generic[T]):
    """Tiny thread-safe JSON-on-disk store keyed by string id."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._data: dict[str, T] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._data = {}
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._flush()

    def _flush(self) -> None:
        # Atomic write: write to a sibling temp file then rename.
        fd, tmp = tempfile.mkstemp(
            prefix=self.path.name + ".", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, default=str)
            os.replace(tmp, self.path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def get(self, key: str) -> T | None:
        with self._lock:
            return self._data.get(key)

    def all(self) -> list[T]:
        with self._lock:
            return list(self._data.values())

    def put(self, key: str, value: T) -> None:
        with self._lock:
            self._data[key] = value
            self._flush()

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)
            self._flush()

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._flush()


def stores_root() -> Path:
    return Path(os.environ.get("MAICOS_STORES_DIR", "./var/stores"))
