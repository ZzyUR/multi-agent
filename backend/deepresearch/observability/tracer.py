"""Trace bottom layer — emit structured TraceEvents to JSONL + stdout.

Every significant action in the harness calls tracer.emit().
Output goes to:
  1. JSONL file at {TRACE_DIR}/{run_id}.jsonl  (always)
  2. Rich console (when TRACE_STDOUT=true)

Higher-level persistence to MySQL is wired in Phase 6.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from time import monotonic
from typing import Any, Generator

from deepresearch.config.settings import get_settings
from deepresearch.schemas.models import EventType, TraceEvent


class Tracer:
    def __init__(
        self,
        trace_dir: str,
        stdout: bool = True,
        db=None,   # TraceDB | None — optional SQLite persistence (P6)
    ) -> None:
        self._dir = Path(trace_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._stdout = stdout
        self._db = db

    # ── Public API ─────────────────────────────────────────────────────────────

    def emit(
        self,
        event_type: str | EventType,
        run_id: str,
        *,
        agent_id: str | None = None,
        parent_event_id: str | None = None,
        duration_ms: float | None = None,
        tags: list[str] | None = None,
        **data: Any,
    ) -> TraceEvent:
        event = TraceEvent(
            run_id=run_id,
            agent_id=agent_id,
            parent_event_id=parent_event_id,
            event_type=str(event_type),
            duration_ms=duration_ms,
            tags=tags or [],
            data=data,
        )
        self._write(event)
        return event

    @contextmanager
    def span(
        self,
        event_type: str | EventType,
        run_id: str,
        *,
        agent_id: str | None = None,
        parent_event_id: str | None = None,
        tags: list[str] | None = None,
        **data: Any,
    ) -> Generator[TraceEvent, None, None]:
        """Context manager that emits a single event with wall-clock duration."""
        start = monotonic()
        event = TraceEvent(
            run_id=run_id,
            agent_id=agent_id,
            parent_event_id=parent_event_id,
            event_type=str(event_type),
            tags=tags or [],
            data=data,
        )
        try:
            yield event
        finally:
            event.duration_ms = (monotonic() - start) * 1000
            self._write(event)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _write(self, event: TraceEvent) -> None:
        line = event.model_dump_json()
        # Append to per-run JSONL file
        jsonl_path = self._dir / f"{event.run_id}.jsonl"
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

        # P6: also persist to SQLite when a TraceDB is attached
        if self._db is not None:
            try:
                self._db.insert(event)
            except Exception:
                pass   # never let DB errors break the trace path

        if self._stdout:
            ts = event.timestamp.strftime("%H:%M:%S")
            agent = f"[{event.agent_id}] " if event.agent_id else ""
            dur = f" ({event.duration_ms:.0f}ms)" if event.duration_ms else ""
            print(
                f"[TRACE {ts}] {agent}{event.event_type}{dur}  {_compact(event.data)}",
                file=sys.stderr,
            )


def _compact(data: dict[str, Any]) -> str:
    """Short single-line summary of event data for console output."""
    if not data:
        return ""
    try:
        s = json.dumps(data, ensure_ascii=False)
        return s[:120] + "…" if len(s) > 120 else s
    except Exception:
        return str(data)[:120]


@lru_cache(maxsize=1)
def get_tracer() -> Tracer:
    cfg = get_settings()
    return Tracer(trace_dir=cfg.trace_dir, stdout=cfg.trace_stdout)
