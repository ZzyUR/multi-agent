"""LangGraph comparison implementation (Phase 6.7).

This module shows how the SAME research orchestration can be expressed
using LangGraph's StateGraph API, for architectural comparison.

Key differences from our custom LeadAgent:
  - State is a typed dict, not a class with mutable fields
  - Edges are declared statically; branching via conditional_edge
  - Each "node" is a pure async function (no shared self._* state)
  - LangGraph handles the execution loop; we only define the graph

Usage:
    graph = build_research_graph()
    result = await graph.ainvoke({"question": "...", "profile": "fast"})

Requires: langgraph (optional dependency — falls back gracefully if absent)
"""

from __future__ import annotations

from typing import Any, TypedDict

from deepresearch.common.logging import get_logger

log = get_logger("orchestrator.langgraph")


# ── State schema ──────────────────────────────────────────────────────────────

class ResearchState(TypedDict, total=False):
    """Shared state passed between all graph nodes."""
    question: str
    profile: str
    run_id: str
    subtasks: list[str]
    findings: list[dict]
    report: str
    depth: int
    tokens_used: int
    sufficient: bool


# ── Node functions ────────────────────────────────────────────────────────────

async def node_plan(state: ResearchState) -> ResearchState:
    """PLAN node — equivalent to LeadAgent._plan()."""
    from deepresearch.model_client import get_model_client
    from deepresearch.orchestrator.lead_agent import LeadAgent, _load_profile, _extract_json, _PLAN_SYSTEM
    from deepresearch.schemas.models import Message

    model = get_model_client()
    profile = _load_profile(state.get("profile", "standard"))
    max_breadth = profile.get("max_breadth", 4)

    system = _PLAN_SYSTEM.format(min_tasks=2, max_tasks=max_breadth)
    messages = [
        Message(role="system", content=system),
        Message(role="user", content=f"研究问题：{state['question']}"),
    ]
    text, _, tokens = await model.chat(messages, max_tokens=1024)
    data = _extract_json(text or "")
    subtasks = data.get("subtasks", [state["question"]])[:max_breadth]

    log.info("lg_plan_done", subtasks=subtasks)
    return {
        **state,
        "subtasks": subtasks,
        "tokens_used": state.get("tokens_used", 0) + tokens,
        "depth": 0,
    }


async def node_dispatch(state: ResearchState) -> ResearchState:
    """DISPATCH node — parallel worker fan-out, equivalent to Dispatcher.dispatch()."""
    import asyncio
    import uuid

    from deepresearch.model_client import get_model_client
    from deepresearch.observability.tracer import get_tracer
    from deepresearch.workers.research_worker import ResearchWorker, build_mcp_client

    model = get_model_client()
    tracer = get_tracer()
    run_id = state.get("run_id", str(uuid.uuid4()))

    async def run_worker(query: str) -> dict:
        task_id = str(uuid.uuid4())
        mcp = build_mcp_client(run_id, task_id=task_id)
        worker = ResearchWorker(
            worker_id=f"lg-worker-{task_id[:8]}",
            run_id=run_id,
            model_client=model,
            mcp_client=mcp,
            tracer=tracer,
            max_steps=8,
        )
        finding = await worker.research(query)
        return {
            "task_id": finding.task_id,
            "summary": finding.summary,
            "source_ids": finding.source_ids,
        }

    subtasks = state.get("subtasks", [])
    results = await asyncio.gather(*[run_worker(q) for q in subtasks])

    existing = state.get("findings", [])
    all_findings = existing + list(results)

    log.info("lg_dispatch_done", workers=len(results))
    return {
        **state,
        "run_id": run_id,
        "findings": all_findings,
        "depth": state.get("depth", 0) + 1,
    }


async def node_assess(state: ResearchState) -> ResearchState:
    """ASSESS node — sufficiency check, equivalent to LeadAgent._assess()."""
    from deepresearch.orchestrator.lead_agent import _ASSESS_SYSTEM, _extract_json
    from deepresearch.model_client import get_model_client
    from deepresearch.schemas.models import Message

    model = get_model_client()
    findings = state.get("findings", [])
    question = state["question"]

    summaries = "\n\n".join(
        f"【发现 {i+1}】{f.get('summary', '')}"
        for i, f in enumerate(findings)
    )
    system = _ASSESS_SYSTEM.format(question=question, summaries=summaries)
    messages = [
        Message(role="system", content=system),
        Message(role="user", content="请评估研究完整性。"),
    ]
    text, _, tokens = await model.chat(messages, max_tokens=512)
    data = _extract_json(text or "")
    sufficient = bool(data.get("sufficient", True))
    missing = data.get("missing_topics", [])

    if not sufficient and missing:
        return {
            **state,
            "subtasks": missing,
            "sufficient": False,
            "tokens_used": state.get("tokens_used", 0) + tokens,
        }
    return {
        **state,
        "sufficient": True,
        "tokens_used": state.get("tokens_used", 0) + tokens,
    }


async def node_synthesize(state: ResearchState) -> ResearchState:
    """SYNTHESIZE node — equivalent to LeadAgent._synthesize()."""
    from deepresearch.orchestrator.lead_agent import _SYNTHESIZE_SYSTEM
    from deepresearch.model_client import get_model_client
    from deepresearch.schemas.models import Message

    model = get_model_client()
    findings = state.get("findings", [])
    question = state["question"]

    summaries = "\n\n---\n\n".join(
        f"**发现 {i+1}**: {f.get('summary', '')}"
        for i, f in enumerate(findings)
    )
    system = _SYNTHESIZE_SYSTEM.format(question=question, summaries=summaries)
    messages = [
        Message(role="system", content=system),
        Message(role="user", content="请撰写综合研究报告。"),
    ]
    text, _, tokens = await model.chat(messages, max_tokens=8192)

    log.info("lg_synthesize_done")
    return {
        **state,
        "report": text or "（报告生成失败）",
        "tokens_used": state.get("tokens_used", 0) + tokens,
    }


def _should_continue(state: ResearchState) -> str:
    """Conditional edge: dispatch again or move to synthesize."""
    profile_name = state.get("profile", "standard")
    from deepresearch.orchestrator.lead_agent import _load_profile
    profile = _load_profile(profile_name)
    max_depth = profile.get("max_depth", 2)

    if state.get("sufficient", True):
        return "synthesize"
    if state.get("depth", 0) >= max_depth:
        return "synthesize"
    return "dispatch"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_research_graph():
    """Build and return a compiled LangGraph StateGraph.

    Falls back to None if langgraph is not installed.
    This function is intentionally lazy-imported so the module can be imported
    even without langgraph installed (for documentation/comparison purposes).
    """
    try:
        from langgraph.graph import StateGraph, END  # type: ignore[import]
    except ImportError:
        log.warning("langgraph_not_installed", msg="pip install langgraph to use the graph")
        return None

    builder = StateGraph(ResearchState)

    # Nodes
    builder.add_node("plan", node_plan)
    builder.add_node("dispatch", node_dispatch)
    builder.add_node("assess", node_assess)
    builder.add_node("synthesize", node_synthesize)

    # Edges
    builder.set_entry_point("plan")
    builder.add_edge("plan", "dispatch")
    builder.add_edge("dispatch", "assess")
    builder.add_conditional_edges(
        "assess",
        _should_continue,
        {"dispatch": "dispatch", "synthesize": "synthesize"},
    )
    builder.add_edge("synthesize", END)

    return builder.compile()


# ── Architectural comparison table ────────────────────────────────────────────

COMPARISON = """
┌──────────────────────┬────────────────────────────┬──────────────────────────────┐
│ Dimension            │ Custom LeadAgent (Our)     │ LangGraph                    │
├──────────────────────┼────────────────────────────┼──────────────────────────────┤
│ State management     │ Mutable class attributes   │ Immutable TypedDict snapshots│
│ Branching            │ if/while in Python         │ Declarative conditional_edge │
│ Parallelism          │ asyncio.gather() explicit  │ Graph fan-out (built-in)     │
│ Observability        │ Custom Tracer + JSONL      │ LangSmith integration        │
│ Persistence          │ Custom checkpoint store    │ SqliteSaver / RedisSaver     │
│ Learning curve       │ Low (pure Python)          │ Medium (graph mental model)  │
│ Flexibility          │ Full (any Python pattern)  │ Constrained by graph API     │
│ Interview value      │ Shows architecture design  │ Shows ecosystem familiarity  │
└──────────────────────┴────────────────────────────┴──────────────────────────────┘
"""
