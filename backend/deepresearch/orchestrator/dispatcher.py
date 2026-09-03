"""Dispatcher — A2A parallel fan-out.

Key design decisions (from PRD):
  - Each Worker gets a FRESH context window (no shared state between workers).
  - Workers cannot spawn sub-workers — they have no access to Dispatcher.
    This is an architectural hard ban: only LeadAgent holds a Dispatcher instance.
  - max_total_workers is enforced HERE in code, not in a prompt.
  - Parallel execution via asyncio.gather().
"""

from __future__ import annotations

import asyncio

from deepresearch.common.exceptions import AgentBudgetExceededError
from deepresearch.common.logging import get_logger
from deepresearch.filesystem.virtual_fs import VirtualFS
from deepresearch.memory.base import MemoryService
from deepresearch.model_client import BaseModelClient
from deepresearch.observability.tracer import Tracer
from deepresearch.orchestrator.task_tree import TaskNode
from deepresearch.rag.retriever import ChromaRetriever
from deepresearch.schemas.models import EventType, ResearchRun, TaskStatus
from deepresearch.workers.research_worker import ResearchWorker, build_mcp_client

log = get_logger("orchestrator.dispatcher")


class Dispatcher:
    """Parallel fan-out engine.  Only LeadAgent should instantiate this."""

    def __init__(
        self,
        model_client: BaseModelClient,
        tracer: Tracer,
        run_id: str,
        vfs: VirtualFS | None = None,
        retriever: ChromaRetriever | None = None,
        memory: MemoryService | None = None,
    ) -> None:
        self._model = model_client
        self._tracer = tracer
        self._run_id = run_id
        self._vfs = vfs
        self._retriever = retriever
        self._memory = memory
        # P5: track live asyncio Tasks for cancellation
        self._active_tasks: list[asyncio.Task] = []

    async def dispatch(self, nodes: list[TaskNode], run: ResearchRun) -> None:
        """
        Fan out: each node → isolated ResearchWorker with a fresh context.
        Results are written back into node.finding.
        """
        if not nodes:
            return

        # ── Hard limit: total workers spawned across the entire run ───────────
        remaining = run.max_total_workers - run.total_workers_spawned
        if remaining <= 0:
            raise AgentBudgetExceededError(
                "max_total_workers", run.total_workers_spawned, run.max_total_workers
            )
        if len(nodes) > remaining:
            log.warning(
                "dispatch_trimmed",
                requested=len(nodes),
                allowed=remaining,
            )
            nodes = nodes[:remaining]

        # ── Token budget pre-check ────────────────────────────────────────────
        if run.tokens_used >= run.max_tokens_budget:
            raise AgentBudgetExceededError(
                "max_tokens_budget", run.tokens_used, run.max_tokens_budget
            )

        run.total_workers_spawned += len(nodes)

        self._tracer.emit(
            EventType.TASK_DISPATCH,
            self._run_id,
            count=len(nodes),
            queries=[n.query for n in nodes],
        )
        log.info("dispatching", count=len(nodes))

        # ── Parallel fan-out ──────────────────────────────────────────────────
        tasks = [
            asyncio.create_task(self._run_node(node, run), name=f"worker-{node.task_id[:8]}")
            for node in nodes
        ]
        self._active_tasks.extend(tasks)
        try:
            await asyncio.gather(*tasks, return_exceptions=False)
        finally:
            for t in tasks:
                try:
                    self._active_tasks.remove(t)
                except ValueError:
                    pass

    async def cancel_pending(self) -> int:
        """Cancel all active worker tasks (P5 HITL abort support).

        Returns the number of tasks that were cancelled.
        """
        tasks = list(self._active_tasks)
        for t in tasks:
            t.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        self._active_tasks.clear()
        cancelled = sum(1 for r in results if isinstance(r, asyncio.CancelledError))
        log.info("dispatcher_cancelled", count=cancelled, total=len(tasks))
        return cancelled

    async def _run_node(self, node: TaskNode, run: ResearchRun) -> None:
        """Run one worker in isolation — no shared context with siblings."""
        node.status = TaskStatus.RUNNING
        worker_id = f"worker-{node.task_id[:8]}"

        # Each worker gets its OWN MCP client → own tool call state, no cross-talk
        # But they share retriever + memory (for cross-worker dedup & knowledge)
        mcp = build_mcp_client(
            run_id=self._run_id,
            retriever=self._retriever,
            memory=self._memory,
            task_id=node.task_id,
        )

        worker = ResearchWorker(
            worker_id=worker_id,
            run_id=self._run_id,
            model_client=self._model,   # shared read-only model client is fine
            mcp_client=mcp,
            tracer=self._tracer,
            max_steps=8,
            vfs=self._vfs,
            retriever=self._retriever,
            memory=self._memory,
            task_id=node.task_id,
        )

        try:
            finding = await worker.research(node.query)
            node.finding = finding
            node.status = TaskStatus.DONE
            run.tokens_used += worker.tokens_used
            log.info("worker_done", worker=worker_id, tokens=worker.tokens_used)
        except Exception as exc:
            log.error("worker_failed", worker=worker_id, error=str(exc))
            node.status = TaskStatus.FAILED
            from deepresearch.schemas.models import Finding
            node.finding = Finding(
                run_id=self._run_id,
                task_id=node.task_id,
                summary=f"[研究失败: {exc}]",
            )
