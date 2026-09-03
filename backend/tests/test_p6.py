"""P6 可观测性 / 成本控制 / 编排对照 — offline tests.

Coverage:
  6.1/6.3  TraceReader.replay() produces correct decision chain
  6.2      TraceDB SQLite insert / load / list_runs / batch
  6.4      tool_success_rate() and per-tool stats
  6.5      research_profiles.yaml — fast < standard < deep on all axes
  6.6      RunStats.compute_cost() and summary_lines()
  6.7      LangGraph comparison module imports + graph build + comparison table
  6.8      /api/research/{run_id}/stats and /api/research/{run_id}/replay
           (tested via FastAPI test client)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from deepresearch.observability.trace_db import TraceDB
from deepresearch.observability.trace_reader import RunStats, ToolStats, TraceReader
from deepresearch.observability.tracer import Tracer
from deepresearch.schemas.models import EventType

# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_trace(trace_dir: str, run_id: str = "run-p6") -> None:
    """Emit a realistic set of trace events into trace_dir."""
    tracer = Tracer(trace_dir=trace_dir, stdout=False)
    t = tracer.emit

    t(EventType.RUN_START,     run_id, question="量子计算对密码学的影响？", profile="fast")
    t(EventType.PLAN_START,    run_id)
    t(EventType.PLAN_DONE,     run_id, subtasks=["背景", "应用"], count=2)
    t(EventType.TASK_DISPATCH, run_id, count=2, queries=["背景", "应用"])

    t(EventType.TASK_START,    run_id, agent_id="worker-1", query="背景")
    t(EventType.TOOL_CALL,     run_id, tool="web_search", args={"query": "量子计算"})
    t(EventType.TOOL_RESULT,   run_id, tool="web_search", success=True,  duration_ms=120.0)
    t(EventType.TOOL_CALL,     run_id, tool="fetch_page", args={"url": "http://a.com"})
    t(EventType.TOOL_RESULT,   run_id, tool="fetch_page", success=True,  duration_ms=340.0)
    t(EventType.TOOL_CALL,     run_id, tool="web_search", args={"query": "密码学"})
    t(EventType.TOOL_RESULT,   run_id, tool="web_search", success=False, duration_ms=50.0)
    t(EventType.TASK_DONE,     run_id, agent_id="worker-1", tokens=800)

    t(EventType.SYNTHESIZE,    run_id)
    t(EventType.CITATION_CHECK,run_id, stage="done", total=5, supported=4, support_rate=0.8)
    t(EventType.RUN_END,       run_id, tokens_used=2500, total_workers=2,
                                       cache_hit_rate=0.35, citation_support_rate=0.8)


# ── 6.2  TraceDB ──────────────────────────────────────────────────────────────

def test_trace_db_insert_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        tracer = Tracer(trace_dir=tmpdir, stdout=False,
                        db=TraceDB(Path(tmpdir) / "traces.db"))
        run_id = "db-test-run"
        tracer.emit(EventType.RUN_START, run_id, question="Test?", profile="fast")
        tracer.emit(EventType.RUN_END, run_id, tokens_used=100)

        db = TraceDB(Path(tmpdir) / "traces.db")
        events = db.load_run(run_id)

        assert len(events) == 2
        assert events[0]["event_type"] == "run_start"
        assert events[1]["event_type"] == "run_end"
        assert events[0]["data"]["question"] == "Test?"


def test_trace_db_insert_many():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = TraceDB(Path(tmpdir) / "traces.db")
        tracer = Tracer(trace_dir=tmpdir, stdout=False)
        run_id = "batch-run"
        ev1 = tracer.emit(EventType.RUN_START, run_id, question="Q")
        ev2 = tracer.emit(EventType.RUN_END, run_id, tokens_used=50)

        db.insert_many([ev1, ev2])
        assert db.count_events(run_id) == 2


def test_trace_db_list_runs():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = TraceDB(Path(tmpdir) / "traces.db")
        tracer = Tracer(trace_dir=tmpdir, stdout=False, db=db)
        tracer.emit(EventType.RUN_START, "run-A", question="A")
        tracer.emit(EventType.RUN_START, "run-B", question="B")

        runs = db.list_runs()
        assert "run-A" in runs
        assert "run-B" in runs


def test_trace_db_count_events():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = TraceDB(Path(tmpdir) / "traces.db")
        tracer = Tracer(trace_dir=tmpdir, stdout=False, db=db)
        for i in range(5):
            tracer.emit(EventType.TOOL_CALL, "run-cnt", tool=f"tool_{i}")
        assert db.count_events("run-cnt") == 5


def test_trace_db_run_summary():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = TraceDB(Path(tmpdir) / "traces.db")
        tracer = Tracer(trace_dir=tmpdir, stdout=False, db=db)
        tracer.emit(EventType.RUN_START, "run-s", question="Q")
        tracer.emit(EventType.PLAN_DONE, "run-s", count=3)
        tracer.emit(EventType.RUN_END,   "run-s", tokens_used=200)

        summary = db.run_summary("run-s")
        assert summary["event_count"] == 3
        assert summary["event_type_counts"]["run_start"] == 1
        assert summary["event_type_counts"]["run_end"] == 1


def test_trace_db_deduplicates_event_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = TraceDB(Path(tmpdir) / "traces.db")
        tracer = Tracer(trace_dir=tmpdir, stdout=False)
        ev = tracer.emit(EventType.RUN_START, "run-dup", question="Q")
        db.insert(ev)
        db.insert(ev)  # duplicate — should be silently ignored
        assert db.count_events("run-dup") == 1


def test_trace_db_empty_run_returns_nothing():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = TraceDB(Path(tmpdir) / "traces.db")
        assert db.load_run("nonexistent-run") == []
        assert db.count_events("nonexistent-run") == 0


# ── 6.1 / 6.3  TraceReader ───────────────────────────────────────────────────

def test_trace_reader_load_and_event_count():
    with tempfile.TemporaryDirectory() as tmpdir:
        _build_trace(tmpdir)
        reader = TraceReader.load("run-p6", trace_dir=tmpdir)
        # Ensure multiple events were loaded
        assert len(reader._events) >= 10


def test_trace_reader_stats_tokens_and_profile():
    with tempfile.TemporaryDirectory() as tmpdir:
        _build_trace(tmpdir)
        reader = TraceReader.load("run-p6", trace_dir=tmpdir)
        stats = reader.stats()

        assert stats.total_tokens == 2500
        assert stats.profile == "fast"
        assert stats.question == "量子计算对密码学的影响？"
        assert stats.cache_hit_rate == pytest.approx(0.35)
        assert stats.citation_support_rate == pytest.approx(0.8)


def test_trace_reader_stats_tool_calls():
    with tempfile.TemporaryDirectory() as tmpdir:
        _build_trace(tmpdir)
        stats = TraceReader.load("run-p6", trace_dir=tmpdir).stats()

        assert "web_search" in stats.tool_stats
        ws = stats.tool_stats["web_search"]
        assert ws.calls == 2          # two web_search tool_calls emitted
        assert ws.successes == 1
        assert ws.failures == 1
        assert ws.success_rate == pytest.approx(0.5)


def test_trace_reader_replay_structure():
    with tempfile.TemporaryDirectory() as tmpdir:
        _build_trace(tmpdir)
        replay = TraceReader.load("run-p6", trace_dir=tmpdir).replay()

        assert "RUN_START" in replay
        assert "PLAN_DONE" in replay
        assert "DISPATCH" in replay
        assert "WORKER_START" in replay
        assert "RUN_END" in replay
        assert "量子计算" in replay


def test_trace_reader_tool_success_rate():
    with tempfile.TemporaryDirectory() as tmpdir:
        _build_trace(tmpdir)
        rates = TraceReader.load("run-p6", trace_dir=tmpdir).tool_success_rate()

        assert "web_search" in rates
        assert rates["web_search"] == pytest.approx(0.5)
        assert "fetch_page" in rates
        assert rates["fetch_page"] == pytest.approx(1.0)


# ── 6.4  Metrics via TraceReader.stats() ──────────────────────────────────────

def test_run_stats_total_findings():
    with tempfile.TemporaryDirectory() as tmpdir:
        tracer = Tracer(trace_dir=tmpdir, stdout=False)
        rid = "run-findings"
        tracer.emit(EventType.RUN_START, rid, question="Q", profile="standard")
        tracer.emit(EventType.TASK_DONE, rid, agent_id="w1", tokens=100)
        tracer.emit(EventType.TASK_DONE, rid, agent_id="w2", tokens=200)
        tracer.emit(EventType.RUN_END,   rid, tokens_used=500)

        stats = TraceReader.load(rid, trace_dir=tmpdir).stats()
        assert stats.total_findings == 2


def test_tool_stats_avg_latency():
    with tempfile.TemporaryDirectory() as tmpdir:
        _build_trace(tmpdir)
        stats = TraceReader.load("run-p6", trace_dir=tmpdir).stats()
        ws = stats.tool_stats["fetch_page"]
        # avg_latency_ms is computed from event timestamps; non-negative
        assert ws.avg_latency_ms >= 0


# ── 6.5  Research profiles ────────────────────────────────────────────────────

def _load_yaml_profiles():
    import yaml
    from deepresearch.config.settings import get_settings
    cfg = get_settings()
    with open(cfg.profiles_path) as f:
        return yaml.safe_load(f)["profiles"]


def test_profiles_breadth_order():
    profiles = _load_yaml_profiles()
    assert profiles["fast"]["max_breadth"] < profiles["standard"]["max_breadth"]
    assert profiles["standard"]["max_breadth"] < profiles["deep"]["max_breadth"]


def test_profiles_depth_order():
    profiles = _load_yaml_profiles()
    assert profiles["fast"]["max_depth"] <= profiles["standard"]["max_depth"]
    assert profiles["standard"]["max_depth"] < profiles["deep"]["max_depth"]


def test_profiles_token_budget_order():
    profiles = _load_yaml_profiles()
    assert profiles["fast"]["max_tokens_budget"] < profiles["standard"]["max_tokens_budget"]
    assert profiles["standard"]["max_tokens_budget"] < profiles["deep"]["max_tokens_budget"]


def test_profiles_have_required_keys():
    profiles = _load_yaml_profiles()
    required = {"max_depth", "max_breadth", "max_total_workers", "max_tokens_budget"}
    for name in ("fast", "standard", "deep"):
        assert required <= profiles[name].keys(), f"Profile '{name}' missing keys"


def test_profile_loaded_by_lead_agent():
    """LeadAgent._load_profile() returns correct values."""
    from deepresearch.orchestrator.lead_agent import _load_profile
    fast = _load_profile("fast")
    deep = _load_profile("deep")
    assert fast["max_breadth"] < deep["max_breadth"]
    assert fast["max_tokens_budget"] < deep["max_tokens_budget"]


# ── 6.6  Cost computation ─────────────────────────────────────────────────────

def test_run_stats_cost_positive():
    with tempfile.TemporaryDirectory() as tmpdir:
        _build_trace(tmpdir)
        stats = TraceReader.load("run-p6", trace_dir=tmpdir).stats()
        assert stats.estimated_cost_usd > 0.0


def test_run_stats_cost_scales_with_tokens():
    rs_low  = RunStats(run_id="x", total_tokens=1000)
    rs_high = RunStats(run_id="y", total_tokens=100_000)
    rs_low.compute_cost()
    rs_high.compute_cost()
    assert rs_high.estimated_cost_usd > rs_low.estimated_cost_usd * 50


def test_run_stats_summary_lines():
    rs = RunStats(
        run_id="test", question="Research Q?", profile="standard",
        total_tokens=5000, total_workers=3, duration_ms=12_000,
        cache_hit_rate=0.4, citation_support_rate=0.85,
    )
    rs.compute_cost()
    lines = "\n".join(rs.summary_lines())
    assert "Research Q?" in lines
    assert "standard" in lines
    assert "5,000" in lines
    assert "12.0s" in lines
    assert "85%" in lines


# ── 6.7  LangGraph comparison ─────────────────────────────────────────────────

def test_langgraph_module_importable():
    from deepresearch.orchestrator import langgraph_impl  # noqa: F401


def test_langgraph_comparison_table_structure():
    from deepresearch.orchestrator.langgraph_impl import COMPARISON
    assert "LangGraph" in COMPARISON
    assert "Custom LeadAgent" in COMPARISON
    assert "State management" in COMPARISON


def test_langgraph_build_graph_handles_missing_package():
    from deepresearch.orchestrator.langgraph_impl import build_research_graph
    result = build_research_graph()
    # Either returns a compiled graph (langgraph installed) or None (not installed)
    assert result is None or hasattr(result, "ainvoke")


def test_langgraph_state_schema():
    from deepresearch.orchestrator.langgraph_impl import ResearchState
    state: ResearchState = {
        "question": "Test?",
        "profile": "fast",
        "run_id": "lg-test",
        "subtasks": ["A", "B"],
        "findings": [],
        "report": "",
        "depth": 0,
        "tokens_used": 0,
        "sufficient": False,
    }
    assert state["question"] == "Test?"


def test_langgraph_should_continue_logic():
    from deepresearch.orchestrator.langgraph_impl import _should_continue
    # sufficient=True → "synthesize"
    assert _should_continue({"question": "Q", "profile": "fast", "sufficient": True, "depth": 0}) == "synthesize"
    # sufficient=False, depth=0 < max_depth=1 → "dispatch"
    assert _should_continue({"question": "Q", "profile": "fast", "sufficient": False, "depth": 0}) == "dispatch"
    # sufficient=False but depth >= max_depth → "synthesize"
    assert _should_continue({"question": "Q", "profile": "fast", "sufficient": False, "depth": 99}) == "synthesize"


# ── 6.8  API endpoints ────────────────────────────────────────────────────────

@pytest.fixture
def api_client(tmp_path):
    """FastAPI test client with temp trace dir."""
    import os
    os.environ["TRACE_DIR"] = str(tmp_path)
    os.environ["TRACE_STDOUT"] = "false"
    # Clear settings cache so new env vars take effect
    from deepresearch.config.settings import get_settings
    get_settings.cache_clear()

    from fastapi.testclient import TestClient
    from deepresearch.api.app import app
    with TestClient(app) as client:
        yield client, tmp_path

    get_settings.cache_clear()


def test_api_health(api_client):
    client, _ = api_client
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_api_stats_returns_404_for_unknown_run(api_client):
    client, _ = api_client
    resp = client.get("/api/research/nonexistent-run/stats")
    assert resp.status_code == 404


def test_api_replay_returns_404_for_unknown_run(api_client):
    client, _ = api_client
    resp = client.get("/api/research/nonexistent-run/replay")
    assert resp.status_code == 404


def test_api_stats_and_replay_with_real_trace(api_client):
    client, tmp_path = api_client
    _build_trace(str(tmp_path), run_id="api-test-run")

    stats_resp = client.get("/api/research/api-test-run/stats")
    assert stats_resp.status_code == 200
    body = stats_resp.json()
    assert body["tokens"] == 2500
    assert body["profile"] == "fast"
    assert "tool_stats" in body
    assert "web_search" in body["tool_stats"]

    replay_resp = client.get("/api/research/api-test-run/replay")
    assert replay_resp.status_code == 200
    replay_body = replay_resp.json()
    assert "replay" in replay_body
    assert "RUN_START" in replay_body["replay"]
    assert "量子计算" in replay_body["replay"]


def test_api_history_lists_runs(api_client):
    client, tmp_path = api_client
    _build_trace(str(tmp_path), run_id="hist-run-1")
    _build_trace(str(tmp_path), run_id="hist-run-2")

    resp = client.get("/api/research/history")
    assert resp.status_code == 200
    run_ids = [r["run_id"] for r in resp.json()["runs"]]
    assert "hist-run-1" in run_ids
    assert "hist-run-2" in run_ids
