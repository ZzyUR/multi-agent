"""Tool call retry + circuit breaker.

Failure handling strategy (P1):
  1. Retry  — network/timeout errors, exponential backoff
  2. Circuit breaker — if a tool fails N times in a row, mark it open
                       and raise ToolCircuitOpenError so Lead can re-plan

Phase 2+ will add:
  - Fallback to secondary tool (search A → search B)
  - Per-run persistent failure stats fed into Trace
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any, Callable, Coroutine

from deepresearch.common.exceptions import (
    ToolCallError,
    ToolCallMaxRetriesError,
    ToolCircuitOpenError,
)
from deepresearch.common.logging import get_logger

log = get_logger("retry_policy")


class RetryPolicy:
    """Exponential-backoff retry + per-tool circuit breaker."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,   # seconds
        circuit_threshold: int = 3, # consecutive failures to open circuit
        circuit_reset_after: float = 60.0,  # seconds before half-open
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.circuit_threshold = circuit_threshold
        self.circuit_reset_after = circuit_reset_after

        self._consecutive_failures: dict[str, int] = defaultdict(int)
        self._circuit_opened_at: dict[str, float] = {}

    # ── Public ─────────────────────────────────────────────────────────────────

    async def execute(
        self,
        tool_name: str,
        fn: Callable[..., Coroutine[Any, Any, Any]],
        **kwargs: Any,
    ) -> Any:
        if self._is_circuit_open(tool_name):
            log.warning("circuit_open", tool=tool_name)
            raise ToolCircuitOpenError(tool_name)

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                result = await fn(**kwargs)
                self._record_success(tool_name)
                return result
            except (ToolCallError, ToolCircuitOpenError):
                raise  # don't retry our own exceptions
            except Exception as exc:
                last_exc = exc
                delay = self.base_delay * (2 ** attempt)
                log.warning(
                    "tool_retry",
                    tool=tool_name,
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(exc),
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(delay)

        self._record_failure(tool_name)
        raise ToolCallMaxRetriesError(tool_name, self.max_retries) from last_exc

    # ── Internal ───────────────────────────────────────────────────────────────

    def _is_circuit_open(self, tool_name: str) -> bool:
        opened_at = self._circuit_opened_at.get(tool_name)
        if opened_at is None:
            return False
        if time.monotonic() - opened_at > self.circuit_reset_after:
            # half-open: allow one trial
            del self._circuit_opened_at[tool_name]
            self._consecutive_failures[tool_name] = 0
            return False
        return True

    def _record_success(self, tool_name: str) -> None:
        self._consecutive_failures[tool_name] = 0
        self._circuit_opened_at.pop(tool_name, None)

    def _record_failure(self, tool_name: str) -> None:
        self._consecutive_failures[tool_name] += 1
        if self._consecutive_failures[tool_name] >= self.circuit_threshold:
            self._circuit_opened_at[tool_name] = time.monotonic()
            log.error("circuit_tripped", tool=tool_name)
