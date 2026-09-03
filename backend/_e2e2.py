"""临时端到端：验证修复后的 HTML 研报。验证后删除。"""
import asyncio

from deepresearch.config.settings import get_settings
from deepresearch.model_client import get_model_client
from deepresearch.observability.tracer import get_tracer
from deepresearch.orchestrator.lead_agent import LeadAgent


async def main():
    get_settings.cache_clear()
    model = get_model_client()
    tracer = get_tracer()
    lead = LeadAgent(model_client=model, tracer=tracer, profile="fast")
    run, report = await lead.run("梳理具身智能 / 人形机器人产业链与投资机会")
    print("RUN_ID", run.run_id)
    print("HTML_LEN", len(report))
    print("IS_HTML", report.lstrip().startswith("<!DOCTYPE"))


if __name__ == "__main__":
    asyncio.run(main())
