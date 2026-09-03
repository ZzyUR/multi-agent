"""CitationAgent — post-synthesis hallucination guard.

Algorithm:
  1. Parse the final report into claim sentences (model-assisted).
  2. For each claim, query Chroma (vector_search) to find supporting evidence.
  3. If evidence found → keep claim with [n] citation.
     If no evidence  → apply UNSUPPORTED_POLICY (flag | delete | keep_as_is).
  4. Return revised report + CitationReport (structured audit).

Policies (configurable via settings or argument):
  "flag"        — append "(⚠ 无来源支撑)" after unsupported claims
  "delete"      — remove unsupported sentences from the report
  "keep_as_is"  — leave report unchanged, but still audit
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Literal

from deepresearch.common.logging import get_logger
from deepresearch.model_client import BaseModelClient
from deepresearch.observability.tracer import Tracer
from deepresearch.rag.retriever import ChromaRetriever
from deepresearch.schemas.models import EventType, Message

log = get_logger("worker.citation")

UnsupportedPolicy = Literal["flag", "delete", "keep_as_is"]

_CLAIM_EXTRACT_SYSTEM = """\
你是一位严谨的学术审校员。给定一篇研究报告，请提取其中所有**具体事实性论断**（factual claims）。

规则：
- 仅提取可被独立验证的陈述（含数字、引用、具体事件、机构名称等）
- 跳过过渡句、章节标题、解释性说明
- 每条论断独立一行，以 JSON 数组形式返回
- 最多 20 条

只返回 JSON 数组，不要其他文字：
["论断1", "论断2", ...]
"""

_CLAIM_VERIFY_SYSTEM = """\
你是一位事实核查员。判断以下证据片段是否足以支撑给定论断。

只返回 JSON：{"supported": true 或 false, "reason": "一句话说明"}
"""


@dataclass
class ClaimVerification:
    claim: str
    supported: bool
    evidence: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class CitationReport:
    total_claims: int = 0
    supported: int = 0
    unsupported: int = 0
    support_rate: float = 0.0
    verifications: list[ClaimVerification] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"引用核查: {self.total_claims} 条论断, "
            f"{self.supported} 条有支撑 ({self.support_rate:.0%}), "
            f"{self.unsupported} 条无来源"
        )


class CitationAgent:
    """Standalone agent — verifies every factual claim in the final report."""

    def __init__(
        self,
        model_client: BaseModelClient,
        retriever: ChromaRetriever | None,
        tracer: Tracer,
        run_id: str,
        *,
        policy: UnsupportedPolicy = "flag",
        min_evidence_score: float = 0.35,
    ) -> None:
        self._model = model_client
        self._retriever = retriever
        self._tracer = tracer
        self._run_id = run_id
        self._policy = policy
        self._min_score = min_evidence_score

    async def verify_and_revise(
        self, report: str
    ) -> tuple[str, CitationReport]:
        """
        Main entrypoint.
        Returns (revised_report, citation_report).
        """
        self._tracer.emit(EventType.CITATION_CHECK, self._run_id, stage="start")

        # Step 1: extract claims
        claims = await self._extract_claims(report)
        log.info("citation_claims_extracted", count=len(claims), run_id=self._run_id)

        if not claims:
            report_obj = CitationReport(total_claims=0, support_rate=1.0)
            return report, report_obj

        # Step 2: verify each claim — concurrently (was sequential: up to 20
        # round-trips back-to-back, the single biggest latency tail).
        verifications: list[ClaimVerification] = list(
            await asyncio.gather(*(self._verify_claim(c) for c in claims))
        )

        # Step 3: build citation report
        supported = sum(1 for v in verifications if v.supported)
        cit_report = CitationReport(
            total_claims=len(verifications),
            supported=supported,
            unsupported=len(verifications) - supported,
            support_rate=supported / max(len(verifications), 1),
            verifications=verifications,
        )
        log.info(
            "citation_done",
            run_id=self._run_id,
            support_rate=cit_report.support_rate,
            unsupported=cit_report.unsupported,
        )

        # Step 4: revise report per policy
        revised = self._apply_policy(report, verifications)

        self._tracer.emit(
            EventType.CITATION_CHECK,
            self._run_id,
            stage="done",
            total=cit_report.total_claims,
            supported=cit_report.supported,
            support_rate=round(cit_report.support_rate, 3),
        )

        return revised, cit_report

    # ── Private ──────────────────────────────────────────────────────────────

    async def _extract_claims(self, report: str) -> list[str]:
        # Feed only the body (skip the sources section to avoid circular refs)
        body = _strip_sources_section(report)
        messages = [
            Message(role="system", content=_CLAIM_EXTRACT_SYSTEM),
            Message(role="user", content=body[:6000]),
        ]
        text, _, _ = await self._model.chat(messages, max_tokens=1024)
        if not text:
            return []
        # Extract JSON array
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return []
        try:
            raw = json.loads(m.group())
            return [str(c).strip() for c in raw if str(c).strip()][:20]
        except json.JSONDecodeError:
            return []

    async def _verify_claim(self, claim: str) -> ClaimVerification:
        evidence_texts: list[str] = []
        source_urls: list[str] = []

        # Retrieve supporting evidence from Chroma
        if self._retriever:
            hits = self._retriever.query(query_text=claim, n_results=3)
            for hit in hits:
                if isinstance(hit, dict) and hit.get("score", 0) >= self._min_score:
                    evidence_texts.append(hit.get("text", "")[:400])
                    url = hit.get("url", "")
                    if url:
                        source_urls.append(url)

        # If we have evidence, ask the model to confirm
        if evidence_texts:
            evidence_block = "\n\n".join(
                f"[证据{i+1}] {t}" for i, t in enumerate(evidence_texts)
            )
            messages = [
                Message(role="system", content=_CLAIM_VERIFY_SYSTEM),
                Message(
                    role="user",
                    content=f"论断：{claim}\n\n证据：\n{evidence_block}",
                ),
            ]
            text, _, _ = await self._model.chat(messages, max_tokens=256)
            data = _safe_json(text or "")
            supported = bool(data.get("supported", False))
            reason = data.get("reason", "")
        else:
            supported = False
            reason = "向量库中未检索到相关证据"

        return ClaimVerification(
            claim=claim,
            supported=supported,
            evidence=evidence_texts,
            source_urls=source_urls,
            reason=reason,
        )

    def _apply_policy(
        self, report: str, verifications: list[ClaimVerification]
    ) -> str:
        if self._policy == "keep_as_is":
            return report

        unsupported_claims = {
            v.claim for v in verifications if not v.supported
        }
        if not unsupported_claims:
            return report

        if self._policy == "flag":
            # 按句子去重标记：同一句即使命中多个无支撑论断，也只标注一次
            keys = [c[:40] for c in unsupported_claims if c[:40]]

            def _mark(m: "re.Match") -> str:
                seg = m.group(0)
                if "⚠" in seg:            # 该句已标注，跳过
                    return seg
                if any(k in seg for k in keys):
                    return seg + " _(⚠ 无来源支撑)_"
                return seg

            return re.sub(r"[^。\n]+", _mark, report)

        if self._policy == "delete":
            for claim in unsupported_claims:
                # Delete the sentence containing this claim
                escaped = re.escape(claim[:60])
                report = re.sub(rf"[^。\n]*{escaped}[^。\n]*[。\n]?", "", report)
            return report

        return report


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_sources_section(text: str) -> str:
    """Remove the ## 来源 section to avoid self-referential verification."""
    idx = max(
        text.find("## 来源"),
        text.find("## 参考"),
        text.find("## References"),
    )
    return text[:idx] if idx > 0 else text


def _safe_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return {}
