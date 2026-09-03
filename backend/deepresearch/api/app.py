"""FastAPI application — Phase 7 backend.

Endpoints:
  POST /api/research          — start a new research run (returns run_id)
  GET  /api/research/{run_id}/stream — SSE stream of trace events
  GET  /api/research/{run_id}/report — final report (Markdown)
  GET  /api/research/{run_id}/stats  — run statistics (P6 TraceReader)
  GET  /api/research/history         — list of completed runs
  GET  /api/health                   — health check

SSE event types sent to client:
  {type: "trace",   data: {event_type, agent_id, data, timestamp}}
  {type: "report",  data: {content: "# Markdown..."}}
  {type: "done",    data: {run_id, tokens_used, cache_hit_rate, ...}}
  {type: "error",   data: {message}}
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from deepresearch.common.logging import configure_logging, get_logger
from deepresearch.config.settings import get_settings
from deepresearch.observability.trace_reader import TraceReader

configure_logging()
log = get_logger("api")

app = FastAPI(title="DeepResearch Agent API", version="7.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory run registry ────────────────────────────────────────────────────
# Maps run_id → asyncio.Queue for SSE events
_run_queues: dict[str, asyncio.Queue] = {}
_run_reports: dict[str, str] = {}
_run_meta: dict[str, dict] = {}


# ── Request / Response models ─────────────────────────────────────────────────

class StartResearchRequest(BaseModel):
    question: str
    profile: str = "standard"
    mock: bool = False


class StartResearchResponse(BaseModel):
    run_id: str
    message: str = "Research started"


class ClarifyRequest(BaseModel):
    question: str


# ── Patched Tracer that also enqueues SSE events ──────────────────────────────

class SSETracer:
    """Wraps the real Tracer and forwards events to an asyncio Queue."""

    def __init__(self, real_tracer, run_id: str, queue: asyncio.Queue) -> None:
        self._real = real_tracer
        self._run_id = run_id
        self._queue = queue

    def emit(self, event_type, run_id, *, agent_id=None, **data):
        ev = self._real.emit(event_type, run_id, agent_id=agent_id, **data)
        # Push to SSE queue (non-blocking)
        try:
            self._queue.put_nowait({
                "type": "trace",
                "data": {
                    "event_type": str(event_type),
                    "agent_id": agent_id,
                    "data": data,
                    "timestamp": ev.timestamp.isoformat(),
                },
            })
        except asyncio.QueueFull:
            pass
        return ev

    def span(self, *args, **kwargs):
        return self._real.span(*args, **kwargs)

    # Proxy remaining attributes
    def __getattr__(self, name):
        return getattr(self._real, name)


# ── Background research task ──────────────────────────────────────────────────

async def _run_research(run_id: str, question: str, profile: str, mock: bool) -> None:
    queue = _run_queues[run_id]

    try:
        from deepresearch.observability.tracer import get_tracer
        from deepresearch.orchestrator.lead_agent import LeadAgent

        real_tracer = get_tracer()
        sse_tracer = SSETracer(real_tracer, run_id, queue)

        if mock:
            # Bypass lru_cache — create fresh mock instances directly
            from deepresearch.model_client import MockModelClient
            from deepresearch.rag.web_search import MockSearch, get_search_backend
            get_search_backend.cache_clear()
            import os
            os.environ["USE_MOCK_SEARCH"] = "true"
            model = MockModelClient()
        else:
            from deepresearch.model_client import get_model_client
            model = get_model_client()
        lead = LeadAgent(model_client=model, tracer=sse_tracer, profile=profile)

        run, report = await lead.run(question, run_id=run_id)
        _run_reports[run_id] = report

        cache_hit_rate = getattr(model, "cache_hit_rate", 0.0)
        meta = {
            "run_id": run_id,
            "tokens_used": run.tokens_used,
            "workers": run.total_workers_spawned,
            "cache_hit_rate": cache_hit_rate,
        }
        _run_meta[run_id] = meta

        queue.put_nowait({"type": "report", "data": {"content": report}})
        queue.put_nowait({"type": "done", "data": meta})

    except Exception as exc:
        log.error("research_error", run_id=run_id, error=str(exc))
        queue.put_nowait({"type": "error", "data": {"message": str(exc)}})
    finally:
        # Sentinel to close the SSE stream
        queue.put_nowait(None)


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/research", response_model=StartResearchResponse)
async def start_research(req: StartResearchRequest) -> StartResearchResponse:
    run_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    _run_queues[run_id] = queue

    # Launch research in background (non-blocking)
    asyncio.create_task(_run_research(run_id, req.question, req.profile, req.mock))

    log.info("research_started", run_id=run_id, question=req.question[:60])
    return StartResearchResponse(run_id=run_id)


@app.get("/api/research/{run_id}/stream")
async def stream_research(run_id: str) -> EventSourceResponse:
    if run_id not in _run_queues:
        raise HTTPException(status_code=404, detail="Run not found")

    queue = _run_queues[run_id]

    async def event_generator() -> AsyncIterator[dict]:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield {
                "event": item["type"],
                "data": json.dumps(item["data"], ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@app.get("/api/research/{run_id}/report")
async def get_report(run_id: str) -> JSONResponse:
    report = _run_reports.get(run_id)
    if report is None:
        # 回退：从 VFS 磁盘读持久化报告（backend 重启后内存丢失，但文件仍在）
        cfg = get_settings()
        run_dir = Path(cfg.virtual_fs_root) / run_id
        for fname in ("report.html", "report_final.md", "report_draft.md"):
            fpath = run_dir / fname
            if fpath.exists():
                report = fpath.read_text(encoding="utf-8")
                break
    if report is None:
        raise HTTPException(status_code=404, detail="Report not yet available")
    return JSONResponse({"run_id": run_id, "content": report})


@app.get("/api/research/{run_id}/stats")
async def get_stats(run_id: str) -> JSONResponse:
    cfg = get_settings()
    try:
        reader = TraceReader.load(run_id, trace_dir=cfg.trace_dir)
        stats = reader.stats()
        return JSONResponse({
            "run_id": run_id,
            "question": stats.question,
            "profile": stats.profile,
            "duration_s": stats.duration_ms / 1000,
            "tokens": stats.total_tokens,
            "estimated_cost_usd": stats.estimated_cost_usd,
            "cache_hit_rate": stats.cache_hit_rate,
            "citation_support_rate": stats.citation_support_rate,
            "compaction_events": len(stats.compaction_events),
            "tool_stats": {
                name: {
                    "calls": ts.calls,
                    "success_rate": ts.success_rate,
                    "avg_latency_ms": ts.avg_latency_ms,
                }
                for name, ts in stats.tool_stats.items()
            },
        })
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Trace not found")


@app.get("/api/research/{run_id}/replay")
async def replay_trace(run_id: str) -> JSONResponse:
    """Return a human-readable decision-chain replay string (P6 6.3)."""
    cfg = get_settings()
    try:
        reader = TraceReader.load(run_id, trace_dir=cfg.trace_dir)
        return JSONResponse({"run_id": run_id, "replay": reader.replay()})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Trace not found")


# ── HITL intervention endpoints (P5) ─────────────────────────────────────────

class HITLRespondRequest(BaseModel):
    value: str


@app.get("/api/research/{run_id}/hitl/pending")
async def hitl_get_pending(run_id: str) -> JSONResponse:
    """Return the current pending HITL intervention prompt, if any."""
    from deepresearch.orchestrator.hitl import get_hitl_broker
    broker = get_hitl_broker()
    pending = broker.get_pending(run_id)
    return JSONResponse({"run_id": run_id, "pending": pending})


@app.post("/api/research/{run_id}/hitl/respond")
async def hitl_respond(run_id: str, req: HITLRespondRequest) -> JSONResponse:
    """Deliver a human response to a waiting intervention point."""
    from deepresearch.orchestrator.hitl import get_hitl_broker
    broker = get_hitl_broker()
    ok = broker.respond(run_id, req.value)
    return JSONResponse({"run_id": run_id, "delivered": ok})


@app.post("/api/research/{run_id}/hitl/abort")
async def hitl_abort(run_id: str) -> JSONResponse:
    """Signal a running research to stop after the current dispatch round."""
    from deepresearch.orchestrator.hitl import get_hitl_broker
    broker = get_hitl_broker()
    broker.signal_abort(run_id)
    return JSONResponse({"run_id": run_id, "aborted": True})


@app.get("/api/research/history")
async def list_history() -> JSONResponse:
    cfg = get_settings()
    trace_dir = Path(cfg.trace_dir)
    runs = []
    for f in sorted(trace_dir.glob("*.jsonl")):
        if "episodic" in f.name or "semantic" in f.name:
            continue
        run_id = f.stem
        try:
            reader = TraceReader.load(run_id, trace_dir=cfg.trace_dir)
            s = reader.stats()
            runs.append({
                "run_id": run_id,
                "question": s.question[:80],
                "profile": s.profile,
                "tokens": s.total_tokens,
                "duration_s": s.duration_ms / 1000,
                "estimated_cost_usd": s.estimated_cost_usd,
            })
        except Exception:
            runs.append({"run_id": run_id})
    return JSONResponse({"runs": runs})


_CLARIFY_SYSTEM = """用户想研究：「{topic}」。
在开始深度研究前，请针对这个主题**特有的歧义点**生成澄清问题，帮助 Agent 确定研究边界。

要求：
- 问题必须针对「{topic}」本身，不要问"研究深度""时间范围"这类通用系统参数
- 明确的主题生成 2 个问题，宽泛/模糊的主题生成 3 个
- 每个问题给 3~4 个互斥选项
- 每个问题附一句"为什么问这个"（reason，≤20字）
- 若问题适合多选（如关注哪些维度），把 multi 设为 true

只输出 JSON，不要任何其他文字：
{{"clarifications":[{{"question":"...","reason":"...","multi":false,"options":["选项A","选项B","选项C"]}}]}}"""


@app.post("/api/clarify")
async def clarify(req: ClarifyRequest) -> JSONResponse:
    """ReAct 第一步：Agent 读取主题，动态生成主题专属的澄清问题。"""
    import re
    from deepresearch.model_client import get_model_client
    from deepresearch.schemas.models import Message

    model = get_model_client()
    messages = [
        Message(role="system", content=_CLARIFY_SYSTEM.format(topic=req.question[:200])),
        Message(role="user", content="只输出 JSON。"),
    ]
    try:
        text, _, _ = await model.chat(messages, max_tokens=1024)
    except Exception as exc:
        log.warning("clarify_failed", error=str(exc))
        return JSONResponse({"clarifications": []})

    clar = []
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if m:
        try:
            clar = json.loads(m.group()).get("clarifications", [])
        except json.JSONDecodeError:
            clar = []
    log.info("clarify_generated", question=req.question[:50], count=len(clar))
    return JSONResponse({"clarifications": clar})


@app.get("/api/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": "7.0.0"})


# ── Static frontend ───────────────────────────────────────────────────────────
# Serve Vite build output (frontend/dist/) at /

_frontend_dist = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="static")
