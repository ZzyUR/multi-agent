"""Virtual File System — Agent 的"外部硬盘"。

每个 run 拥有独立目录：
  virtual_fs/{run_id}/
    ├── plan.md              # Lead 写的研究计划
    ├── sources.jsonl        # 所有来源（append-only）
    ├── report_draft.md      # 最终报告草稿
    └── findings/
        └── {task_id}.md    # 各 Worker 的完整发现（各自隔离）

关键设计：子 Agent 把大块原文写文件、只回摘要给 Lead。
这是 Lead 上下文不爆炸的根本保证。
"""

from __future__ import annotations

import json
from pathlib import Path

from deepresearch.common.logging import get_logger
from deepresearch.schemas.models import Source

log = get_logger("filesystem.vfs")


class VirtualFS:
    def __init__(self, root: str, run_id: str) -> None:
        self.run_id = run_id
        self.run_root = Path(root) / run_id
        (self.run_root / "findings").mkdir(parents=True, exist_ok=True)
        log.info("vfs_ready", path=str(self.run_root))

    # ── Write / Read ──────────────────────────────────────────────────────────

    def write(self, rel_path: str, content: str) -> str:
        """Write content to a path relative to this run's root. Returns absolute path."""
        full = self.run_root / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        log.info("vfs_write", path=rel_path, chars=len(content))
        return str(full)

    def read(self, rel_path: str) -> str:
        full = self.run_root / rel_path
        return full.read_text(encoding="utf-8") if full.exists() else ""

    def exists(self, rel_path: str) -> bool:
        return (self.run_root / rel_path).exists()

    # ── Sources (append-only) ─────────────────────────────────────────────────

    def append_source(self, source: Source) -> None:
        path = self.run_root / "sources.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(source.model_dump_json() + "\n")

    def load_sources(self) -> list[Source]:
        path = self.run_root / "sources.jsonl"
        if not path.exists():
            return []
        sources = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    sources.append(Source.model_validate_json(line))
                except Exception:
                    pass
        return sources

    # ── Worker finding path ───────────────────────────────────────────────────

    def finding_path(self, task_id: str) -> str:
        """Relative path for a worker's findings file."""
        return f"findings/{task_id}.md"

    def write_finding(self, task_id: str, content: str) -> str:
        """Write worker findings. Returns the relative path."""
        rel = self.finding_path(task_id)
        self.write(rel, content)
        return rel
