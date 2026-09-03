"""Local MCP Client — P1 implementation.

P1: tools are registered as local async Python functions.
     Interface is identical to what a real MCP server client would expose,
     so swapping to stdio/HTTP MCP in later phases is a one-line change.

Interface:
    client = LocalMCPClient()
    client.register(WEB_SEARCH, search_fn)
    tools = await client.list_tools()         # → list[ToolDefinition]
    result = await client.call_tool("web_search", {"query": "..."})  # → ToolResult
"""

from __future__ import annotations

import time
from typing import Any, Callable, Coroutine

from deepresearch.common.exceptions import ToolCallError, ToolCircuitOpenError
from deepresearch.common.logging import get_logger
from deepresearch.mcp.retry_policy import RetryPolicy
from deepresearch.mcp.tool_schema import ToolDefinition
from deepresearch.observability.tracer import get_tracer
from deepresearch.schemas.models import EventType, ToolResult

log = get_logger("mcp.client")

AsyncToolFn = Callable[..., Coroutine[Any, Any, Any]]


class LocalMCPClient:
    """P1 tool registry — local functions behind the MCP interface."""

    def __init__(
        self,
        run_id: str,
        retry_policy: RetryPolicy | None = None,
        fallback_map: dict[str, str] | None = None,
    ) -> None:
        self.run_id = run_id
        self._retry = retry_policy or RetryPolicy()
        self._tools: dict[str, tuple[ToolDefinition, AsyncToolFn]] = {}
        self._tracer = get_tracer()
        # P5: primary → fallback tool name mapping for circuit-breaker degradation
        self._fallback_map: dict[str, str] = fallback_map or {}

    def register(self, defn: ToolDefinition, fn: AsyncToolFn) -> None:
        self._tools[defn.name] = (defn, fn)
        log.info("tool_registered", name=defn.name)

    async def list_tools(self) -> list[ToolDefinition]:
        return [defn for defn, _ in self._tools.values()]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name not in self._tools:
            return ToolResult(
                call_id="", tool_name=name, success=False,
                error=f"Unknown tool: {name}"
            )

        defn, fn = self._tools[name]
        t0 = time.monotonic()

        with self._tracer.span(
            EventType.TOOL_CALL, self.run_id, tool=name, args=arguments
        ) as span:
            try:
                output = await self._retry.execute(name, fn, **arguments)
                duration_ms = (time.monotonic() - t0) * 1000
                result = ToolResult(
                    call_id=span.event_id,
                    tool_name=name,
                    success=True,
                    output=output,
                    duration_ms=duration_ms,
                )
                self._tracer.emit(
                    EventType.TOOL_RESULT, self.run_id,
                    tool=name, success=True, duration_ms=duration_ms,
                )
                return result

            except ToolCircuitOpenError as exc:
                duration_ms = (time.monotonic() - t0) * 1000
                self._tracer.emit(
                    EventType.TOOL_CIRCUIT_OPEN, self.run_id,
                    tool=name, duration_ms=duration_ms,
                )
                # P5: try fallback tool before giving up
                fallback_name = self._fallback_map.get(name)
                if fallback_name and fallback_name in self._tools:
                    log.info("tool_fallback_attempt", primary=name, fallback=fallback_name)
                    self._tracer.emit(
                        EventType.TOOL_RESULT, self.run_id,
                        tool=name, success=False, fallback=fallback_name,
                    )
                    _, fallback_fn = self._tools[fallback_name]
                    try:
                        fb_output = await self._retry.execute(
                            fallback_name, fallback_fn, **arguments
                        )
                        fb_duration = (time.monotonic() - t0) * 1000
                        self._tracer.emit(
                            EventType.TOOL_RESULT, self.run_id,
                            tool=fallback_name, success=True,
                            via_fallback=True, duration_ms=fb_duration,
                        )
                        return ToolResult(
                            call_id=span.event_id,
                            tool_name=fallback_name,
                            success=True,
                            output=fb_output,
                            duration_ms=fb_duration,
                        )
                    except Exception as fb_exc:
                        log.error("tool_fallback_failed", fallback=fallback_name, error=str(fb_exc))
                        return ToolResult(
                            call_id=span.event_id, tool_name=name,
                            success=False, error=f"primary+fallback both failed: {fb_exc}",
                            duration_ms=(time.monotonic() - t0) * 1000,
                        )
                return ToolResult(
                    call_id=span.event_id,
                    tool_name=name,
                    success=False,
                    error=str(exc),
                    duration_ms=duration_ms,
                )
            except ToolCallError as exc:
                duration_ms = (time.monotonic() - t0) * 1000
                self._tracer.emit(
                    EventType.TOOL_RESULT, self.run_id,
                    tool=name, success=False, error=str(exc), duration_ms=duration_ms,
                )
                return ToolResult(
                    call_id=span.event_id,
                    tool_name=name,
                    success=False,
                    error=str(exc),
                    duration_ms=duration_ms,
                )
