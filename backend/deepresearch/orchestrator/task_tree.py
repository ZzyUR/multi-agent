"""Task tree — ROMA-style decomposition (Atomizer / Planner / Executor / Aggregator).

P2: flat tree (root → N leaves), all leaves run in parallel.
P3+: can support multi-level dependencies.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from deepresearch.schemas.models import Finding, TaskStatus


@dataclass
class TaskNode:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    query: str = ""
    depth: int = 0
    status: TaskStatus = TaskStatus.PENDING
    finding: Finding | None = None
    parent_id: str | None = None
    children: list["TaskNode"] = field(default_factory=list)

    # ── Atomizer ──────────────────────────────────────────────────────────────
    def is_atomic(self) -> bool:
        """P2: every leaf is treated as atomic (dispatched directly)."""
        return len(self.children) == 0


class TaskTree:
    """Tracks the full research task hierarchy for one run."""

    def __init__(self, root_query: str, run_id: str) -> None:
        self.run_id = run_id
        self.root = TaskNode(run_id=run_id, query=root_query, depth=0)
        self._nodes: dict[str, TaskNode] = {self.root.task_id: self.root}

    # ── Planner ───────────────────────────────────────────────────────────────
    def add_children(
        self, parent: TaskNode, queries: list[str]
    ) -> list[TaskNode]:
        """Create child TaskNodes and attach to parent."""
        children: list[TaskNode] = []
        for q in queries:
            node = TaskNode(
                run_id=self.run_id,
                query=q,
                depth=parent.depth + 1,
                parent_id=parent.task_id,
            )
            parent.children.append(node)
            self._nodes[node.task_id] = node
            children.append(node)
        return children

    # ── Aggregator ────────────────────────────────────────────────────────────
    def collect_findings(self) -> list[Finding]:
        """Collect all findings from completed leaf nodes (breadth-first)."""
        findings: list[Finding] = []
        queue = list(self.root.children) or [self.root]
        while queue:
            node = queue.pop(0)
            if node.finding and node.status == TaskStatus.DONE:
                findings.append(node.finding)
            queue.extend(node.children)
        return findings

    def leaf_nodes(self) -> list[TaskNode]:
        result: list[TaskNode] = []
        self._collect_leaves(self.root, result)
        return result

    def _collect_leaves(self, node: TaskNode, acc: list[TaskNode]) -> None:
        if node.is_atomic():
            acc.append(node)
        else:
            for child in node.children:
                self._collect_leaves(child, acc)

    # ── Status summary ────────────────────────────────────────────────────────
    def summary(self) -> dict:
        leaves = self.leaf_nodes()
        done = [n for n in leaves if n.status == TaskStatus.DONE]
        failed = [n for n in leaves if n.status == TaskStatus.FAILED]
        return {
            "total_leaves": len(leaves),
            "done": len(done),
            "failed": len(failed),
            "pending": len(leaves) - len(done) - len(failed),
        }
