"""临时端到端验证：真实 LLM + 真实搜索跑一次完整研究。验证后可删除。"""
import asyncio

from deepresearch.config.settings import get_settings
from deepresearch.model_client import get_model_client
from deepresearch.observability.tracer import get_tracer
from deepresearch.orchestrator.lead_agent import LeadAgent


async def main():
    get_settings.cache_clear()
    cfg = get_settings()
    print(f"model={cfg.model_name} mock_model={cfg.use_mock_model} mock_search={cfg.use_mock_search}")
    model = get_model_client()
    tracer = get_tracer()
    lead = LeadAgent(model_client=model, tracer=tracer, profile="fast")
    run, report = await lead.run("2026年中国新能源汽车行业竞争格局")
    print("=" * 70)
    print(f"workers={run.total_workers_spawned}  tokens={run.tokens_used}")
    print("=" * 70)
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
