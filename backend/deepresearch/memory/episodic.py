"""Episodic Memory — append-only JSONL 事件日志（可重放）。

记录：每次搜索、抓取、派发、发现的完整时序事件。
特性：
  - append-only（不修改历史）
  - 可重放（按 run_id 过滤）
  - 联动去重：seen_urls 集合防止重复抓取
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from deepresearch.common.logging import get_logger

log = get_logger("memory.episodic")


class EpisodicMemory:
    def __init__(self, run_id: str, episodic_dir: str = "./traces") -> None:
        self.run_id = run_id
        self._path = Path(episodic_dir) / f"{run_id}.episodic.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._seen_urls: set[str] = set()

    # ── Record ────────────────────────────────────────────────────────────────

    def record(self, event_type: str, **data: Any) -> None:
        entry = {
            "run_id": self.run_id,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            **data,
        }
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def record_fetch(self, url: str, chars: int, task_id: str) -> None:
        self._seen_urls.add(url)
        self.record("fetch", url=url, chars=chars, task_id=task_id)

    def record_search(self, query: str, result_count: int, task_id: str) -> None:
        self.record("search", query=query, result_count=result_count, task_id=task_id)

    def record_finding(self, task_id: str, summary: str, source_count: int) -> None:
        self.record("finding", task_id=task_id, summary=summary[:200], source_count=source_count)

    # ── Dedup ─────────────────────────────────────────────────────────────────

    def has_seen(self, url: str) -> bool:
        return url in self._seen_urls

    def mark_seen(self, url: str) -> None:
        self._seen_urls.add(url)

    def seen_urls(self) -> set[str]:
        return set(self._seen_urls)

    # ── Replay ────────────────────────────────────────────────────────────────

    def replay(self) -> list[dict]:
        if not self._path.exists():
            return []
        events = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return events
