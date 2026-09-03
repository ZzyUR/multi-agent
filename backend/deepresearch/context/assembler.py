"""Context Assembler — stable-prefix ordering for prompt-cache efficiency.

Design:
  • Stable (slow-changing) content goes at the TOP of the message list so the
    OpenAI/Bailian prompt cache can reuse the KV cache across consecutive turns.
  • Pinned content is marked with metadata and is never removed by compaction.
  • Volatile content (tool outputs, mid-turn chat) goes at the BOTTOM.

Stable ordering (index → role):
  0  system  — research persona + output format (PINNED, never changes per run)
  1  user    — research question (PINNED)
  2+ assistant/tool/user — ReAct messages (volatile, subject to compaction)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from deepresearch.schemas.models import Message


# Sentinel value stored in message metadata to mark pinned entries
_PINNED = "__pinned__"


@dataclass
class AssembledContext:
    """Holds the ordered list of messages to pass to the model, plus stats."""

    messages: list[Message]
    pinned_count: int = 0
    volatile_count: int = 0
    estimated_tokens: int = 0  # rough estimate: 4 chars ≈ 1 token

    def total(self) -> int:
        return self.pinned_count + self.volatile_count


class ContextAssembler:
    """Builds a message list with stable prefix / volatile suffix ordering.

    Usage:
        assembler = ContextAssembler(system_prompt, user_question)
        for msg in react_messages:
            assembler.add_volatile(msg)
        ctx = assembler.assemble()
        model.chat(ctx.messages)
    """

    def __init__(self, system_prompt: str, user_question: str) -> None:
        self._pinned: list[Message] = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_question),
        ]
        self._volatile: list[Message] = []

    # ── Mutation ──────────────────────────────────────────────────────────────

    def add_volatile(self, msg: Message) -> None:
        """Append a ReAct message (assistant thought, tool call, tool result)."""
        self._volatile.append(msg)

    def add_volatile_batch(self, msgs: list[Message]) -> None:
        self._volatile.extend(msgs)

    def replace_volatile(self, msgs: list[Message]) -> None:
        """Swap entire volatile section — used by compaction."""
        self._volatile = list(msgs)

    def volatile_snapshot(self) -> list[Message]:
        return list(self._volatile)

    # ── Assembly ─────────────────────────────────────────────────────────────

    def assemble(self) -> AssembledContext:
        all_msgs = self._pinned + self._volatile
        raw_text = "".join(
            (m.content or "") + "".join(
                tc.get("function", {}).get("arguments", "")
                for tc in (m.tool_calls or [])
            )
            for m in all_msgs
        )
        est_tokens = max(1, len(raw_text) // 4)
        return AssembledContext(
            messages=all_msgs,
            pinned_count=len(self._pinned),
            volatile_count=len(self._volatile),
            estimated_tokens=est_tokens,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def volatile_len(self) -> int:
        return len(self._volatile)

    def estimated_tokens(self) -> int:
        return self.assemble().estimated_tokens
