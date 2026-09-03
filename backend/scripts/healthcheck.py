#!/usr/bin/env python3
"""
P0 self-check script — verifies all infrastructure connections.

Usage:
    python -m scripts.healthcheck          # uses .env
    USE_MOCK_MODEL=true python -m scripts.healthcheck   # offline mode
"""

import asyncio
import sys
from pathlib import Path

# Make project importable when run as script
sys.path.insert(0, str(Path(__file__).parent.parent))

from deepresearch.common.logging import configure_logging, get_logger
from deepresearch.config.settings import get_settings

configure_logging()
log = get_logger("healthcheck")

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️ "


async def check_model() -> bool:
    from deepresearch.model_client import get_model_client
    from deepresearch.schemas.models import Message

    cfg = get_settings()
    mode = "MOCK" if cfg.use_mock_model else f"real ({cfg.model_name})"
    try:
        client = get_model_client()
        text, calls, tokens = await client.chat(
            [Message(role="user", content="ping")]
        )
        log.info(f"{PASS} Model client [{mode}]", tokens=tokens)
        return True
    except Exception as e:
        log.error(f"{FAIL} Model client [{mode}]", error=str(e))
        return False


async def check_mysql() -> bool:
    cfg = get_settings()
    try:
        import aiomysql

        conn = await aiomysql.connect(
            host=cfg.mysql_host,
            port=cfg.mysql_port,
            user=cfg.mysql_user,
            password=cfg.mysql_password,
            db=cfg.mysql_db,
        )
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
        conn.close()
        log.info(f"{PASS} MySQL", host=cfg.mysql_host, port=cfg.mysql_port)
        return True
    except Exception as e:
        log.error(f"{FAIL} MySQL", error=str(e))
        return False


async def check_redis() -> bool:
    cfg = get_settings()
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(cfg.redis_url)
        await r.ping()
        await r.aclose()
        log.info(f"{PASS} Redis", url=cfg.redis_url)
        return True
    except Exception as e:
        log.error(f"{FAIL} Redis", error=str(e))
        return False


async def check_chroma() -> bool:
    cfg = get_settings()
    try:
        import chromadb

        client = chromadb.PersistentClient(path=cfg.chroma_path)
        # Just list collections to confirm it's responsive
        client.list_collections()
        log.info(f"{PASS} Chroma", path=cfg.chroma_path)
        return True
    except Exception as e:
        log.error(f"{FAIL} Chroma", error=str(e))
        return False


async def check_trace() -> bool:
    try:
        from deepresearch.observability.tracer import get_tracer
        from deepresearch.schemas.models import EventType

        tracer = get_tracer()
        tracer.emit(EventType.RUN_START, run_id="healthcheck-run", note="self-check")
        log.info(f"{PASS} Tracer (JSONL)")
        return True
    except Exception as e:
        log.error(f"{FAIL} Tracer", error=str(e))
        return False


async def main() -> None:
    print("\n=== DeepResearch P0 Health Check ===\n")

    results = await asyncio.gather(
        check_model(),
        check_trace(),
        check_mysql(),
        check_redis(),
        check_chroma(),
        return_exceptions=True,
    )

    passed = sum(1 for r in results if r is True)
    total = len(results)

    print(f"\n{'='*36}")
    print(f"Result: {passed}/{total} checks passed")

    if passed < total:
        print("\nTip: start dependencies with  docker-compose up -d")
        print("     use USE_MOCK_MODEL=true for offline model check")
        sys.exit(1)
    else:
        print("All systems go. Ready to develop Phase 1.")


if __name__ == "__main__":
    asyncio.run(main())
