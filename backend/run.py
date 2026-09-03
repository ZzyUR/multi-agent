"""
CLI entry point — Phase 2+

Usage:
    python run.py "研究问题" [--profile fast|standard|deep] [--mock]

Examples:
    python run.py "2026年新能源汽车行业竞争格局分析"
    python run.py "什么是 Multi-Agent 系统，它有哪些应用场景" --profile fast
    python run.py "test" --mock      # 全离线 Mock 模式
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from deepresearch.common.logging import configure_logging, get_logger

configure_logging()
log = get_logger("run")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DeepResearch Multi-Agent CLI")
    p.add_argument("question", help="研究问题")
    p.add_argument(
        "--profile", choices=["fast", "standard", "deep"],
        default="standard", help="研究深度档位（默认 standard）",
    )
    p.add_argument(
        "--mock", action="store_true",
        help="强制使用 Mock 模型和 Mock 搜索（离线测试）",
    )
    p.add_argument(
        "--single", action="store_true",
        help="跳过 Lead Agent，直接用单 Worker（P1 模式，调试用）",
    )
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    if args.mock:
        import os
        os.environ["USE_MOCK_MODEL"] = "true"
        os.environ["USE_MOCK_SEARCH"] = "true"

    from deepresearch.config.settings import get_settings
    from deepresearch.model_client import get_model_client
    from deepresearch.observability.tracer import get_tracer

    cfg = get_settings()
    tracer = get_tracer()
    model = get_model_client()

    print(f"\n{'='*60}")
    print(f"  DeepResearch Agent — Phase 5 (Anti-Hallucination)")
    print(f"{'='*60}")
    print(f"  Question : {args.question}")
    print(f"  Profile  : {args.profile}")
    print(f"  Model    : {'MOCK' if cfg.use_mock_model else cfg.model_name}")
    print(f"  Search   : {'MOCK' if cfg.use_mock_search else 'DuckDuckGo'}")
    print(f"{'='*60}\n")

    if args.single:
        # ── P1 single-agent mode (debug) ──────────────────────────────────────
        import uuid
        from deepresearch.schemas.models import EventType
        from deepresearch.workers.research_worker import ResearchWorker, build_mcp_client

        run_id = str(uuid.uuid4())
        tracer.emit(EventType.RUN_START, run_id=run_id, question=args.question)
        mcp = build_mcp_client(run_id)
        worker = ResearchWorker(
            worker_id="worker-0", run_id=run_id,
            model_client=model, mcp_client=mcp, tracer=tracer,
        )
        finding = await worker.research(args.question)
        print(finding.summary)

    else:
        # ── P2 multi-agent mode ───────────────────────────────────────────────
        from deepresearch.orchestrator.lead_agent import LeadAgent

        lead = LeadAgent(model_client=model, tracer=tracer, profile=args.profile)

        try:
            run, report = await lead.run(args.question)
        except Exception as exc:
            log.error("run_failed", error=str(exc))
            print(f"\n[ERROR] {exc}")
            sys.exit(1)

        # ── Output ─────────────────────────────────────────────────────────────
        cache_hit_pct = getattr(model, "cache_hit_rate", 0.0) * 100
        print(f"\n{'='*60}")
        print("  RESEARCH COMPLETE")
        print(f"{'='*60}")
        print(f"  Run ID      : {run.run_id}")
        print(f"  Workers     : {run.total_workers_spawned}")
        print(f"  Tokens      : {run.tokens_used:,}")
        print(f"  Cache hits  : {cache_hit_pct:.1f}% of prompt tokens")
        print(f"  VFS dir     : {cfg.virtual_fs_root}/{run.run_id}/")
        print(f"  Checkpoints : {cfg.checkpoint_dir}/{run.run_id}/")
        print(f"  Trace       : {cfg.trace_dir}/{run.run_id}.jsonl")
        print(f"{'='*60}\n")
        print(report)


if __name__ == "__main__":
    asyncio.run(main())
