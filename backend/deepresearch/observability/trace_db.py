"""SQLite-backed trace persistence (P6 6.2).

Provides an efficient, queryable store for trace events alongside the JSONL
append-only log.  Uses stdlib sqlite3 — no external service required; plug
in the configured MySQL DSN later by swapping the connection string.

Schema (single table, no ORM):
  trace_events(id, run_id, event_id, event_type, agent_id,
               timestamp, duration_ms, data_json, tags_json)

Usage:
    db = TraceDB("./data/traces/traces.db")
    db.insert(event)
    events = db.load_run("run-abc")
    runs   = db.list_runs()
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from deepresearch.common.logging import get_logger
from deepresearch.schemas.models import TraceEvent

log = get_logger("observability.trace_db")

_DDL = """
CREATE TABLE IF NOT EXISTS trace_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT    NOT NULL,
    event_id    TEXT    UNIQUE NOT NULL,
    event_type  TEXT    NOT NULL,
    agent_id    TEXT,
    timestamp   TEXT    NOT NULL,
    duration_ms REAL,
    data_json   TEXT    NOT NULL DEFAULT '{}',
    tags_json   TEXT    NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_run_id    ON trace_events(run_id);
CREATE INDEX IF NOT EXISTS idx_event_type ON trace_events(event_type);
"""


class TraceDB:
    """SQLite trace store — thread-safe singleton per DB path."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(_DDL)
        log.info("trace_db_ready", path=self._path)

    # ── Write ──────────────────────────────────────────────────────────────────

    def insert(self, event: TraceEvent) -> None:
        """Persist one trace event.  Silently ignores duplicate event_id."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO trace_events
                    (run_id, event_id, event_type, agent_id,
                     timestamp, duration_ms, data_json, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.run_id,
                    event.event_id,
                    event.event_type,
                    event.agent_id,
                    event.timestamp.isoformat(),
                    event.duration_ms,
                    json.dumps(event.data, ensure_ascii=False),
                    json.dumps(event.tags or [], ensure_ascii=False),
                ),
            )

    def insert_many(self, events: list[TraceEvent]) -> None:
        """Batch insert — more efficient than calling insert() in a loop."""
        rows = [
            (
                ev.run_id, ev.event_id, ev.event_type, ev.agent_id,
                ev.timestamp.isoformat(), ev.duration_ms,
                json.dumps(ev.data, ensure_ascii=False),
                json.dumps(ev.tags or [], ensure_ascii=False),
            )
            for ev in events
        ]
        with self._conn() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO trace_events
                    (run_id, event_id, event_type, agent_id,
                     timestamp, duration_ms, data_json, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    # ── Read ───────────────────────────────────────────────────────────────────

    def load_run(self, run_id: str) -> list[dict[str, Any]]:
        """Return all events for a run, ordered by timestamp."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT run_id, event_id, event_type, agent_id,
                       timestamp, duration_ms, data_json, tags_json
                FROM trace_events
                WHERE run_id = ?
                ORDER BY timestamp ASC
                """,
                (run_id,),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def list_runs(self) -> list[str]:
        """Return distinct run_ids sorted alphabetically."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT run_id FROM trace_events ORDER BY run_id"
            ).fetchall()
        return [r[0] for r in rows]

    def count_events(self, run_id: str) -> int:
        """Return the number of events stored for a given run_id."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM trace_events WHERE run_id = ?", (run_id,)
            ).fetchone()
        return row[0] if row else 0

    def run_summary(self, run_id: str) -> dict[str, Any]:
        """Return a lightweight summary (first+last event, event type counts)."""
        events = self.load_run(run_id)
        if not events:
            return {"run_id": run_id, "event_count": 0}
        type_counts: dict[str, int] = {}
        for ev in events:
            t = ev["event_type"]
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "run_id": run_id,
            "event_count": len(events),
            "first_ts": events[0]["timestamp"],
            "last_ts": events[-1]["timestamp"],
            "event_type_counts": type_counts,
        }

    # ── Internal ───────────────────────────────────────────────────────────────

    @contextmanager
    def _conn(self):
        """Open a connection that commits on success and always closes.

        Returning a raw ``sqlite3.Connection`` leaks it: sqlite3's own context
        manager (__exit__) commits on success but never closes the connection.
        On Windows the leftover open handle keeps the DB file locked, so any
        later attempt to delete the file (e.g. pytest reclaiming its tmp_path)
        fails with ``PermissionError: [WinError 32]``. Wrapping with an explicit
        close fixes both the leak and the Windows teardown failure.
        """
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


# ── Factory ────────────────────────────────────────────────────────────────────

_db_instances: dict[str, TraceDB] = {}


def get_trace_db(db_path: str | Path | None = None) -> TraceDB:
    """Return (or create) a TraceDB for the given path."""
    from deepresearch.config.settings import get_settings
    if db_path is None:
        cfg = get_settings()
        db_path = str(Path(cfg.trace_dir) / "traces.db")
    key = str(db_path)
    if key not in _db_instances:
        _db_instances[key] = TraceDB(db_path)
    return _db_instances[key]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id":      row["run_id"],
        "event_id":    row["event_id"],
        "event_type":  row["event_type"],
        "agent_id":    row["agent_id"],
        "timestamp":   row["timestamp"],
        "duration_ms": row["duration_ms"],
        "data":        json.loads(row["data_json"]),
        "tags":        json.loads(row["tags_json"]),
    }
