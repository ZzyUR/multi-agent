"""P5 防幻觉与人在回路 — offline tests.

Coverage:
  5.1/5.3 CitationAgent: flag / delete unsupported claims
  5.4/5.5 Checkpoint: save → load → resume from synth stage
  5.6     Circuit breaker triggers tool fallback
  5.7/5.8 HITL broker: intent clarification + plan review
  5.9/5.10 HITL: abort signal detected in dispatch loop
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

from deepresearch.checkpoint.state_store import CheckpointData, CheckpointStore
from deepresearch.mcp.client import LocalMCPClient
from deepresearch.mcp.retry_policy import RetryPolicy
from deepresearch.mcp.tool_schema import ToolDefinition
from deepresearch.model_client import BaseModelClient, MockModelClient
from deepresearch.orchestrator.dispatcher import Dispatcher
from deepresearch.orchestrator.hitl import HITLBroker
from deepresearch.observability.tracer import Tracer
from deepresearch.schemas.models import EventType, Message, ToolCall
from deepresearch.workers.citation_agent import CitationAgent

# ── Shared test fixtures ───────────────────────────────────────────────────────

_TEST_REPORT = """\
# Research Report

## Summary
Mock claim A is critical.
Mock claim B has been proven.

## Sources
[1] https://example.com
"""

# Model that returns valid JSON for citation tasks
class _CitationMockClient(BaseModelClient):
    async def chat(
        self, messages: list[Message], *, tools=None, **kwargs
    ) -> tuple[str | None, list[ToolCall], int]:
        system = next((m.content for m in messages if m.role == "system"), "")
        if "事实性论断" in (system or ""):
            # Claim extraction → return JSON array matching report content
            return '["Mock claim A is critical.", "Mock claim B has been proven."]', [], 50
        # Claim verification (only called if retriever returns hits) → not needed here
        return '{"supported": false, "reason": "no evidence"}', [], 50


def _tracer() -> Tracer:
    import tempfile
    return Tracer(trace_dir=tempfile.mkdtemp(), stdout=False)


# ── 5.1 / 5.3  CitationAgent ──────────────────────────────────────────────────

async def test_citation_flags_unsupported_claims():
    agent = CitationAgent(
        model_client=_CitationMockClient(),
        retriever=None,   # no retriever → all claims unsupported
        tracer=_tracer(),
        run_id="test-cite-flag",
        policy="flag",
    )
    revised, report_obj = await agent.verify_and_revise(_TEST_REPORT)

    assert report_obj.total_claims == 2
    assert report_obj.unsupported == 2
    assert report_obj.support_rate == 0.0
    assert "⚠" in revised


async def test_citation_deletes_unsupported_claims():
    agent = CitationAgent(
        model_client=_CitationMockClient(),
        retriever=None,
        tracer=_tracer(),
        run_id="test-cite-del",
        policy="delete",
    )
    revised, report_obj = await agent.verify_and_revise(_TEST_REPORT)

    assert report_obj.unsupported == 2
    assert "Mock claim A is critical." not in revised
    assert "Mock claim B has been proven." not in revised


async def test_citation_keep_as_is_leaves_report_unchanged():
    agent = CitationAgent(
        model_client=_CitationMockClient(),
        retriever=None,
        tracer=_tracer(),
        run_id="test-cite-keep",
        policy="keep_as_is",
    )
    revised, _ = await agent.verify_and_revise(_TEST_REPORT)
    assert revised == _TEST_REPORT


async def test_citation_no_claims_returns_intact():
    empty_report = "# Report\n\nNo factual claims here."
    # Mock that returns empty array
    class _EmptyClaimMock(BaseModelClient):
        async def chat(self, messages, *, tools=None, **kwargs):
            return "[]", [], 10

    agent = CitationAgent(
        model_client=_EmptyClaimMock(),
        retriever=None,
        tracer=_tracer(),
        run_id="test-cite-empty",
        policy="flag",
    )
    revised, report_obj = await agent.verify_and_revise(empty_report)
    assert revised == empty_report
    assert report_obj.total_claims == 0


# ── 5.4 / 5.5  Checkpoint save → load → resume ────────────────────────────────

def test_checkpoint_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = CheckpointStore("run-abc", checkpoint_dir=tmpdir)
        data = CheckpointData(
            run_id="run-abc", stage="plan", question="Test?",
            profile="fast", subtask_queries=["sub1", "sub2"],
            tokens_used=100,
        )
        path = store.save(data)
        assert Path(path).exists()

        loaded = store.load_latest()
        assert loaded is not None
        assert loaded.stage == "plan"
        assert loaded.subtask_queries == ["sub1", "sub2"]
        assert loaded.tokens_used == 100


def test_checkpoint_load_returns_latest_of_multiple():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = CheckpointStore("run-multi", checkpoint_dir=tmpdir)
        store.save(CheckpointData(
            run_id="run-multi", stage="plan", question="Q",
            profile="fast", subtask_queries=["s1"],
        ))
        time.sleep(0.01)  # ensure different timestamp
        store.save(CheckpointData(
            run_id="run-multi", stage="worker", question="Q",
            profile="fast", subtask_queries=["s1"], findings=[{"summary": "f1"}],
        ))
        loaded = store.load_latest()
        assert loaded.stage == "worker"
        assert loaded.findings == [{"summary": "f1"}]


def test_checkpoint_load_returns_none_when_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = CheckpointStore("run-empty", checkpoint_dir=tmpdir)
        assert store.load_latest() is None


def test_checkpoint_clear_removes_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = CheckpointStore("run-clear", checkpoint_dir=tmpdir)
        store.save(CheckpointData(
            run_id="run-clear", stage="plan", question="Q", profile="fast",
        ))
        store.clear()
        assert store.load_latest() is None
        assert store.list_checkpoints() == []


def test_checkpoint_data_round_trip():
    original = CheckpointData(
        run_id="xyz", stage="synth", question="Test question",
        profile="standard", subtask_queries=["A", "B"],
        report="# Report\n\nContent.",
        tokens_used=5000,
        citation_report={"total": 3, "supported": 2, "support_rate": 0.667},
    )
    restored = CheckpointData.from_dict(original.to_dict())
    assert restored.stage == original.stage
    assert restored.report == original.report
    assert restored.citation_report == original.citation_report


# ── 5.6  Circuit breaker + fallback tool ──────────────────────────────────────

async def test_fallback_tool_used_after_circuit_opens():
    _fallback_calls = []

    async def _failing_search(**kwargs):
        raise ConnectionError("network error")

    async def _fallback_search(**kwargs):
        _fallback_calls.append(kwargs)
        return [{"title": "fallback", "url": "http://fallback.com", "snippet": "ok"}]

    # Circuit opens after 2 consecutive failures (threshold=2, max_retries=1)
    policy = RetryPolicy(max_retries=1, circuit_threshold=2)
    client = LocalMCPClient(
        run_id="test-fallback",
        retry_policy=policy,
        fallback_map={"web_search": "fallback_search"},
    )

    _params = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    web_search_def = ToolDefinition(name="web_search", description="Primary search", parameters=_params)
    fallback_def = ToolDefinition(name="fallback_search", description="Fallback search", parameters=_params)
    client.register(web_search_def, _failing_search)
    client.register(fallback_def, _fallback_search)

    # Two calls to open circuit
    result1 = await client.call_tool("web_search", {"query": "test"})
    result2 = await client.call_tool("web_search", {"query": "test"})
    assert not result1.success
    assert not result2.success

    # Third call: circuit open → should use fallback
    result3 = await client.call_tool("web_search", {"query": "test"})
    assert result3.success
    assert result3.tool_name == "fallback_search"
    assert result3.output[0]["title"] == "fallback"
    assert len(_fallback_calls) >= 1


async def test_unknown_tool_returns_failure():
    client = LocalMCPClient(run_id="test-unknown")
    result = await client.call_tool("nonexistent_tool", {})
    assert not result.success
    assert "Unknown tool" in result.error


# ── 5.7 / 5.8  HITL Broker intent + plan review ───────────────────────────────

async def test_hitl_auto_approve_returns_original_question():
    broker = HITLBroker(auto_approve=True)
    result = await broker.intent_clarify("run1", "original question")
    assert result == "original question"


async def test_hitl_auto_approve_returns_original_plan():
    broker = HITLBroker(auto_approve=True)
    plan = ["subtask A", "subtask B"]
    result = await broker.plan_review("run1", plan)
    assert result == plan


async def test_hitl_respond_delivers_clarification():
    broker = HITLBroker(auto_approve=False, timeout=2.0)

    async def _waiter():
        return await broker.intent_clarify("run1", "original question")

    task = asyncio.create_task(_waiter())
    await asyncio.sleep(0.02)   # let waiter block on queue
    broker.respond("run1", "refined question")
    result = await task

    assert result == "refined question"


async def test_hitl_respond_delivers_plan_modification():
    broker = HITLBroker(auto_approve=False, timeout=2.0)
    original = ["old task 1", "old task 2"]
    new_plan = ["new task A", "new task B", "new task C"]

    async def _waiter():
        return await broker.plan_review("run1", original)

    task = asyncio.create_task(_waiter())
    await asyncio.sleep(0.02)
    broker.respond("run1", json.dumps(new_plan))
    result = await task

    assert result == new_plan


async def test_hitl_plan_review_ok_returns_original():
    broker = HITLBroker(auto_approve=False, timeout=2.0)
    original = ["task 1", "task 2"]

    task = asyncio.create_task(broker.plan_review("run2", original))
    await asyncio.sleep(0.02)
    broker.respond("run2", "ok")
    result = await task

    assert result == original


async def test_hitl_timeout_returns_default():
    broker = HITLBroker(auto_approve=False, timeout=0.05)  # 50ms timeout
    result = await broker.intent_clarify("run-timeout", "fallback question")
    assert result == "fallback question"   # timeout → original returned


# ── 5.9 / 5.10  HITL abort + dispatcher cancel ────────────────────────────────

async def test_hitl_check_abort_detects_signal():
    broker = HITLBroker(auto_approve=False)
    assert not broker.check_abort("run-x")
    broker.signal_abort("run-x")
    assert broker.check_abort("run-x")


async def test_hitl_signal_abort_unblocks_pending_request():
    broker = HITLBroker(auto_approve=False, timeout=5.0)

    async def _waiter():
        return await broker.intent_clarify("run-abort", "question")

    task = asyncio.create_task(_waiter())
    await asyncio.sleep(0.02)
    broker.signal_abort("run-abort")   # should unblock waiter with empty string
    result = await asyncio.wait_for(task, timeout=1.0)
    # Empty response → returns original question
    assert result == "question"


async def test_hitl_clear_run_removes_abort_flag():
    broker = HITLBroker()
    broker.signal_abort("run-clear")
    assert broker.check_abort("run-clear")
    broker.clear_run("run-clear")
    assert not broker.check_abort("run-clear")


async def test_dispatcher_cancel_pending():
    """Workers that are cancelled should not raise to the caller."""
    from deepresearch.orchestrator.dispatcher import Dispatcher
    from deepresearch.orchestrator.task_tree import TaskNode
    from deepresearch.schemas.models import ResearchRun

    tracer = _tracer()
    dispatcher = Dispatcher(MockModelClient(), tracer, "run-cancel")

    cancelled_count = await dispatcher.cancel_pending()
    assert cancelled_count == 0   # nothing active → 0 cancelled

    # Verify the list is empty after cancel
    assert dispatcher._active_tasks == []
