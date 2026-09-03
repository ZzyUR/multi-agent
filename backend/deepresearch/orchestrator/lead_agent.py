"""Lead Agent — Orchestrator state machine.

State flow:
  INTENT → PLAN → DISPATCH → COLLECT → ASSESS
                                  ↑          |
                                  └──────────┘  (depth < max_depth & missing topics)
                                  → SYNTHESIZE → DONE

Key PRD rules enforced here:
  - max_depth / max_breadth / max_total_workers / max_tokens_budget are code-level limits
  - Sub-agents (Workers) are created ONLY by Dispatcher, not by Workers themselves
  - Workers only return summaries — full text goes to VFS in P3
"""

from __future__ import annotations

import json
import re

import yaml

from deepresearch.checkpoint.state_store import CheckpointData, get_checkpoint_store
from deepresearch.common.exceptions import AgentBudgetExceededError
from deepresearch.common.logging import get_logger
from deepresearch.filesystem.virtual_fs import VirtualFS
from deepresearch.memory.base import MemoryService
from deepresearch.model_client import BaseModelClient
from deepresearch.observability.tracer import Tracer
from deepresearch.orchestrator.dispatcher import Dispatcher
from deepresearch.orchestrator.task_tree import TaskNode, TaskTree
from deepresearch.orchestrator.todo_queue import TodoQueue
from deepresearch.schemas.models import (
    EventType,
    Message,
    ResearchRun,
    RunStatus,
)
from deepresearch.orchestrator.hitl import HITLBroker
from deepresearch.workers.citation_agent import CitationAgent
from deepresearch.report import render_html_report, REPORT_JSON_SYSTEM

log = get_logger("orchestrator.lead")

# ── Prompts ────────────────────────────────────────────────────────────────────

_PLAN_SYSTEM = """\
你是一位资深研究规划师。你的任务是将用户的研究问题拆解为若干个独立的子课题。

要求：
1. 每个子课题必须独立，可以单独研究，不依赖其他子课题的结果
2. 子课题之间应覆盖原问题的不同维度，无重叠
3. 每个子课题是一个完整的研究问题句子（不是短语）
4. 子课题数量：{min_tasks}~{max_tasks} 个

请用 JSON 格式返回，格式如下（只返回JSON，不要其他文字）：
{{
  "subtasks": [
    "子课题1的完整研究问题",
    "子课题2的完整研究问题"
  ],
  "rationale": "为什么这样拆分（一句话）"
}}\
"""

_ASSESS_SYSTEM = """\
你是一位研究质量评估员。评估当前研究发现是否足够回答原始问题。

原始问题：{question}

已收集的研究发现摘要：
{summaries}

请判断：
1. 当前发现是否足以全面回答原始问题？
2. 还有哪些重要方面尚未覆盖？

只返回 JSON，格式如下：
{{
  "sufficient": true 或 false,
  "missing_topics": ["缺失话题1（完整问题句子）", "缺失话题2"]
}}\
"""

_SYNTHESIZE_SYSTEM = """\
你是一位资深研究分析师。基于多个子研究团队收集的【完整原始材料】，综合撰写一份详尽、专业、有深度的研究报告。

研究问题：{question}

各子研究团队的完整研究材料：
{summaries}

写作要求：
1. 报告必须详实、有深度，篇幅不少于 1500 字
2. 每个关键论断都要有具体的事实、数据、案例支撑，并标注来源引用 [n]
3. 进行跨维度的对比与因果分析，而非简单罗列信息
4. 主动指出材料中的分歧、不确定性与值得关注的趋势
5. 结论必须基于上述材料中的证据，不得编造数据或来源
6. 来源 URL 必须来自上述材料中真实出现的链接，严禁虚构

报告结构（Markdown）：

# [报告标题]

## 执行摘要
（用 4-6 句话概括最核心的发现与结论）

## 主要发现

### 1. [维度一标题]
（详细分析，含具体数据/事实，引用来源 [1][2]…）

### 2. [维度二标题]
…

（根据材料覆盖的维度，灵活组织 3-5 个章节）

## 综合分析
（跨维度的深度洞察：因果关系、横向对比、趋势研判）

## 结论与建议
（基于证据的明确结论，以及可执行的建议）

## 来源
- [1] 来源标题 — 真实URL
- [2] 来源标题 — 真实URL

每个关键论断必须有来源引用编号 [n]；来源列表用 Markdown 无序列表逐条列出，URL 必须真实。\
"""


# ── JSON helpers ───────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """Extract the first JSON object from model output (handles code fences)."""
    # Try ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        raw = m.group(1)
    else:
        # Find outermost { }
        start = text.find("{")
        end = text.rfind("}") + 1
        raw = text[start:end] if start != -1 and end > start else "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _loads_lenient(text: str) -> dict:
    """Parse a JSON object, tolerating truncation (e.g. hit max_tokens):
    strip code fences; on failure, truncate at the last top-level-safe comma
    and close any open brackets so the parsed-so-far content is recovered."""
    if not text:
        return {}
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if m:
        s = m.group(1)
    else:
        start = text.find("{")
        s = text[start:] if start >= 0 else ""
    s = s.strip()
    if not s:
        return {}
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Bare-placeholder repair: LLMs sometimes emit unquoted tokens like XXX / YY%
    # (often copied from mock data) as JSON values, which is invalid. Replace
    # any bare alphabetic token in value position with null.
    def _fix_bare(m: "re.Match") -> str:
        return m.group(0) if m.group(2) in ("true", "false", "null") else m.group(1) + "null" + m.group(3)
    fixed = s
    for _ in range(5):
        new = re.sub(r'([:\[,]\s*)([A-Za-z]{2,}[A-Za-z0-9]*%?)(\s*[,\]\}])', _fix_bare, fixed)
        if new == fixed:
            break
        fixed = new
    if fixed != s:
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            s = fixed  # keep cleaned version for truncation repair below
    # Truncation repair: walk the string tracking string/bracket state,
    # remember each comma + the bracket stack at that point, then cut at the
    # last comma and append the matching closers.
    last = None  # (index, stack_snapshot)
    stack: list[str] = []
    in_str = False
    esc = False
    for i, ch in enumerate(s):
        if esc:
            esc = False
            continue
        if in_str:
            if ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
        elif ch == ",":
            last = (i, list(stack))
    if last is not None:
        idx, st = last
        repaired = s[:idx] + "".join(reversed(st))
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass
    return {}


def _report_plain_text(data: dict, question: str) -> str:
    """Flatten the structured report into plain text for citation checking.
    Walks the block array; falls back to the legacy fixed-shape fields."""
    if not data:
        return question
    parts: list = [data.get("title", "")]
    for b in data.get("blocks", []) or []:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "prose":
            parts += [b.get("heading", ""), b.get("lead", "")] + list(b.get("paragraphs") or [])
        elif t == "callout":
            parts += [b.get("title", ""), b.get("text", "")]
        elif t == "conclusions":
            parts += list(b.get("items") or [])
        elif t == "quadrant":
            parts += [b.get("heading", ""), b.get("intro", "")]
        elif t == "table":
            for row in b.get("rows", []) or []:
                parts += [str(c) for c in row]
    if not data.get("blocks"):  # legacy fixed-shape fallback
        parts += [data.get("summary_lead", ""), data.get("summary_body", ""),
                  data.get("synth_body", "")]
        for sec in data.get("sections", []) or []:
            parts += [sec.get("para_1", ""), sec.get("para_2", "")]
        parts += data.get("conclusions", []) or []
    return "\n".join(str(p) for p in parts if p)


def _estimate_cost(tokens: int) -> str:
    """Rough USD estimate for display (qwen-plus blended ~$0.0004/1k)."""
    return f"${tokens / 1000 * 0.0004:.4f}"


# ── Profile loader ─────────────────────────────────────────────────────────────

def _load_profile(profile_name: str) -> dict:
    from deepresearch.config.settings import get_settings
    cfg = get_settings()
    with open(cfg.profiles_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    profiles = data.get("profiles", {})
    return profiles.get(profile_name, profiles.get("standard", {}))


# ── Lead Agent ─────────────────────────────────────────────────────────────────

class LeadAgent:
    """Orchestrator — runs the full research state machine."""

    def __init__(
        self,
        model_client: BaseModelClient,
        tracer: Tracer,
        profile: str = "standard",
    ) -> None:
        self._model = model_client
        self._tracer = tracer
        self._profile = profile
        # Whether to run the ASSESS → 补研 round (extra worker batch). Off by
        # default for fast/standard to cut latency; deep keeps it.
        self._enable_assess = bool(_load_profile(profile).get("enable_assess", False))

    async def run(
        self,
        question: str,
        *,
        run_id: str | None = None,
        resume: bool = False,
        hitl: HITLBroker | None = None,
    ) -> tuple[ResearchRun, str]:
        """Execute the full research pipeline.

        Args:
            question: The research question.
            run_id:   If provided, re-use this run ID (required when resume=True).
            resume:   If True, load the latest checkpoint for run_id and fast-forward
                      past already-completed stages.
            hitl:     Optional HITL broker — enables 3 intervention points.

        Returns (ResearchRun metadata, final_report_markdown).
        """
        run = self._init_run(question, run_id=run_id)
        tree = TaskTree(root_query=question, run_id=run.run_id)
        queue = TodoQueue()

        from deepresearch.config.settings import get_settings
        cfg = get_settings()
        vfs = VirtualFS(root=cfg.virtual_fs_root, run_id=run.run_id)
        from deepresearch.rag.retriever import get_retriever
        retriever = get_retriever(run_id=run.run_id, chroma_path=cfg.chroma_path)
        memory = MemoryService(run_id=run.run_id, traces_dir=cfg.trace_dir)

        # P5: checkpoint store for this run
        ckpt_store = get_checkpoint_store(
            run.run_id,
            checkpoint_dir=getattr(cfg, "checkpoint_dir", "./checkpoints"),
        )

        # P5: resume — load checkpoint and fast-forward past completed stages
        _cp = ckpt_store.load_latest() if resume else None
        if _cp and _cp.stage == "done" and _cp.report:
            log.info("resume_done", run_id=run.run_id)
            run.status = RunStatus.DONE
            run.tokens_used = _cp.tokens_used
            return run, _cp.report
        if _cp and _cp.stage == "synth" and _cp.report:
            log.info("resume_synth", run_id=run.run_id)
            # Skip planning + dispatch; run citation on saved draft
            citation_agent = CitationAgent(
                model_client=self._model, retriever=retriever,
                tracer=self._tracer, run_id=run.run_id,
                policy=getattr(cfg, "citation_policy", "flag"),
            )
            revised, cit = await citation_agent.verify_and_revise(_cp.report)
            vfs.write("report_final.md", revised)
            run.status = RunStatus.DONE
            run.tokens_used = _cp.tokens_used
            ckpt_store.save(CheckpointData(
                run_id=run.run_id, stage="done", question=question,
                profile=self._profile, report=revised,
                tokens_used=run.tokens_used,
                citation_report={"total": cit.total_claims, "supported": cit.supported,
                                 "support_rate": cit.support_rate},
            ))
            return run, revised

        vfs.write("plan.md", f"# Research Plan\n\nQuestion: {question}\nProfile: {self._profile}\n")

        dispatcher = Dispatcher(
            self._model, self._tracer, run.run_id,
            vfs=vfs, retriever=retriever, memory=memory,
        )

        self._tracer.emit(
            EventType.RUN_START, run.run_id,
            question=question, profile=self._profile,
        )

        # ── HITL point 1: INTENT clarification ────────────────────────────────
        if hitl:
            run.status = RunStatus.INTENT
            question = await hitl.intent_clarify(
                run.run_id, question, tracer=self._tracer
            )

        # ── PLAN ──────────────────────────────────────────────────────────────
        # Resume fast-forward: if we have a "plan"/"worker" checkpoint, skip planning
        if _cp and _cp.stage in ("plan", "worker") and _cp.subtask_queries:
            log.info("resume_plan", run_id=run.run_id, subtasks=len(_cp.subtask_queries))
            subtask_queries = _cp.subtask_queries
        else:
            run.status = RunStatus.PLANNING
            self._tracer.emit(EventType.PLAN_START, run.run_id, question=question)
            subtask_queries = await self._plan(question, run)
        # ── HITL point 2: PLAN review ─────────────────────────────────────────
        if hitl:
            subtask_queries = await hitl.plan_review(
                run.run_id, subtask_queries, tracer=self._tracer
            )

        child_nodes = tree.add_children(tree.root, subtask_queries)
        queue.add(*child_nodes)
        self._tracer.emit(
            EventType.PLAN_DONE, run.run_id,
            subtasks=subtask_queries, count=len(subtask_queries),
        )
        log.info("plan_done", subtasks=subtask_queries)

        # P5: checkpoint after planning
        ckpt_store.save(CheckpointData(
            run_id=run.run_id, stage="plan", question=question,
            profile=self._profile, subtask_queries=subtask_queries,
            tokens_used=run.tokens_used,
        ))

        # ── DISPATCH → COLLECT → ASSESS loop ──────────────────────────────────
        depth = 0
        while queue.has_pending and depth < run.max_depth:
            depth += 1
            log.info("dispatch_round", depth=depth, pending=queue.pending_count)

            # ── HITL point 3: mid-run abort check ─────────────────────────────
            if hitl and hitl.check_abort(run.run_id):
                log.info("hitl_abort_detected", run_id=run.run_id, depth=depth)
                self._tracer.emit(
                    EventType.HUMAN_INTERVENE, run.run_id,
                    point="run", action="abort",
                )
                await dispatcher.cancel_pending()
                break

            if run.tokens_used >= run.max_tokens_budget:
                log.warning("token_budget_exceeded", used=run.tokens_used)
                self._tracer.emit(
                    EventType.RUN_END, run.run_id, reason="token_budget_exceeded"
                )
                break

            run.status = RunStatus.RUNNING
            batch = queue.pop_batch(run.max_breadth)
            try:
                await dispatcher.dispatch(batch, run)
            except AgentBudgetExceededError as exc:
                log.warning("budget_limit_hit", error=str(exc))
                self._tracer.emit(EventType.RUN_END, run.run_id, reason=str(exc))
                break

            for node in batch:
                if node.finding:
                    queue.mark_done(node, node.finding) if node.status.value == "done" \
                        else queue.mark_failed(node, "worker failed")

            # P5: incremental checkpoint after each dispatch round
            findings_so_far = [
                {"task_id": f.task_id, "summary": f.summary, "content_path": f.content_path}
                for f in tree.collect_findings()
            ]
            ckpt_store.save(CheckpointData(
                run_id=run.run_id, stage="worker", question=question,
                profile=self._profile, subtask_queries=subtask_queries,
                findings=findings_so_far, tokens_used=run.tokens_used,
            ))

            if self._enable_assess and depth < run.max_depth and not queue.has_pending:
                missing = await self._assess(tree, question, run)
                if missing:
                    log.info("assess_missing", topics=missing)
                    new_nodes = tree.add_children(tree.root, missing)
                    queue.add(*new_nodes)
                else:
                    log.info("assess_sufficient")
                    break

        # ── SYNTHESIZE → 结构化 JSON ──────────────────────────────────────────
        run.status = RunStatus.SYNTHESIZING
        self._tracer.emit(EventType.SYNTHESIZE, run.run_id)
        structured, plain = await self._synthesize_structured(tree, question, run)
        vfs.write("report_data.json", json.dumps(structured, ensure_ascii=False, indent=2))
        facts_added = memory.consolidate()
        log.info("memory_consolidate", facts_added=facts_added)

        ckpt_store.save(CheckpointData(
            run_id=run.run_id, stage="synth", question=question,
            profile=self._profile, subtask_queries=subtask_queries,
            findings=findings_so_far if 'findings_so_far' in dir() else [],
            report=plain, tokens_used=run.tokens_used,
        ))

        # ── CITE（对纯文本核查，得到引用支撑率，keep_as_is 不改报告） ──────────
        run.status = RunStatus.CITING
        citation_agent = CitationAgent(
            model_client=self._model,
            retriever=retriever,
            tracer=self._tracer,
            run_id=run.run_id,
            policy=getattr(cfg, "citation_policy", "flag"),
        )
        _, cit_report = await citation_agent.verify_and_revise(plain)
        log.info("citation_done", summary=cit_report.summary())

        # ── RENDER 可视化 HTML 研报 ───────────────────────────────────────────
        cache_hit_rate = getattr(self._model, "cache_hit_rate", 0.0)
        revised_report = render_html_report(structured, {
            "tokens": f"{run.tokens_used:,}",
            "cost": _estimate_cost(run.tokens_used),
            "citation_rate": f"{cit_report.support_rate * 100:.0f}%",
            "profile": self._profile,
        })
        vfs.write("report.html", revised_report)

        run.status = RunStatus.DONE

        # P5: final checkpoint
        ckpt_store.save(CheckpointData(
            run_id=run.run_id, stage="done", question=question,
            profile=self._profile, subtask_queries=subtask_queries,
            report=revised_report, tokens_used=run.tokens_used,
            citation_report={
                "total": cit_report.total_claims,
                "supported": cit_report.supported,
                "support_rate": cit_report.support_rate,
            },
        ))

        self._tracer.emit(
            EventType.RUN_END, run.run_id,
            total_workers=run.total_workers_spawned,
            tokens_used=run.tokens_used,
            cache_hit_rate=round(cache_hit_rate, 4),
            citation_support_rate=round(cit_report.support_rate, 3),
        )
        log.info(
            "run_done",
            workers=run.total_workers_spawned,
            tokens=run.tokens_used,
            findings=len(tree.collect_findings()),
            cache_hit_rate=round(cache_hit_rate, 4),
            citation_support_rate=round(cit_report.support_rate, 3),
        )
        return run, revised_report

    # ── PLAN ──────────────────────────────────────────────────────────────────

    async def _plan(self, question: str, run: ResearchRun) -> list[str]:
        min_tasks = 2
        max_tasks = run.max_breadth

        system = _PLAN_SYSTEM.format(min_tasks=min_tasks, max_tasks=max_tasks)
        messages = [
            Message(role="system", content=system),
            Message(role="user", content=f"研究问题：{question}"),
        ]
        text, _, tokens = await self._model.chat(messages, max_tokens=1024)
        run.tokens_used += tokens

        data = _extract_json(text or "")
        subtasks = data.get("subtasks", [])

        # Fallback: if JSON parse failed, treat full text as one task
        if not subtasks or not isinstance(subtasks, list):
            log.warning("plan_json_failed", raw=text)
            subtasks = [question]

        # Enforce breadth limit (hard)
        subtasks = subtasks[:run.max_breadth]
        return [str(t).strip() for t in subtasks if str(t).strip()]

    # ── ASSESS ────────────────────────────────────────────────────────────────

    async def _assess(
        self, tree: TaskTree, question: str, run: ResearchRun
    ) -> list[str]:
        findings = tree.collect_findings()
        if not findings:
            return []

        summaries = "\n\n".join(
            f"【子课题 {i+1}】{f.summary}" for i, f in enumerate(findings)
        )
        system = _ASSESS_SYSTEM.format(question=question, summaries=summaries)
        messages = [
            Message(role="system", content=system),
            Message(role="user", content="请评估研究完整性。"),
        ]
        text, _, tokens = await self._model.chat(messages, max_tokens=512)
        run.tokens_used += tokens

        data = _extract_json(text or "")
        if data.get("sufficient", True):
            return []

        missing = data.get("missing_topics", [])
        # Enforce breadth limit on new tasks
        return [str(t).strip() for t in missing if str(t).strip()][: run.max_breadth]

    # ── SYNTHESIZE ────────────────────────────────────────────────────────────

    async def _synthesize_structured(
        self, tree: TaskTree, question: str, run: ResearchRun
    ) -> tuple[dict, str]:
        """Produce a structured report JSON (for HTML rendering) + plain text
        (for citation checking). Reads each worker's FULL finding from VFS."""
        findings = tree.collect_findings()
        if not findings:
            data = {"title": question, "sources": [], "blocks": [
                {"type": "prose", "heading": "说明", "paragraphs": ["未能收集到有效研究发现。"]}
            ]}
            return data, "未能收集到有效研究发现。"

        from deepresearch.config.settings import get_settings
        cfg = get_settings()
        vfs = VirtualFS(root=cfg.virtual_fs_root, run_id=run.run_id)

        parts: list[str] = []
        for i, f in enumerate(findings):
            body = ""
            if f.content_path:
                try:
                    body = vfs.read(f.content_path)
                except Exception as exc:
                    log.warning("synth_read_finding_failed", path=f.content_path, error=str(exc))
            if not body.strip():
                body = f.summary
            parts.append(f"### 子课题 {i+1} 的完整研究材料\n\n{body[:6000]}")

        summaries = "\n\n---\n\n".join(parts)
        system = REPORT_JSON_SYSTEM.format(question=question, summaries=summaries)
        messages = [
            Message(role="system", content=system),
            Message(role="user", content="请输出研报 JSON。只返回 JSON 对象。"),
        ]
        text, _, tokens = await self._model.chat(messages, max_tokens=8192)
        run.tokens_used += tokens

        data = _loads_lenient(text or "")
        if not data.get("blocks") and not data.get("sections"):
            # JSON 解析失败：回退为最小结构，至少保住正文
            log.warning("synth_json_failed", raw=(text or "")[:200])
            data = {
                "title": question,
                "blocks": [{"type": "prose", "heading": "研究综述",
                            "paragraphs": [text or "综合报告生成失败。"]}],
                "sources": [],
            }
        plain = _report_plain_text(data, question)
        return data, plain

    # ── Init ──────────────────────────────────────────────────────────────────

    def _init_run(self, question: str, *, run_id: str | None = None) -> ResearchRun:
        profile = _load_profile(self._profile)
        from deepresearch.config.settings import get_settings
        cfg = get_settings()
        kwargs = dict(
            question=question,
            profile=self._profile,
            max_depth=cfg.max_depth or profile.get("max_depth", 2),
            max_breadth=cfg.max_breadth or profile.get("max_breadth", 4),
            max_total_workers=cfg.max_total_workers or profile.get("max_total_workers", 10),
            max_tokens_budget=cfg.max_tokens_budget or profile.get("max_tokens_budget", 150000),
        )
        if run_id:
            kwargs["run_id"] = run_id
        return ResearchRun(**kwargs)
