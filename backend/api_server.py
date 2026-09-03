"""FastAPI server launcher — Phase 7.

Usage:
    python api_server.py [--host 0.0.0.0] [--port 8000] [--reload]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from deepresearch.common.logging import configure_logging
configure_logging()

import uvicorn


def main() -> None:
    p = argparse.ArgumentParser(description="DeepResearch API Server")
    import os
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    p.add_argument("--reload", action="store_true", help="Auto-reload on code changes")
    args = p.parse_args()

    print(f"\n{'='*60}")
    print(f"  DeepResearch API Server — Phase 7")
    print(f"{'='*60}")
    print(f"  API   : http://{args.host}:{args.port}/api/")
    print(f"  Docs  : http://{args.host}:{args.port}/docs")
    print(f"{'='*60}\n")

    uvicorn.run(
        "deepresearch.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
