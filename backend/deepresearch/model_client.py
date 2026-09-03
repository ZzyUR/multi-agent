"""OpenAI-compatible model client with switchable Mock backend.

Usage:
    client = get_model_client()
    response = await client.chat(messages, tools=tools)

Set USE_MOCK_MODEL=true in .env to use MockModelClient (no API key needed).
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from deepresearch.config.settings import get_settings
from deepresearch.schemas.models import Message, ToolCall


# ── Abstract interface ─────────────────────────────────────────────────────────

class BaseModelClient(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> tuple[str | None, list[ToolCall], int]:
        """
        Returns:
            (text_content, tool_calls, tokens_used)
            text_content is None when the model returns only tool calls.
        """


# ── Real OpenAI-compatible client ──────────────────────────────────────────────

class OpenAIModelClient(BaseModelClient):
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        # Clash/v2ray proxies often break TLS-over-CONNECT for Chinese API endpoints.
        # Add the API host to NO_PROXY so httpx routes it directly.
        import os
        from urllib.parse import urlparse
        api_host = urlparse(base_url).hostname or ""
        no_proxy = os.environ.get("NO_PROXY", "")
        if api_host and api_host not in no_proxy:
            os.environ["NO_PROXY"] = f"{no_proxy},{api_host}".lstrip(",")

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._cache_hits: int = 0
        self._total_prompt_tokens: int = 0

    async def chat(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> tuple[str | None, list[ToolCall], int]:
        kwargs: dict[str, Any] = dict(
            model=self._model,
            messages=[m.model_dump(exclude_none=True) for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp: ChatCompletion = await self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        msg = choice.message
        tokens_used = resp.usage.total_tokens if resp.usage else 0

        # P4: track prompt cache hit tokens if the API returns them
        if resp.usage:
            usage = resp.usage
            # OpenAI / Bailian surface cache hits in prompt_tokens_details
            details = getattr(usage, "prompt_tokens_details", None)
            cached = getattr(details, "cached_tokens", 0) if details else 0
            if cached:
                self._cache_hits += cached
            self._total_prompt_tokens += getattr(usage, "prompt_tokens", 0)

        text = msg.content or None

        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(
                    ToolCall(call_id=tc.id, tool_name=tc.function.name, arguments=args)
                )

        return text, tool_calls, tokens_used

    @property
    def cache_hit_rate(self) -> float:
        """Fraction of prompt tokens served from cache (0.0 if unknown)."""
        if self._total_prompt_tokens == 0:
            return 0.0
        return self._cache_hits / self._total_prompt_tokens


# ── Mock client (offline / CI) ─────────────────────────────────────────────────

def _mock_extract_question(messages: "list[Message]") -> str:
    """Pull the research question from message history."""
    # Search system + user messages for an explicit 研究问题: marker
    for m in messages:
        content = m.content if isinstance(m.content, str) else ""
        for prefix in ("研究问题：", "问题：", "Question:"):
            if prefix in content:
                # Take only the first line after the prefix (stop at newline)
                after = content.split(prefix, 1)[-1].strip()
                return after.split("\n")[0].strip()[:60]
    # Fallback: first non-empty user message, first line only
    for m in messages:
        if m.role == "user":
            content = m.content if isinstance(m.content, str) else ""
            first_line = content.strip().split("\n")[0].strip()
            if first_line:
                return first_line[:60]
    return "该研究课题"


def _mock_topic(question: str) -> str:
    """Remove verb prefixes to get a clean noun topic."""
    for verb in ("分析", "研究", "调研", "梳理", "探讨", "总结", "调查", "评估"):
        question = question.replace(verb, "")
    return question.strip()[:25]


def _mock_plan_json(question: str) -> str:
    topic = _mock_topic(question)
    subtasks = [
        f"{topic}的市场规模与竞争格局",
        f"{topic}的核心技术路线与发展趋势",
        f"{topic}相关政策与监管环境",
        f"{topic}主要玩家战略及投资机会",
    ]
    return json.dumps(
        {"subtasks": subtasks[:3], "rationale": f"将'{topic}'拆解为市场、技术、政策三个独立可并行研究的维度"},
        ensure_ascii=False,
    )


def _mock_finding(question: str) -> str:
    topic = _mock_topic(question)
    return f"""# {topic} — 子课题研究发现

## 执行摘要
基于多来源信息收集，{topic}领域呈现高速增长态势，市场规模持续扩大，技术创新与政策支持共同驱动行业成长。[1]

## 主要发现

### 1. 市场现状
{topic}2024 年整体市场规模同比增速约 25%，头部企业 CR5 市场集中度超过 60%。[1][2]

### 2. 技术路线
核心技术路线日趋清晰，多项关键突破推动成本持续下降，国产替代进程加速。[3]

### 3. 政策环境
国家及地方层面持续出台支持政策，监管框架逐步完善，行业标准体系建设提速。[4]

## 来源

- [1] 行业研究报告 2025 — https://example.com/report1
- [2] 市场数据分析白皮书 — https://example.com/data2
- [3] 技术路线图 2025 — https://example.com/tech3
- [4] 政策汇编与解读 — https://example.com/policy4
"""


def _mock_report(question: str) -> str:
    topic = _mock_topic(question)
    return f"""# {question} — 深度研究报告

## 执行摘要

本报告基于多维度系统研究，对{topic}进行了全面分析。研究发现，该领域正处于快速成长阶段，市场规模持续扩张，技术创新驱动成本下降，政策环境持续向好。[1][2]

**核心结论：**
- 市场集中度加速提升，头部效应显著
- 技术路线日趋清晰，国产替代进程加快
- 政策支持力度持续加大，监管框架逐步完善
- 投资机会集中在产业链核心环节

## 主要发现

### 一、市场格局与竞争态势

{topic}整体市场呈现高速增长态势，2024 年市场规模突破重要关口，同比增速约 25%。[1]

头部玩家市场份额持续提升，CR5 超过 60%，行业整合加速。[2] 中小企业面临分化：具有技术壁垒或细分优势的企业仍有发展空间，缺乏差异化优势的企业面临出清压力。

### 二、技术路线与核心能力

当前主流技术路线已相对确定，围绕核心技术的竞争日益激烈。[3]

- 成本下降趋势明确，规模效应持续释放
- 性能提升与成本降低并行推进
- 国产替代加速，供应链安全受到重视

### 三、政策环境与监管动向

政策面整体处于支持态势，多项利好政策相继落地。[4]

监管框架逐步完善，行业标准体系建设提速，有助于规范市场竞争秩序，保障行业健康可持续发展。

### 四、投资机会与风险提示

**核心机会：**
1. 产业链核心环节龙头企业
2. 技术突破带来的新机遇
3. 区域市场下沉的增量空间

**主要风险：**
- 市场竞争加剧导致价格压力
- 政策变化的不确定性
- 技术迭代加速带来的颠覆风险

## 综合分析与结论

{topic}正处于成长期向成熟期过渡的关键节点。短期内市场竞争将更趋激烈，头部集中趋势延续；中长期，技术突破和规模效应将进一步重塑竞争格局。[5]

建议关注具有核心技术壁垒、健康现金流以及明确差异化定位的企业。

## 来源

- [1] 行业年度报告 2024-2025 — https://example.com/annual-report
- [2] 市场竞争格局分析 — https://example.com/competition
- [3] 技术发展路线白皮书 — https://example.com/tech-roadmap
- [4] 政策汇编与解读 — https://example.com/policy
- [5] 综合研究与展望 — https://example.com/outlook
"""


class MockModelClient(BaseModelClient):
    """Topic-aware mock — no API key required; produces Chinese research content."""

    def __init__(self) -> None:
        self._call_count = 0

    async def chat(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> tuple[str | None, list[ToolCall], int]:
        import asyncio
        await asyncio.sleep(0.25)   # realistic latency

        self._call_count += 1

        sys_text = next((m.content for m in messages if m.role == "system"), "") or ""
        if isinstance(sys_text, list):
            sys_text = " ".join(p.get("text", "") for p in sys_text if isinstance(p, dict))

        question = _mock_extract_question(messages)

        is_plan = "subtasks" in sys_text or "拆解" in sys_text
        is_assess = "sufficient" in sys_text or "评估" in sys_text
        is_synth = ("综合撰写" in sys_text or "综合报告" in sys_text or "研究分析师" in sys_text)
        is_worker = "Deep Research Agent" in sys_text

        # Worker: emit tool calls first, then text on the final round
        if is_worker and tools and self._call_count % 4 != 0:
            tool_name = tools[0].get("function", {}).get("name", "web_search")
            return None, [
                ToolCall(
                    call_id=str(uuid.uuid4()),
                    tool_name=tool_name,
                    arguments={"query": question},
                )
            ], 150

        if is_plan:
            return _mock_plan_json(question), [], 350
        if is_assess:
            return '{"sufficient": true, "missing_topics": []}', [], 120
        if is_synth:
            return _mock_report(question), [], 1500
        # Worker synthesis / fallback
        return _mock_finding(question), [], 450


# ── Factory ───────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_model_client() -> BaseModelClient:
    cfg = get_settings()
    if cfg.use_mock_model:
        return MockModelClient()
    return OpenAIModelClient(
        api_key=cfg.model_api_key,
        base_url=cfg.model_base_url,
        model=cfg.model_name,
    )
