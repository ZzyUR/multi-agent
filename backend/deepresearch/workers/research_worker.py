"""Research Worker — single-agent ReAct loop (Phase 1 → P3 升级).

P3 关键变化：
  1. fetch_page → chunk → 存 Chroma，返回内容摘要而非全文
  2. vector_search 工具：从 Chroma 检索最相关片段
  3. 研究完成后，完整发现写入 VFS findings/{task_id}.md
  4. 只返回简短 summary + content_path 给 Lead（上下文不爆）
  5. Episodic 记忆联动去重：同一 URL 不重复抓取
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime

from deepresearch.common.logging import get_logger
from deepresearch.context.assembler import ContextAssembler
from deepresearch.context.compaction import compact
from deepresearch.filesystem.virtual_fs import VirtualFS
from deepresearch.mcp.client import LocalMCPClient
from deepresearch.mcp.tool_schema import FETCH_PAGE, VECTOR_SEARCH, WEB_SEARCH
from deepresearch.memory.base import MemoryService
from deepresearch.model_client import BaseModelClient
from deepresearch.observability.tracer import Tracer
from deepresearch.rag.retriever import ChromaRetriever
from deepresearch.rag.web_search import fetch_page, get_search_backend
from deepresearch.schemas.models import (
    EventType,
    Finding,
    Message,
    Source,
)

log = get_logger("worker.research")

# ── Prompts ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
你是一个专业的深度研究助手（Deep Research Agent）。

## 任务
用户给你一个研究问题。你需要：
1. 使用 web_search 搜索相关信息（多次，不同角度）
2. 对重要搜索结果使用 fetch_page 获取完整内容（内容会自动存入知识库）
3. 使用 vector_search 从知识库中检索与问题最相关的片段
4. 综合信息，生成一份结构化、带引用的研究发现

## 搜索策略
- 先宏观后具体：先搜概述，再搜细节，至少搜 3-4 个不同角度
- **必须用中文搜索关键词**（中文资料更丰富；英文查询经常无结果）
- **充分利用 web_search 返回的标题和摘要**——摘要里的数字、事实、机构名即使打不开原网页也要采用并记录来源
- 对 2-3 个最相关 URL 尝试 fetch_page；若失败（403/超时）不要纠结，直接用搜索摘要里的信息继续
- 用 vector_search 检索已抓取内容的支撑证据
- 重点提取**可量化的数据**：市场规模、增长率、份额、数量、金额、时间点等

## 输出格式（Markdown）
最终输出必须包含：
# [标题]
## 执行摘要
## 主要发现
### 1. ...
### 2. ...
## 来源
[1] 标题 — URL

关键：每条论断必须有来源引用 [n]。\
"""

_SYNTHESIS_PROMPT = """\
根据以上研究过程，请生成一份完整的研究发现报告（Markdown 格式）。
必须包含：执行摘要、主要发现（分章节）、来源列表。
每个关键论断需要来源引用 [n]。\
"""

MAX_PAGE_CHARS_IN_CONTEXT = 2000  # 放进对话的页面内容上限（其余存 VFS）


class ResearchWorker:
    def __init__(
        self,
        worker_id: str,
        run_id: str,
        model_client: BaseModelClient,
        mcp_client: LocalMCPClient,
        tracer: Tracer,
        max_steps: int = 12,
        vfs: VirtualFS | None = None,
        retriever: ChromaRetriever | None = None,
        memory: MemoryService | None = None,
        task_id: str | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.run_id = run_id
        self.model = model_client
        self.mcp = mcp_client
        self.tracer = tracer
        self.max_steps = max_steps
        self.vfs = vfs
        self.retriever = retriever
        self.memory = memory
        self.task_id = task_id or str(uuid.uuid4())
        self.tokens_used = 0
        self._collected_sources: list[dict] = []

    async def research(self, query: str) -> Finding:
        self.tracer.emit(
            EventType.TASK_START, self.run_id,
            agent_id=self.worker_id, query=query,
        )

        tools_schema = [t.to_openai_schema() for t in await self.mcp.list_tools()]

        # P4: use ContextAssembler for stable-prefix ordering
        assembler = ContextAssembler(
            system_prompt=_SYSTEM_PROMPT,
            user_question=f"请深入研究以下问题：\n\n{query}",
        )  

        steps = 0
        final_text: str | None = None

        while steps < self.max_steps:
            steps += 1
            log.info("react_step", step=steps, worker=self.worker_id)

            # P4: run compaction cascade before every model call
            compaction = await compact(
                assembler,
                run_id=self.run_id,
                tracer=self.tracer,
                memory=self.memory,
                model_client=self.model,
            )
            if compaction:
                log.info(
                    "context_compacted",
                    worker=self.worker_id,
                    layers=compaction.layers_applied,
                    saved_tokens=compaction.saved,
                )

            ctx = assembler.assemble()
            with self.tracer.span(EventType.TASK_START, self.run_id,
                                  agent_id=self.worker_id, step=steps):
                text, tool_calls, tokens = await self.model.chat(
                    ctx.messages, tools=tools_schema, max_tokens=4096
                )
            self.tokens_used += tokens

            if tool_calls:
                assembler.add_volatile(Message(
                    role="assistant",
                    content=text or "",
                    tool_calls=[
                        {
                            "id": tc.call_id,
                            "type": "function",
                            "function": {
                                "name": tc.tool_name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in tool_calls
                    ],
                ))
                for tc in tool_calls:
                    result = await self.mcp.call_tool(tc.tool_name, tc.arguments)
                    if result.success:
                        if tc.tool_name == "web_search" and isinstance(result.output, list):
                            for item in result.output:
                                if isinstance(item, dict) and "url" in item:
                                    self._collected_sources.append(item)
                        content = _format_tool_output(tc.tool_name, result.output)
                    else:
                        content = f"工具调用失败: {result.error}"

                    assembler.add_volatile(Message(
                        role="tool",
                        tool_call_id=tc.call_id,
                        name=tc.tool_name,
                        content=content,
                    ))
            else:
                assembler.add_volatile(Message(role="assistant", content=text or ""))
                if text and _is_final_report(text):
                    final_text = text
                    log.info("final_report_detected", step=steps)
                    break

        if not final_text:
            log.info("force_synthesis", steps=steps)
            final_text = await self._force_synthesis(assembler.assemble().messages)

        finding = self._build_finding(final_text, query)

        # ── P3: 完整发现写入 VFS ──────────────────────────────────────────────
        if self.vfs:
            content_path = self.vfs.write_finding(self.task_id, final_text)
            finding.content_path = content_path
            log.info("vfs_finding_written", path=content_path)

        # ── P3: 蒸馏一条 semantic 事实 ────────────────────────────────────────
        if self.memory:
            self.memory.episodic.record_finding(
                task_id=self.task_id,
                summary=finding.summary,
                source_count=len(finding.source_ids),
            )

        self.tracer.emit(
            EventType.TASK_DONE, self.run_id,
            agent_id=self.worker_id, tokens=self.tokens_used,
            finding_id=finding.finding_id,
            content_path=finding.content_path,
        )
        return finding

    async def _force_synthesis(self, messages: list[Message]) -> str:
        text, _, tokens = await self.model.chat(
            messages + [Message(role="user", content=_SYNTHESIS_PROMPT)],
            max_tokens=4096,
        )
        self.tokens_used += tokens
        return text or "（报告生成失败）"

    def _build_finding(self, report_text: str, query: str) -> Finding:
        source_ids = [s.get("url", "") for s in self._collected_sources]
        urls_in_report = re.findall(r"https?://[^\s\)>\]\"']+", report_text)
        all_ids = list(dict.fromkeys(source_ids + urls_in_report))[:20]

        lines = report_text.strip().split("\n")
        summary_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                summary_lines.append(stripped)
            if len(summary_lines) >= 3:
                break
        summary = " ".join(summary_lines)[:500]

        return Finding(
            run_id=self.run_id,
            task_id=self.task_id,
            summary=summary,
            key_points=[],
            source_ids=all_ids,
            content_path="",
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _format_tool_output(tool_name: str, output: object) -> str:
    if tool_name == "web_search" and isinstance(output, list):
        lines = ["搜索结果：\n"]
        for i, item in enumerate(output, 1):
            if isinstance(item, dict):
                lines.append(
                    f"[{i}] {item.get('title','')}\n"
                    f"    URL: {item.get('url','')}\n"
                    f"    {item.get('snippet','')}\n"
                )
        return "\n".join(lines)
    if tool_name == "fetch_page" and isinstance(output, dict):
        return (
            f"已抓取并存入知识库：{output.get('url','')}\n"
            f"内容摘要（前 {MAX_PAGE_CHARS_IN_CONTEXT} 字）：\n"
            f"{output.get('preview','')}"
        )
    if tool_name == "vector_search" and isinstance(output, list):
        lines = ["知识库检索结果：\n"]
        for i, hit in enumerate(output, 1):
            if isinstance(hit, dict):
                lines.append(
                    f"[{i}] 相关度 {hit.get('score',0):.2f} | {hit.get('url','')}\n"
                    f"    {hit.get('text','')[:300]}\n"
                )
        return "\n".join(lines)
    return str(output)


def _is_final_report(text: str) -> bool:
    has_heading = bool(re.search(r"^#{1,3}\s+\S", text, re.MULTILINE))
    has_sources = "来源" in text or "参考" in text or "[1]" in text or "http" in text
    return has_heading and has_sources and len(text) > 400


# ── Tool functions ─────────────────────────────────────────────────────────────

async def tool_web_search(query: str, max_results: int = 5) -> list[dict]:
    backend = get_search_backend()
    results = await backend.search(query, max_results=max_results)
    return [{"url": r.url, "title": r.title, "snippet": r.snippet} for r in results]


def _make_fetch_page_fn(
    retriever: ChromaRetriever | None,
    memory: MemoryService | None,
    task_id: str,
):
    async def tool_fetch_page(url: str) -> dict:
        """P3: fetch → chunk → Chroma, return preview (not full text)."""
        # Dedup via episodic memory
        if memory and memory.has_seen_url(url):
            log.info("fetch_dedup", url=url)
            return {"url": url, "preview": "[已抓取，跳过重复]", "chunks_added": 0}

        raw = await fetch_page(url)
        preview = raw[:MAX_PAGE_CHARS_IN_CONTEXT]

        # Store chunks in Chroma
        chunks_added = 0
        if retriever and raw.strip():
            chunks_added = retriever.add_page(url=url, text=raw, task_id=task_id)

        # Mark as seen in episodic memory
        if memory:
            memory.episodic.record_fetch(url=url, chars=len(raw), task_id=task_id)

        return {"url": url, "preview": preview, "chunks_added": chunks_added}

    return tool_fetch_page


def _make_vector_search_fn(retriever: ChromaRetriever | None, task_id: str):
    async def tool_vector_search(query: str, n_results: int = 5) -> list[dict]:
        if retriever is None:
            return [{"text": "向量库未初始化", "url": "", "score": 0}]
        return retriever.query(query_text=query, n_results=n_results, task_id=task_id)

    return tool_vector_search


# ── Factory ────────────────────────────────────────────────────────────────────

def build_mcp_client(
    run_id: str,
    retriever: ChromaRetriever | None = None,
    memory: MemoryService | None = None,
    task_id: str | None = None,
) -> LocalMCPClient:
    """Create and wire up an MCP client with all P3 tools registered."""
    from deepresearch.mcp.client import LocalMCPClient

    _task_id = task_id or str(uuid.uuid4())
    client = LocalMCPClient(run_id=run_id)
    client.register(WEB_SEARCH, tool_web_search)
    client.register(FETCH_PAGE, _make_fetch_page_fn(retriever, memory, _task_id))
    client.register(VECTOR_SEARCH, _make_vector_search_fn(retriever, _task_id))
    return client
