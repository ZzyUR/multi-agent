"""Checkpoint state store — save/resume run state.

Storage: JSON files in {checkpoint_dir}/{run_id}/ directory.
Each checkpoint is an atomic file write (write-then-rename).

Checkpoint events:
  • "plan"    — immediately after planning, before dispatch
  • "worker"  — after each worker completes (incremental)
  • "synth"   — after synthesis (before citation)
  • "done"    — after citation + final report

Resume strategy:
  load_latest(run_id) → returns the most recent checkpoint dict or None.
  The caller (LeadAgent) checks which stage was reached and skips forward.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from deepresearch.common.logging import get_logger

log = get_logger("checkpoint")

CHECKPOINT_DIR_DEFAULT = "./checkpoints"


@dataclass
class CheckpointData:
    run_id: str
    stage: str                        # "plan" | "worker" | "synth" | "done"
    question: str
    profile: str
    subtask_queries: list[str] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)   # serialised Finding dicts
    report: str = ""
    citation_report: dict = field(default_factory=dict)
    tokens_used: int = 0
    saved_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CheckpointData":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class CheckpointStore:
    """Filesystem-backed checkpoint store for a single run."""

    def __init__(self, run_id: str, checkpoint_dir: str = CHECKPOINT_DIR_DEFAULT) -> None:
        self.run_id = run_id
        self._dir = Path(checkpoint_dir) / run_id
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, data: CheckpointData) -> str:
        """Write checkpoint atomically. Returns path."""
        filename = f"{data.stage}_{int(data.saved_at * 1000)}.json"
        tmp = self._dir / (filename + ".tmp")
        final = self._dir / filename
        tmp.write_text(json.dumps(data.to_dict(), ensure_ascii=False, indent=2))
        tmp.rename(final)
        log.info("checkpoint_saved", run_id=self.run_id, stage=data.stage, path=str(final))
        return str(final)

    def load_latest(self) -> CheckpointData | None:
        """Return the most recent checkpoint for this run, or None."""
        files = sorted(self._dir.glob("*.json"))
        if not files:
            return None
        latest = files[-1]
        try:
            raw = json.loads(latest.read_text(encoding="utf-8"))
            cp = CheckpointData.from_dict(raw)
            log.info("checkpoint_loaded", run_id=self.run_id, stage=cp.stage, path=str(latest))
            return cp
        except Exception as exc:
            log.warning("checkpoint_load_failed", path=str(latest), error=str(exc))
            return None

    def list_checkpoints(self) -> list[str]:
        return [f.name for f in sorted(self._dir.glob("*.json"))]

    def clear(self) -> None:
        """Delete all checkpoints for this run (used after successful completion)."""
        for f in self._dir.glob("*.json"):
            f.unlink(missing_ok=True)
        log.info("checkpoints_cleared", run_id=self.run_id)


# ── Factory / global registry ─────────────────────────────────────────────────

_stores: dict[str, CheckpointStore] = {}


def get_checkpoint_store(
    run_id: str,
    checkpoint_dir: str = CHECKPOINT_DIR_DEFAULT,
) -> CheckpointStore:
    if run_id not in _stores:
        _stores[run_id] = CheckpointStore(run_id, checkpoint_dir)
    return _stores[run_id]
