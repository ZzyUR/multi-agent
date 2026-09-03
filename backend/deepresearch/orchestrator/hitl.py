"""Human-in-the-Loop (HITL) broker — three intervention points.

P5 intervention points:
  1. INTENT — before planning: user refines or clarifies the research question
  2. PLAN   — after planning: user adds/removes/reorders subtasks
  3. RUN    — mid-research (via check_abort): user aborts or signals changes

In production the API layer calls respond() / signal_abort() over SSE/WebSocket.
In tests or headless mode, set auto_approve=True to bypass all blocking waits.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from deepresearch.common.logging import get_logger
from deepresearch.schemas.models import EventType

log = get_logger("hitl")

_DEFAULT_TIMEOUT = 300.0   # seconds to wait for human before falling back


class HITLBroker:
    """In-process broker connecting LeadAgent to the human-facing API layer."""

    def __init__(
        self,
        auto_approve: bool = False,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._auto = auto_approve
        self._timeout = timeout
        self._queues: dict[str, asyncio.Queue[str]] = {}
        self._pending: dict[str, dict[str, Any]] = {}   # visible to API layer
        self._aborted: set[str] = set()

    # ── Intervention point 1 ───────────────────────────────────────────────────

    async def intent_clarify(
        self,
        run_id: str,
        question: str,
        tracer=None,
    ) -> str:
        """Block until the user confirms or refines the research question."""
        if self._auto:
            return question
        if tracer:
            tracer.emit(
                EventType.HUMAN_INTERVENE, run_id,
                point="intent", prompt=question,
            )
        log.info("hitl_intent_wait", run_id=run_id)
        response = await self._await_response(
            run_id, "intent",
            f"请确认或修正研究问题（留空则确认原问题）：\n\n{question}",
        )
        if not response or not response.strip():
            return question
        if tracer:
            tracer.emit(
                EventType.HUMAN_INTERVENE, run_id,
                point="intent", action="clarified", new_question=response.strip(),
            )
        log.info("hitl_intent_response", run_id=run_id, length=len(response))
        return response.strip()

    # ── Intervention point 2 ───────────────────────────────────────────────────

    async def plan_review(
        self,
        run_id: str,
        subtasks: list[str],
        tracer=None,
    ) -> list[str]:
        """Block until the user approves or edits the research plan."""
        if self._auto:
            return subtasks
        plan_json = json.dumps(subtasks, ensure_ascii=False, indent=2)
        if tracer:
            tracer.emit(
                EventType.HUMAN_INTERVENE, run_id,
                point="plan", subtasks=subtasks,
            )
        log.info("hitl_plan_wait", run_id=run_id, subtask_count=len(subtasks))
        response = await self._await_response(
            run_id, "plan",
            f"请审核研究计划（回复 'ok' 确认，或直接修改 JSON 列表后返回）：\n\n{plan_json}",
        )
        if not response or response.strip().lower() in ("", "ok", "确认"):
            return subtasks
        try:
            modified = json.loads(response.strip())
            if isinstance(modified, list) and all(isinstance(t, str) for t in modified):
                cleaned = [t.strip() for t in modified if t.strip()]
                if tracer:
                    tracer.emit(
                        EventType.HUMAN_INTERVENE, run_id,
                        point="plan", action="modified", new_subtasks=cleaned,
                    )
                log.info("hitl_plan_modified", run_id=run_id, count=len(cleaned))
                return cleaned
        except (json.JSONDecodeError, TypeError):
            pass
        return subtasks

    # ── Intervention point 3 (non-blocking poll) ───────────────────────────────

    def check_abort(self, run_id: str) -> bool:
        """Return True if the user has signalled this run should stop."""
        return run_id in self._aborted

    # ── API-layer controls ─────────────────────────────────────────────────────

    def respond(self, run_id: str, value: str) -> bool:
        """Deliver a human response to a waiting intent_clarify / plan_review."""
        q = self._queues.get(run_id)
        if q is None:
            log.warning("hitl_respond_no_pending", run_id=run_id)
            return False
        try:
            q.put_nowait(value)
            return True
        except asyncio.QueueFull:
            log.warning("hitl_respond_queue_full", run_id=run_id)
            return False

    def signal_abort(self, run_id: str) -> None:
        """Signal the run to stop after the current dispatch round."""
        self._aborted.add(run_id)
        log.info("hitl_abort_signalled", run_id=run_id)
        self.respond(run_id, "")   # unblock any waiting request

    def get_pending(self, run_id: str) -> dict[str, Any] | None:
        """API-readable: current pending intervention prompt for a run."""
        return self._pending.get(run_id)

    def clear_run(self, run_id: str) -> None:
        """Clean up all state for a finished or cancelled run."""
        self._queues.pop(run_id, None)
        self._pending.pop(run_id, None)
        self._aborted.discard(run_id)

    # ── Internal ───────────────────────────────────────────────────────────────

    async def _await_response(
        self, run_id: str, point: str, prompt: str
    ) -> str | None:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        self._queues[run_id] = q
        self._pending[run_id] = {"point": point, "prompt": prompt}
        try:
            return await asyncio.wait_for(q.get(), timeout=self._timeout)
        except asyncio.TimeoutError:
            log.warning("hitl_timeout", run_id=run_id, point=point)
            return None
        finally:
            self._queues.pop(run_id, None)
            self._pending.pop(run_id, None)


# ── Module singleton ───────────────────────────────────────────────────────────

_broker: HITLBroker | None = None


def get_hitl_broker() -> HITLBroker:
    global _broker
    if _broker is None:
        _broker = HITLBroker(auto_approve=True)   # safe default: no blocking
    return _broker


def set_hitl_broker(broker: HITLBroker) -> None:
    global _broker
    _broker = broker
