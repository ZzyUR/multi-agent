"""Five-layer context compaction cascade.

Layers (cheap → expensive, triggered in order):

  L1 — Tool-output truncation
       Any single tool-result message > TOOL_RESULT_CHAR_LIMIT chars is
       truncated to the first TOOL_RESULT_CHAR_LIMIT chars + a note.
       Threshold: any message exceeds the limit.

  L2 — Early search pruning
       Older web_search results beyond KEEP_RECENT_SEARCHES are collapsed
       to a one-line placeholder.
       Threshold: volatile message count > L2_VOLATILE_THRESHOLD.

  L3 — Message merging
       Consecutive one-liner assistant messages (pure reasoning, no tool
       calls, < MERGE_CHAR_LIMIT chars) are merged into a single message
       so the cache prefix stays stable.
       Threshold: volatile message count > L3_VOLATILE_THRESHOLD.

  L4 — History folding (window pressure)
       When estimated tokens > L4_TOKEN_THRESHOLD (85% of MODEL_MAX_TOKENS),
       fold the entire volatile history into a single summary message.
       A memory.consolidate() call is triggered so nothing is lost.
       Threshold: estimated_tokens > L4_TOKEN_THRESHOLD.

  L5 — Semantic compression (last resort)
       When even L4 didn't help (e.g. remaining messages still large),
       produce a compact JSON skeleton of the research so far and replace
       the volatile section entirely.
       Threshold: estimated_tokens > L5_TOKEN_THRESHOLD after L4.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from deepresearch.common.logging import get_logger
from deepresearch.schemas.models import EventType, Message

if TYPE_CHECKING:
    from deepresearch.context.assembler import ContextAssembler
    from deepresearch.memory.base import MemoryService
    from deepresearch.observability.tracer import Tracer

log = get_logger("context.compaction")

# ── Thresholds ────────────────────────────────────────────────────────────────

MODEL_MAX_TOKENS = 128_000          # qwen-plus context window
TOOL_RESULT_CHAR_LIMIT = 6_000      # L1: max chars kept in a single tool result
KEEP_RECENT_SEARCHES = 3            # L2: keep only the N most recent search rounds
L2_VOLATILE_THRESHOLD = 12          # L2: start pruning after this many volatile msgs
L3_VOLATILE_THRESHOLD = 10          # L3: start merging after this many volatile msgs
MERGE_CHAR_LIMIT = 400              # L3: only merge short assistant messages
L4_TOKEN_THRESHOLD = int(MODEL_MAX_TOKENS * 0.85)   # ~108 800 tokens
L5_TOKEN_THRESHOLD = int(MODEL_MAX_TOKENS * 0.95)   # ~121 600 tokens


# ── Public API ────────────────────────────────────────────────────────────────

class CompactionResult:
    def __init__(
        self,
        layers_applied: list[str],
        tokens_before: int,
        tokens_after: int,
    ) -> None:
        self.layers_applied = layers_applied
        self.tokens_before = tokens_before
        self.tokens_after = tokens_after
        self.saved = tokens_before - tokens_after

    def __bool__(self) -> bool:
        return bool(self.layers_applied)


async def compact(
    assembler: "ContextAssembler",
    run_id: str,
    tracer: "Tracer | None" = None,
    memory: "MemoryService | None" = None,
    *,
    model_client=None,           # required for L4/L5 (summarisation calls)
) -> CompactionResult:
    """Run the cascade in order and return what happened."""
    ctx_before = assembler.assemble()
    tokens_before = ctx_before.estimated_tokens
    layers: list[str] = []

    # L1 — truncate oversized tool results
    if _apply_l1(assembler):
        layers.append("L1:tool_truncate")
        log.info("compaction_l1", run_id=run_id)

    # L2 — prune old search results
    if assembler.volatile_len > L2_VOLATILE_THRESHOLD:
        if _apply_l2(assembler):
            layers.append("L2:search_prune")
            log.info("compaction_l2", run_id=run_id)

    # L3 — merge small consecutive assistant messages
    if assembler.volatile_len > L3_VOLATILE_THRESHOLD:
        if _apply_l3(assembler):
            layers.append("L3:msg_merge")
            log.info("compaction_l3", run_id=run_id)

    # L4 — fold history when approaching context limit
    ctx_now = assembler.assemble()
    if ctx_now.estimated_tokens > L4_TOKEN_THRESHOLD and model_client:
        await _apply_l4(assembler, model_client, memory)
        layers.append("L4:history_fold")
        log.info("compaction_l4", run_id=run_id, tokens=ctx_now.estimated_tokens)

    # L5 — semantic compression if still too large
    ctx_now = assembler.assemble()
    if ctx_now.estimated_tokens > L5_TOKEN_THRESHOLD and model_client:
        await _apply_l5(assembler, model_client)
        layers.append("L5:semantic_compress")
        log.info("compaction_l5", run_id=run_id)

    ctx_after = assembler.assemble()
    result = CompactionResult(layers, tokens_before, ctx_after.estimated_tokens)

    if layers and tracer:
        tracer.emit(
            EventType.CONTEXT_COMPRESS,
            run_id,
            layers=layers,
            tokens_before=tokens_before,
            tokens_after=ctx_after.estimated_tokens,
            saved=result.saved,
        )

    return result


# ── Layer implementations ─────────────────────────────────────────────────────

def _apply_l1(assembler: "ContextAssembler") -> bool:
    """Truncate tool-result messages that exceed TOOL_RESULT_CHAR_LIMIT."""
    msgs = assembler.volatile_snapshot()
    changed = False
    new_msgs: list[Message] = []
    for msg in msgs:
        if msg.role == "tool" and msg.content and len(msg.content) > TOOL_RESULT_CHAR_LIMIT:
            truncated = msg.content[:TOOL_RESULT_CHAR_LIMIT]
            note = f"\n\n[...内容已截断，超出 {TOOL_RESULT_CHAR_LIMIT} 字符限制]"
            new_msg = msg.model_copy(update={"content": truncated + note})
            new_msgs.append(new_msg)
            changed = True
        else:
            new_msgs.append(msg)
    if changed:
        assembler.replace_volatile(new_msgs)
    return changed


def _apply_l2(assembler: "ContextAssembler") -> bool:
    """Collapse older web_search result messages, keep KEEP_RECENT_SEARCHES recent ones."""
    msgs = assembler.volatile_snapshot()
    # Identify tool-result messages that are web_search results
    search_result_indices = [
        i for i, m in enumerate(msgs)
        if m.role == "tool" and m.name == "web_search"
    ]
    if len(search_result_indices) <= KEEP_RECENT_SEARCHES:
        return False

    to_collapse = set(search_result_indices[:-KEEP_RECENT_SEARCHES])
    new_msgs: list[Message] = []
    for i, msg in enumerate(msgs):
        if i in to_collapse:
            new_msgs.append(Message(
                role="tool",
                tool_call_id=msg.tool_call_id,
                name=msg.name,
                content="[搜索结果已折叠 — 内容已存入向量库]",
            ))
        else:
            new_msgs.append(msg)
    assembler.replace_volatile(new_msgs)
    return True


def _apply_l3(assembler: "ContextAssembler") -> bool:
    """Merge consecutive short assistant-only messages."""
    msgs = assembler.volatile_snapshot()
    new_msgs: list[Message] = []
    i = 0
    changed = False
    while i < len(msgs):
        msg = msgs[i]
        if (
            msg.role == "assistant"
            and not msg.tool_calls
            and msg.content
            and len(msg.content) < MERGE_CHAR_LIMIT
        ):
            # Accumulate consecutive short assistant messages
            buf = [msg.content]
            j = i + 1
            while (
                j < len(msgs)
                and msgs[j].role == "assistant"
                and not msgs[j].tool_calls
                and msgs[j].content
                and len(msgs[j].content) < MERGE_CHAR_LIMIT
            ):
                buf.append(msgs[j].content)
                j += 1
            if j > i + 1:
                merged = "\n\n".join(buf)
                new_msgs.append(Message(role="assistant", content=merged))
                changed = True
                i = j
                continue
        new_msgs.append(msg)
        i += 1
    if changed:
        assembler.replace_volatile(new_msgs)
    return changed


async def _apply_l4(
    assembler: "ContextAssembler",
    model_client,
    memory: "MemoryService | None",
) -> None:
    """Fold volatile history into a summary message via model call."""
    msgs = assembler.volatile_snapshot()
    if not msgs:
        return

    # Build a compact text representation for summarisation
    history_text = _msgs_to_text(msgs)

    summary_prompt = [
        Message(
            role="user",
            content=(
                "下面是一段研究对话历史（工具调用 + 发现）。"
                "请用中文写一段 300 字以内的结构化摘要，保留：\n"
                "  1. 已搜索的关键词\n"
                "  2. 核心发现（含来源 URL）\n"
                "  3. 待解决的研究缺口\n\n"
                f"---\n{history_text[:12000]}\n---\n\n摘要："
            ),
        )
    ]
    summary_text, _, _ = await model_client.chat(summary_prompt, max_tokens=512)

    if memory:
        memory.consolidate()

    assembler.replace_volatile([
        Message(
            role="assistant",
            content=f"[历史折叠摘要]\n\n{summary_text or '（摘要生成失败）'}",
        )
    ])


async def _apply_l5(assembler: "ContextAssembler", model_client) -> None:
    """Semantic compression — produce a minimal JSON skeleton."""
    msgs = assembler.volatile_snapshot()
    if not msgs:
        return

    history_text = _msgs_to_text(msgs)

    skeleton_prompt = [
        Message(
            role="user",
            content=(
                "将以下研究对话压缩为 JSON，格式：\n"
                '{"queries":["..."],"key_findings":["..."],"sources":["url1","url2"],'
                '"gaps":["..."]}\n\n'
                f"---\n{history_text[:8000]}\n---\n\n只返回JSON："
            ),
        )
    ]
    skeleton_text, _, _ = await model_client.chat(skeleton_prompt, max_tokens=512)

    assembler.replace_volatile([
        Message(
            role="assistant",
            content=f"[语义压缩骨架]\n\n{skeleton_text or '{}'}",
        )
    ])


# ── Utilities ─────────────────────────────────────────────────────────────────

def _msgs_to_text(msgs: list[Message]) -> str:
    parts = []
    for m in msgs:
        role_tag = f"[{m.role.upper()}]"
        content = m.content or ""
        if m.tool_calls:
            calls = ", ".join(
                f"{tc['function']['name']}({tc['function']['arguments'][:80]})"
                for tc in m.tool_calls
                if isinstance(tc, dict)
            )
            content = f"<tool_calls: {calls}>"
        parts.append(f"{role_tag} {content}")
    return "\n\n".join(parts)
