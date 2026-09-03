"""CLI tool for trace analysis and replay (Phase 6).

Usage:
    python scripts/trace_stats.py <run_id>          # show stats
    python scripts/trace_stats.py <run_id> --replay  # show decision chain
    python scripts/trace_stats.py --list             # list all traces
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from deepresearch.common.logging import configure_logging
configure_logging()

from deepresearch.observability.trace_reader import TraceReader


def list_traces(trace_dir: str = "./traces") -> None:
    p = Path(trace_dir)
    files = sorted(p.glob("*.jsonl"))
    if not files:
        print(f"No traces found in {trace_dir}/")
        return
    print(f"\nTraces in {trace_dir}/:")
    for f in files:
        size_kb = f.stat().st_size / 1024
        print(f"  {f.stem}  ({size_kb:.1f} KB)")


def show_stats(run_id: str, trace_dir: str = "./traces") -> None:
    reader = TraceReader.load(run_id, trace_dir=trace_dir)
    stats = reader.stats()
    print(f"\n{'='*60}")
    print("  TRACE STATS")
    print(f"{'='*60}")
    for line in stats.summary_lines():
        print(f"  {line}")
    print(f"{'='*60}")


def show_replay(run_id: str, trace_dir: str = "./traces") -> None:
    reader = TraceReader.load(run_id, trace_dir=trace_dir)
    print(reader.replay())


def main() -> None:
    p = argparse.ArgumentParser(description="DeepResearch Trace Analyzer")
    p.add_argument("run_id", nargs="?", help="Run ID to analyze")
    p.add_argument("--replay", action="store_true", help="Show decision chain replay")
    p.add_argument("--list", action="store_true", help="List all available traces")
    p.add_argument("--trace-dir", default="./traces", help="Trace directory")
    args = p.parse_args()

    if args.list:
        list_traces(args.trace_dir)
        return

    if not args.run_id:
        p.print_help()
        sys.exit(1)

    if args.replay:
        show_replay(args.run_id, trace_dir=args.trace_dir)
    else:
        show_stats(args.run_id, trace_dir=args.trace_dir)


if __name__ == "__main__":
    main()
