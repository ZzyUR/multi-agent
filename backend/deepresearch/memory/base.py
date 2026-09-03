"""MemoryService — CoALA 四类记忆的统一门面。

接口：
  memory.remember(key, value, type="working"|"episodic"|"semantic")
  memory.recall(query, type="semantic")
  memory.consolidate()   → 从 working/episodic 蒸馏到 semantic

CoALA 框架对照：
  Working   → 当前 run 内存变量
  Episodic  → 研究事件时序日志（append-only JSONL）
  Semantic  → 蒸馏关键事实（可检索）
  Procedural→ 研究策略规范（配置文件，只读）
"""

from __future__ import annotations

from typing import Any

from deepresearch.memory.episodic import EpisodicMemory
from deepresearch.memory.procedural import ProceduralMemory
from deepresearch.memory.semantic import SemanticMemory
from deepresearch.memory.working import WorkingMemory


class MemoryService:
    def __init__(self, run_id: str, traces_dir: str = "./traces") -> None:
        self.run_id = run_id
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory(run_id, episodic_dir=traces_dir)
        self.semantic = SemanticMemory(run_id, semantic_dir=traces_dir)
        self.procedural = ProceduralMemory()

    # ── Unified interface ─────────────────────────────────────────────────────

    def remember(
        self,
        key: str,
        value: Any,
        *,
        memory_type: str = "working",
        source: str = "",
    ) -> None:
        if memory_type == "working":
            self.working.set(key, value)
        elif memory_type == "semantic":
            fact = f"{key}: {value}" if key else str(value)
            self.semantic.remember(fact, source=source)
        elif memory_type == "episodic":
            self.episodic.record(key, **({} if not isinstance(value, dict) else value))

    def recall(self, query: str, *, memory_type: str = "semantic") -> list[str]:
        if memory_type == "semantic":
            return self.semantic.recall(query)
        if memory_type == "working":
            store = self.working.all()
            q = query.lower()
            return [f"{k}: {v}" for k, v in store.items() if q in k.lower() or q in str(v).lower()]
        return []

    def consolidate(self) -> int:
        """Distil episodic events into semantic facts. Returns facts added."""
        events = self.episodic.replay()
        added = 0
        for ev in events:
            if ev.get("event_type") == "finding":
                summary = ev.get("summary", "")
                if summary and summary not in self.semantic.all_facts():
                    self.semantic.remember(summary, source=f"episodic/{ev.get('task_id','')}")
                    added += 1
        return added

    # ── Dedup helpers (delegate to episodic) ──────────────────────────────────

    def has_seen_url(self, url: str) -> bool:
        return self.episodic.has_seen(url)

    def mark_url_seen(self, url: str) -> None:
        self.episodic.mark_seen(url)
