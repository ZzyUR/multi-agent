"""Working Memory — 当前编排上下文（纯内存，生命周期 = 一次 run）。"""

from __future__ import annotations

from typing import Any


class WorkingMemory:
    """Key-value store for transient run-level state."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def all(self) -> dict[str, Any]:
        return dict(self._store)

    def clear(self) -> None:
        self._store.clear()
