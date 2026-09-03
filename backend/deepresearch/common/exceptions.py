"""Base exception hierarchy for DeepResearch."""


class DeepResearchError(Exception):
    """Root exception — catch this to handle all project errors."""

    def __init__(self, message: str, *, code: str = "INTERNAL_ERROR") -> None:
        super().__init__(message)
        self.code = code


class ConfigError(DeepResearchError):
    """Misconfigured settings or missing required env vars."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="CONFIG_ERROR")


# ── Tool / MCP errors ──────────────────────────────────────────────────────────

class ToolCallError(DeepResearchError):
    """A single tool call failed."""

    def __init__(self, tool_name: str, reason: str) -> None:
        super().__init__(f"Tool '{tool_name}' failed: {reason}", code="TOOL_CALL_ERROR")
        self.tool_name = tool_name
        self.reason = reason


class ToolCallMaxRetriesError(ToolCallError):
    """Tool call exhausted all retry attempts."""

    def __init__(self, tool_name: str, attempts: int) -> None:
        super().__init__(tool_name, f"max retries ({attempts}) exceeded")
        self.code = "TOOL_MAX_RETRIES"
        self.attempts = attempts


class ToolCircuitOpenError(ToolCallError):
    """Tool is circuit-broken for this run — skip and re-plan."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(tool_name, "circuit breaker open")
        self.code = "TOOL_CIRCUIT_OPEN"


# ── Agent / orchestration errors ───────────────────────────────────────────────

class AgentBudgetExceededError(DeepResearchError):
    """Token budget or worker count hard limit hit — force wrap-up."""

    def __init__(self, limit_name: str, value: int, limit: int) -> None:
        super().__init__(
            f"Hard limit '{limit_name}' exceeded: {value} > {limit}",
            code="BUDGET_EXCEEDED",
        )
        self.limit_name = limit_name
        self.value = value
        self.limit = limit


class AgentMaxDepthError(DeepResearchError):
    """Research iteration depth limit reached."""

    def __init__(self, depth: int) -> None:
        super().__init__(f"Max research depth {depth} reached", code="MAX_DEPTH")
        self.depth = depth


# ── Checkpoint errors ──────────────────────────────────────────────────────────

class CheckpointError(DeepResearchError):
    """Failed to save or restore a checkpoint."""

    def __init__(self, run_id: str, reason: str) -> None:
        super().__init__(
            f"Checkpoint error for run '{run_id}': {reason}", code="CHECKPOINT_ERROR"
        )
        self.run_id = run_id
