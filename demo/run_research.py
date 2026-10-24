#!/usr/bin/env python3
"""End-to-end research desk demo against the router stub + approval queue.

DONE WHEN: agent proposes three payments and the queue shows them.

Usage:
  # terminal 1: uvicorn stubs.queue_service:app --port 8000
  # terminal 2:
  DRY_RUN=1 python -m demo.run_research
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Repo root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.queue_client import QueueClient
from agent.registry import ensure_registry
from agent.research_agent import format_run_report, run_research
from stubs import router_stub

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Runway research agent demo")
    parser.add_argument(
        "--question",
        default="Is Acme Robotics legit? Check filings, prior coverage, and founders.",
    )
    args = parser.parse_args()

    ensure_registry()
    queue = QueueClient()

    print("=== Research desk ===")
    print(f"Q: {args.question}\n")
    run = run_research(args.question, source_label="cli")
    print(format_run_report(run))

    pending = queue.list(status="pending")
    print(f"=== Approval queue: {len(pending)} pending ===")
    for p in pending:
        print(f"  {p.id}  ${p.amount_usd:.2f}  -> {p.seller}")
        print(f"    purpose: {p.purpose}")
        print(f"    source:  {p.source}")
        print(f"    flags:   {p.flags}")

    enqueued = len(run.enqueued)
    print(f"\nDone: {enqueued} proposals enqueued (target: 3).")
    return 0 if enqueued >= 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
