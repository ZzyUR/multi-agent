"""VFS 权限控制 — 每个 Worker 只能写自己的文件，互不覆盖。

规则：
  - lead       → 可写 plan.md、report_draft.md；只读 findings/*
  - worker-xxx → 只可写 findings/{task_id}.md（自己的）
  - 任何人      → 可读所有文件
"""

from __future__ import annotations

from deepresearch.common.exceptions import DeepResearchError
from deepresearch.common.logging import get_logger

log = get_logger("filesystem.permissions")

_LEAD_WRITABLE = {"plan.md", "report_draft.md", "sources.jsonl"}


class PermissionDenied(DeepResearchError):
    def __init__(self, writer_id: str, path: str) -> None:
        super().__init__(
            f"'{writer_id}' is not allowed to write '{path}'",
            code="PERMISSION_DENIED",
        )


def check_write(writer_id: str, rel_path: str, task_id: str | None = None) -> None:
    """Raise PermissionDenied if writer cannot write to rel_path."""
    if writer_id == "lead":
        if rel_path not in _LEAD_WRITABLE:
            raise PermissionDenied(writer_id, rel_path)
        return

    if writer_id.startswith("worker-"):
        allowed = f"findings/{task_id}.md" if task_id else None
        if rel_path == allowed:
            return
        raise PermissionDenied(writer_id, rel_path)

    raise PermissionDenied(writer_id, rel_path)
