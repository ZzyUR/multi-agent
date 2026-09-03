"""Semantic Memory — 蒸馏后的关键事实与中间结论。

存储：VFS 文件 + Chroma（复用 retriever 的 collection）。
用途：跨 Worker 共享已验证的关键事实，避免重复推导。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deepresearch.common.logging import get_logger

log = get_logger("memory.semantic")


class SemanticMemory:
    """Persistent key-fact store, backed by a simple JSONL file."""

    def __init__(self, run_id: str, semantic_dir: str = "./traces") -> None:
        self.run_id = run_id
        self._path = Path(semantic_dir) / f"{run_id}.semantic.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._facts: list[dict[str, Any]] = self._load()

    def remember(self, fact: str, source: str = "", confidence: float = 1.0) -> None:
        entry = {
            "fact": fact,
            "source": source,
            "confidence": confidence,
        }
        self._facts.append(entry)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        log.info("semantic_store", fact=fact[:60])

    def recall(self, keyword: str, top_k: int = 5) -> list[str]:
        """Simple keyword-based recall (Chroma semantic recall added in P6)."""
        kw = keyword.lower()
        scored = [
            (f["fact"], sum(1 for w in kw.split() if w in f["fact"].lower()))
            for f in self._facts
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [f for f, score in scored[:top_k] if score > 0]

    def all_facts(self) -> list[str]:
        return [f["fact"] for f in self._facts]

    def _load(self) -> list[dict]:
        if not self._path.exists():
            return []
        facts = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    facts.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return facts
