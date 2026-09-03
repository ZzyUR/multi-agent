"""FIFO TODO queue — holds pending TaskNodes for the Lead Agent's dispatch loop."""

from __future__ import annotations

from collections import deque

from deepresearch.orchestrator.task_tree import TaskNode
from deepresearch.schemas.models import Finding, TaskStatus


class TodoQueue:
    """Thread-safe-by-convention FIFO queue of pending research tasks."""

    def __init__(self) -> None:
        self._pending: deque[TaskNode] = deque()
        self._completed: list[TaskNode] = []
        self._failed: list[TaskNode] = []

    # ── Mutation ──────────────────────────────────────────────────────────────

    def add(self, *nodes: TaskNode) -> None:
        self._pending.extend(nodes)

    def pop_batch(self, n: int) -> list[TaskNode]:
        """Dequeue up to n items (no more than available)."""
        batch: list[TaskNode] = []
        for _ in range(min(n, len(self._pending))):
            batch.append(self._pending.popleft())
        return batch

    def mark_done(self, node: TaskNode, finding: Finding) -> None:
        node.finding = finding
        node.status = TaskStatus.DONE
        self._completed.append(node)

    def mark_failed(self, node: TaskNode, error: str) -> None:
        node.status = TaskStatus.FAILED
        node.finding = Finding(
            run_id=node.run_id,
            task_id=node.task_id,
            summary=f"[Worker failed: {error}]",
        )
        self._failed.append(node)

    # ── Queries ───────────────────────────────────────────────────────────────

    @property
    def has_pending(self) -> bool:
        return len(self._pending) > 0

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def completed(self) -> list[TaskNode]:
        return list(self._completed)

    @property
    def failed(self) -> list[TaskNode]:
        return list(self._failed)
