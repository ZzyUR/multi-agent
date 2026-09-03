"""Unified data contracts for the entire DeepResearch system."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


# ── Enums ──────────────────────────────────────────────────────────────────────

class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStatus(StrEnum):
    PENDING = "pending"
    INTENT = "intent"       # clarifying user intent
    PLANNING = "planning"   # building task tree
    RUNNING = "running"     # workers executing
    SYNTHESIZING = "synthesizing"
    CITING = "citing"       # citation agent verifying
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventType(StrEnum):
    RUN_START = "run_start"
    RUN_END = "run_end"
    INTENT_CLARIFY = "intent_clarify"
    PLAN_START = "plan_start"
    PLAN_DONE = "plan_done"
    TASK_DISPATCH = "task_dispatch"
    TASK_START = "task_start"
    TASK_DONE = "task_done"
    TASK_FAILED = "task_failed"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_RETRY = "tool_retry"
    TOOL_CIRCUIT_OPEN = "tool_circuit_open"
    CONTEXT_COMPRESS = "context_compress"
    MEMORY_RECALL = "memory_recall"
    MEMORY_STORE = "memory_store"
    FILE_WRITE = "file_write"
    FILE_READ = "file_read"
    CITATION_CHECK = "citation_check"
    CHECKPOINT = "checkpoint"
    HUMAN_INTERVENE = "human_intervene"
    SYNTHESIZE = "synthesize"


# ── Core domain models ──────────────────────────────────────────────────────────

class Source(BaseModel):
    """A web source fetched during research."""
    source_id: str = Field(default_factory=_uid)
    run_id: str
    task_id: str
    url: str
    title: str = ""
    snippet: str = ""          # short excerpt for Lead context
    content_path: str = ""     # path in VFS where full text is stored
    fetched_at: datetime = Field(default_factory=_now)


class Finding(BaseModel):
    """A structured finding produced by a research worker."""
    finding_id: str = Field(default_factory=_uid)
    task_id: str
    run_id: str
    summary: str               # short summary returned to Lead
    key_points: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    content_path: str = ""     # path in VFS where full finding text lives
    created_at: datetime = Field(default_factory=_now)


class Task(BaseModel):
    """A research subtask dispatched to a worker agent."""
    task_id: str = Field(default_factory=_uid)
    run_id: str
    parent_task_id: str | None = None
    query: str                 # the sub-question to research
    depth: int = 0             # depth in the task tree
    status: TaskStatus = TaskStatus.PENDING
    worker_id: str | None = None
    finding: Finding | None = None
    created_at: datetime = Field(default_factory=_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class ResearchRun(BaseModel):
    """Top-level research session."""
    run_id: str = Field(default_factory=_uid)
    question: str
    profile: str = "standard"  # fast / standard / deep
    status: RunStatus = RunStatus.PENDING
    # resolved limits (from profile + env overrides)
    max_depth: int = 2
    max_breadth: int = 4
    max_total_workers: int = 10
    max_tokens_budget: int = 150000
    tokens_used: int = 0
    total_workers_spawned: int = 0
    created_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None
    report_path: str | None = None  # path in VFS


# ── LLM messaging ──────────────────────────────────────────────────────────────

class ToolCall(BaseModel):
    """An LLM-requested tool call (Function Calling)."""
    call_id: str = Field(default_factory=_uid)
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Result of executing a tool call."""
    call_id: str
    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0


class Message(BaseModel):
    """A single message in an LLM conversation."""
    role: str                           # system | user | assistant | tool
    content: str | list[dict[str, Any]]
    name: str | None = None             # for tool role messages
    tool_call_id: str | None = None     # for tool role messages
    tool_calls: list[dict[str, Any]] | None = None  # raw from LLM response


# ── Observability ──────────────────────────────────────────────────────────────

class TraceEvent(BaseModel):
    """A single structured trace event."""
    event_id: str = Field(default_factory=_uid)
    run_id: str
    agent_id: str | None = None
    parent_event_id: str | None = None
    event_type: str
    timestamp: datetime = Field(default_factory=_now)
    duration_ms: float | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
