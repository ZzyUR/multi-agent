"""Trace Reader — parse, aggregate, and replay JSONL traces.

Provides:
  TraceReader.load(run_id)     — parse all events for a run
  TraceReader.stats()          — aggregated metrics (tokens, latencies, tool calls)
  TraceReader.replay()         — print human-readable decision chain
  TraceReader.tool_success_rate() — per-tool success/failure ratios
  RunStats (dataclass)         — structured metrics for interview demos
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from deepresearch.common.logging import get_logger

log = get_logger("observability.trace_reader")


@dataclass
class ToolStats:
    name: str
    calls: int = 0
    successes: int = 0
    failures: int = 0
    total_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / max(self.calls, 1)

    @property
    def avg_latency_ms(self) -> float:
        return self.total_ms / max(self.calls, 1)


@dataclass
class RunStats:
    run_id: str
    question: str = ""
    profile: str = ""
    total_tokens: int = 0
    total_workers: int = 0
    total_findings: int = 0
    duration_ms: float = 0.0
    tool_stats: dict[str, ToolStats] = field(default_factory=dict)
    compaction_events: list[dict] = field(default_factory=list)
    citation_support_rate: float = -1.0  # -1 = not available
    cache_hit_rate: float = 0.0
    # Phase cost estimate (tokens × price per token)
    estimated_cost_usd: float = 0.0

    # qwen-plus pricing: input ~$0.0004/1K, output ~$0.0012/1K (approximate)
    _INPUT_PRICE_PER_K = 0.0004
    _OUTPUT_PRICE_PER_K = 0.0012

    def compute_cost(self) -> None:
        # Rough estimate: assume 70% input 30% output
        input_tokens = int(self.total_tokens * 0.7)
        output_tokens = self.total_tokens - input_tokens
        self.estimated_cost_usd = (
            input_tokens / 1000 * self._INPUT_PRICE_PER_K
            + output_tokens / 1000 * self._OUTPUT_PRICE_PER_K
        )

    def summary_lines(self) -> list[str]:
        lines = [
            f"Run ID     : {self.run_id}",
            f"Question   : {self.question[:80]}",
            f"Profile    : {self.profile}",
            f"Duration   : {self.duration_ms/1000:.1f}s",
            f"Workers    : {self.total_workers}",
            f"Tokens     : {self.total_tokens:,}",
            f"Est. cost  : ${self.estimated_cost_usd:.4f} USD",
            f"Cache hits : {self.cache_hit_rate:.1%}",
        ]
        if self.citation_support_rate >= 0:
            lines.append(f"Citation   : {self.citation_support_rate:.0%} supported")
        if self.compaction_events:
            all_layers = [l for e in self.compaction_events for l in e.get("layers", [])]
            lines.append(f"Compaction : {len(self.compaction_events)} events → {all_layers}")
        lines.append("")
        lines.append("Tool success rates:")
        for ts in sorted(self.tool_stats.values(), key=lambda x: x.name):
            lines.append(
                f"  {ts.name:20s}  calls={ts.calls}  "
                f"success={ts.success_rate:.0%}  avg={ts.avg_latency_ms:.0f}ms"
            )
        return lines


class TraceReader:
    """Parse and analyse a JSONL trace file."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events

    @classmethod
    def load(cls, run_id: str, trace_dir: str = "./traces") -> "TraceReader":
        path = Path(trace_dir) / f"{run_id}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"Trace not found: {path}")
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        log.info("trace_loaded", run_id=run_id, events=len(events))
        return cls(events)

    def stats(self) -> RunStats:
        run_id = ""
        question = ""
        profile = ""
        total_tokens = 0
        total_workers = 0
        total_findings = 0
        start_ts: float | None = None
        end_ts: float | None = None
        citation_rate = -1.0
        cache_hit_rate = 0.0
        tool_stats: dict[str, ToolStats] = {}
        compaction_events: list[dict] = []

        _tool_call_time: dict[str, float] = {}

        def _ts_ms(ev: dict) -> float:
            raw = ev.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(raw)
                return dt.timestamp() * 1000
            except Exception:
                return 0.0

        for ev in self._events:
            etype = ev.get("event_type", "")
            data = ev.get("data", {})
            ts = _ts_ms(ev)

            if etype == "run_start":
                run_id = ev.get("run_id", "")
                question = data.get("question", "")
                profile = data.get("profile", "")
                start_ts = ts

            elif etype == "run_end":
                end_ts = ts
                total_tokens = data.get("tokens_used", total_tokens)
                total_workers = data.get("total_workers", total_workers)
                citation_rate = data.get("citation_support_rate", -1.0)
                cache_hit_rate = data.get("cache_hit_rate", 0.0)

            elif etype == "task_done":
                total_findings += 1

            elif etype == "tool_call":
                tool = data.get("tool", "unknown")
                # Use a per-tool call counter as synthetic call_id
                call_key = f"{tool}_{tool_stats.get(tool, ToolStats(name=tool)).calls}"
                _tool_call_time[call_key] = ts
                if tool not in tool_stats:
                    tool_stats[tool] = ToolStats(name=tool)
                tool_stats[tool].calls += 1

            elif etype == "tool_result":
                tool = data.get("tool", "unknown")
                success = data.get("success", True)
                # Try to match the most recent open call for this tool
                matched_key = None
                for k in list(_tool_call_time.keys()):
                    if k.startswith(f"{tool}_"):
                        matched_key = k
                        break
                elapsed = 0.0
                if matched_key:
                    elapsed = ts - _tool_call_time.pop(matched_key)
                if tool not in tool_stats:
                    tool_stats[tool] = ToolStats(name=tool)
                if success:
                    tool_stats[tool].successes += 1
                else:
                    tool_stats[tool].failures += 1
                tool_stats[tool].total_ms += elapsed

            elif etype == "context_compress":
                compaction_events.append(data)

        duration_ms = (end_ts - start_ts) if (start_ts and end_ts) else 0.0
        rs = RunStats(
            run_id=run_id,
            question=question,
            profile=profile,
            total_tokens=total_tokens,
            total_workers=total_workers,
            total_findings=total_findings,
            duration_ms=duration_ms,
            tool_stats=tool_stats,
            compaction_events=compaction_events,
            citation_support_rate=citation_rate,
            cache_hit_rate=cache_hit_rate,
        )
        rs.compute_cost()
        return rs

    def replay(self, *, verbose: bool = False) -> str:
        """Return a human-readable decision chain string."""
        lines: list[str] = ["=== TRACE REPLAY ===\n"]

        # Pre-compute start time for relative timestamps
        start_abs: float = 0.0
        for ev in self._events:
            if ev.get("event_type") == "run_start":
                try:
                    start_abs = datetime.fromisoformat(ev["timestamp"]).timestamp() * 1000
                except Exception:
                    pass
                break

        for ev in self._events:
            etype = ev.get("event_type", "")
            data = ev.get("data", {})
            try:
                ev_abs = datetime.fromisoformat(ev.get("timestamp", "")).timestamp() * 1000
            except Exception:
                ev_abs = start_abs
            ts = f"{(ev_abs - start_abs)/1000:.3f}s"

            if etype == "run_start":
                lines.append(f"[{ts}] RUN_START  q={data.get('question','')[:60]}")
            elif etype == "plan_done":
                tasks = data.get("subtasks", [])
                lines.append(f"[{ts}] PLAN_DONE  {len(tasks)} subtasks")
                for i, t in enumerate(tasks, 1):
                    lines.append(f"          {i}. {t[:70]}")
            elif etype == "task_dispatch":
                lines.append(f"[{ts}] DISPATCH   {data.get('count',0)} workers")
            elif etype == "task_start":
                agent = ev.get("agent_id") or data.get("agent_id", "")
                lines.append(f"[{ts}] WORKER_START  {agent}")
            elif etype == "tool_call":
                args_str = str(data.get("args", {}))[:80]
                lines.append(f"[{ts}]   → TOOL {data.get('tool','')}({args_str})")
            elif etype == "tool_result":
                ok = "✓" if data.get("success") else "✗"
                lines.append(f"[{ts}]   ← {ok} {data.get('tool','')} ({data.get('duration_ms',0):.0f}ms)")
            elif etype == "context_compress":
                lines.append(f"[{ts}] COMPACT  layers={data.get('layers',[])}  saved={data.get('saved',0)} tokens")
            elif etype == "task_done":
                agent = ev.get("agent_id") or data.get("agent_id", "")
                lines.append(f"[{ts}] WORKER_DONE  {agent}  tokens={data.get('tokens',0)}")
            elif etype == "synthesize":
                lines.append(f"[{ts}] SYNTHESIZE")
            elif etype == "citation_check":
                stage = data.get("stage", "")
                if stage == "done":
                    lines.append(
                        f"[{ts}] CITE_DONE  "
                        f"support={data.get('support_rate',0):.0%}  "
                        f"unsupported={data.get('total',0)-data.get('supported',0)}"
                    )
            elif etype == "run_end":
                lines.append(
                    f"[{ts}] RUN_END  "
                    f"workers={data.get('total_workers',0)}  "
                    f"tokens={data.get('tokens_used',0):,}  "
                    f"cache={data.get('cache_hit_rate',0):.1%}"
                )
        return "\n".join(lines)

    def tool_success_rate(self) -> dict[str, float]:
        """Returns {tool_name: success_rate}."""
        s = self.stats()
        return {name: ts.success_rate for name, ts in s.tool_stats.items()}
