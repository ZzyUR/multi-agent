"""P4 context-engineering tests — offline CI, no API key required.

Coverage:
  - L1  tool output truncation
  - L2  search result pruning
  - L3  consecutive short assistant message merging
  - L4  history folding when context approaches limit
  - L5  semantic compression as last resort
  - Pinned content (system + user question) survives all compaction rounds
  - Cascade ordering: cheaper layers fire before expensive ones
  - Prompt cache hit rate property accessible on OpenAIModelClient
"""

from __future__ import annotations

import pytest

from deepresearch.context.assembler import ContextAssembler
from deepresearch.context.compaction import (
    KEEP_RECENT_SEARCHES,
    L2_VOLATILE_THRESHOLD,
    L3_VOLATILE_THRESHOLD,
    L4_TOKEN_THRESHOLD,
    L5_TOKEN_THRESHOLD,
    MERGE_CHAR_LIMIT,
    TOOL_RESULT_CHAR_LIMIT,
    compact,
)
from deepresearch.model_client import BaseModelClient, MockModelClient
from deepresearch.schemas.models import Message, ToolCall

# ── Helpers ────────────────────────────────────────────────────────────────────

_SYS = "You are a research assistant. (PINNED_SYSTEM)"
_Q = "What is the impact of quantum computing on cryptography? (PINNED_QUESTION)"


def _assembler() -> ContextAssembler:
    return ContextAssembler(system_prompt=_SYS, user_question=_Q)


def _search_msg(i: int) -> Message:
    return Message(
        role="tool",
        tool_call_id=f"call_{i}",
        name="web_search",
        content=f"搜索结果 {i}: some result content here",
    )


def _asst_msg(text: str = "思考中…") -> Message:
    return Message(role="assistant", content=text)


class _BigSummaryClient(BaseModelClient):
    """Returns a summary large enough that L5 still triggers after L4."""

    async def chat(
        self,
        messages: list[Message],
        *,
        tools=None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> tuple[str | None, list[ToolCall], int]:
        # Return a string that keeps estimated_tokens above L5_TOKEN_THRESHOLD
        summary = "大量研究发现内容。" * ((L5_TOKEN_THRESHOLD * 4 // 9) + 1000)
        return summary, [], 1000


# ── L1: Tool output truncation ─────────────────────────────────────────────────

async def test_l1_truncates_oversized_tool_result():
    asm = _assembler()
    big = "x" * (TOOL_RESULT_CHAR_LIMIT + 2000)
    asm.add_volatile(Message(role="tool", tool_call_id="tc1", name="fetch_page", content=big))

    result = await compact(asm, run_id="test-l1")

    assert "L1:tool_truncate" in result.layers_applied
    msgs = asm.volatile_snapshot()
    assert all(len(m.content or "") <= TOOL_RESULT_CHAR_LIMIT + 200 for m in msgs)
    assert "截断" in msgs[0].content


async def test_l1_does_not_fire_when_content_small():
    asm = _assembler()
    asm.add_volatile(Message(role="tool", tool_call_id="tc1", name="fetch_page", content="小内容"))

    result = await compact(asm, run_id="test-l1-noop")

    assert "L1:tool_truncate" not in result.layers_applied


# ── L2: Search result pruning ──────────────────────────────────────────────────

async def test_l2_collapses_old_search_results():
    asm = _assembler()
    # Need > L2_VOLATILE_THRESHOLD messages AND > KEEP_RECENT_SEARCHES search results
    for i in range(L2_VOLATILE_THRESHOLD + 1):
        asm.add_volatile(_search_msg(i))

    result = await compact(asm, run_id="test-l2")

    assert "L2:search_prune" in result.layers_applied
    msgs = asm.volatile_snapshot()
    collapsed = [m for m in msgs if m.content == "[搜索结果已折叠 — 内容已存入向量库]"]
    assert len(collapsed) > 0
    # Most recent KEEP_RECENT_SEARCHES must be intact
    recent = [m for m in msgs if m.name == "web_search" and m.content != "[搜索结果已折叠 — 内容已存入向量库]"]
    assert len(recent) == KEEP_RECENT_SEARCHES


async def test_l2_skips_when_few_search_results():
    asm = _assembler()
    # Fewer than L2_VOLATILE_THRESHOLD messages — L2 shouldn't fire
    for i in range(KEEP_RECENT_SEARCHES):
        asm.add_volatile(_search_msg(i))

    result = await compact(asm, run_id="test-l2-noop")

    assert "L2:search_prune" not in result.layers_applied


# ── L3: Message merging ────────────────────────────────────────────────────────

async def test_l3_merges_consecutive_short_assistant_messages():
    asm = _assembler()
    # Need volatile_len > L3_VOLATILE_THRESHOLD after adding assistant messages
    for i in range(L3_VOLATILE_THRESHOLD - 2):
        asm.add_volatile(_search_msg(i))
    # Add 3 short consecutive assistant messages to trigger merge
    asm.add_volatile(_asst_msg("思考A"))
    asm.add_volatile(_asst_msg("思考B"))
    asm.add_volatile(_asst_msg("思考C"))

    before_count = asm.volatile_len
    result = await compact(asm, run_id="test-l3")

    assert "L3:msg_merge" in result.layers_applied
    assert asm.volatile_len < before_count
    # Merged content should contain all three
    merged = next(
        m for m in asm.volatile_snapshot()
        if m.role == "assistant" and "思考A" in (m.content or "")
    )
    assert "思考B" in merged.content
    assert "思考C" in merged.content


async def test_l3_does_not_merge_long_assistant_messages():
    asm = _assembler()
    long_text = "x" * (MERGE_CHAR_LIMIT + 10)
    for _ in range(L3_VOLATILE_THRESHOLD + 1):
        asm.add_volatile(_asst_msg(long_text))

    result = await compact(asm, run_id="test-l3-long")

    assert "L3:msg_merge" not in result.layers_applied


# ── L4: History folding ────────────────────────────────────────────────────────

async def test_l4_folds_history_when_context_large():
    asm = _assembler()
    # estimated_tokens = len(text) // 4, need > L4_TOKEN_THRESHOLD
    chars_needed = L4_TOKEN_THRESHOLD * 4 + 4000
    asm.add_volatile(_asst_msg("研究发现：" + "a" * chars_needed))

    model = MockModelClient()
    result = await compact(asm, run_id="test-l4", model_client=model)

    assert "L4:history_fold" in result.layers_applied
    msgs = asm.volatile_snapshot()
    assert len(msgs) == 1
    assert "历史折叠摘要" in msgs[0].content


async def test_l4_skipped_without_model_client():
    asm = _assembler()
    chars_needed = L4_TOKEN_THRESHOLD * 4 + 4000
    asm.add_volatile(_asst_msg("a" * chars_needed))

    # No model_client — L4 must not fire
    result = await compact(asm, run_id="test-l4-nomodel", model_client=None)

    assert "L4:history_fold" not in result.layers_applied


# ── L5: Semantic compression ───────────────────────────────────────────────────

async def test_l5_fires_when_still_large_after_l4():
    asm = _assembler()
    chars_needed = L5_TOKEN_THRESHOLD * 4 + 4000
    asm.add_volatile(_asst_msg("研究内容：" + "b" * chars_needed))

    model = _BigSummaryClient()
    result = await compact(asm, run_id="test-l5", model_client=model)

    assert "L4:history_fold" in result.layers_applied
    assert "L5:semantic_compress" in result.layers_applied
    msgs = asm.volatile_snapshot()
    assert len(msgs) == 1
    assert "语义压缩骨架" in msgs[0].content


# ── Pinned content survival ────────────────────────────────────────────────────

async def test_pinned_content_survives_all_layers():
    asm = _assembler()

    # Trigger L1+L2+L3 with a rich volatile section
    for i in range(L2_VOLATILE_THRESHOLD + 1):
        asm.add_volatile(_search_msg(i))
        asm.add_volatile(Message(
            role="tool",
            tool_call_id=f"fetch_{i}",
            name="fetch_page",
            content="c" * (TOOL_RESULT_CHAR_LIMIT + 100),
        ))
    for _ in range(4):
        asm.add_volatile(_asst_msg("短思考"))

    result = await compact(asm, run_id="test-pinned")

    ctx = asm.assemble()
    assert ctx.messages[0].role == "system"
    assert ctx.messages[0].content == _SYS
    assert ctx.messages[1].role == "user"
    assert ctx.messages[1].content == _Q
    assert ctx.pinned_count == 2


async def test_pinned_content_survives_l4_fold():
    asm = _assembler()
    chars_needed = L4_TOKEN_THRESHOLD * 4 + 4000
    asm.add_volatile(_asst_msg("a" * chars_needed))

    model = MockModelClient()
    await compact(asm, run_id="test-pinned-l4", model_client=model)

    ctx = asm.assemble()
    assert ctx.messages[0].content == _SYS
    assert ctx.messages[1].content == _Q


# ── Cascade ordering ───────────────────────────────────────────────────────────

async def test_cascade_order_l1_before_l2():
    """L1 fires unconditionally; L2 checks volatile count after L1."""
    asm = _assembler()
    # Big tool result (L1 trigger) + many search results (L2 trigger)
    asm.add_volatile(Message(
        role="tool", tool_call_id="tc0", name="fetch_page",
        content="x" * (TOOL_RESULT_CHAR_LIMIT + 500),
    ))
    for i in range(L2_VOLATILE_THRESHOLD + 1):
        asm.add_volatile(_search_msg(i))

    result = await compact(asm, run_id="test-order")

    layers = result.layers_applied
    assert "L1:tool_truncate" in layers
    assert "L2:search_prune" in layers
    # L1 index must come before L2 index
    assert layers.index("L1:tool_truncate") < layers.index("L2:search_prune")


async def test_compaction_result_reports_token_savings():
    asm = _assembler()
    big = "x" * (TOOL_RESULT_CHAR_LIMIT + 2000)
    asm.add_volatile(Message(role="tool", tool_call_id="tc1", name="fetch_page", content=big))

    result = await compact(asm, run_id="test-savings")

    assert result.tokens_before > result.tokens_after
    assert result.saved > 0


async def test_no_compaction_returns_empty_layers():
    asm = _assembler()
    asm.add_volatile(_asst_msg("短消息"))

    result = await compact(asm, run_id="test-noop")

    assert result.layers_applied == []
    assert bool(result) is False  # CompactionResult.__bool__


# ── Prompt cache hit rate ──────────────────────────────────────────────────────

def test_openai_client_exposes_cache_hit_rate():
    from deepresearch.model_client import OpenAIModelClient
    client = OpenAIModelClient(api_key="fake", base_url="http://localhost", model="gpt-4")
    assert hasattr(client, "cache_hit_rate")
    assert client.cache_hit_rate == 0.0  # no calls yet → 0


def test_cache_hit_rate_computed_correctly():
    from deepresearch.model_client import OpenAIModelClient
    client = OpenAIModelClient(api_key="fake", base_url="http://localhost", model="gpt-4")
    # Simulate what the real client accumulates
    client._total_prompt_tokens = 1000
    client._cache_hits = 400
    assert client.cache_hit_rate == pytest.approx(0.4)


def test_cache_hit_rate_zero_when_no_prompt_tokens():
    from deepresearch.model_client import OpenAIModelClient
    client = OpenAIModelClient(api_key="fake", base_url="http://localhost", model="gpt-4")
    client._total_prompt_tokens = 0
    client._cache_hits = 0
    assert client.cache_hit_rate == 0.0
