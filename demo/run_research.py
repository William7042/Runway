#!/usr/bin/env python3
"""End-to-end research desk demo against the router stub + approval queue.

DONE WHEN: agent proposes three payments and the queue shows them.
With --fetch: after you approve in the UI (stub executor posts a receipt),
the agent pulls SIMULATED seller data and prints paid→data.

Usage:
  # terminal 1: uvicorn product.queue_service.app:app --port 8000
  #             (or stubs.queue_service)  STUB_EXECUTOR defaults ON for product
  # terminal 2: python -m sellers.run_all
  # terminal 3:
  DRY_RUN=1 python -m demo.run_research
  DRY_RUN=1 python -m demo.run_research --wait --fetch
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.queue_client import QueueClient
from agent.registry import ensure_registry
from agent.research_agent import format_run_report, run_research

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Runway research agent demo")
    parser.add_argument(
        "--question",
        default="Is Acme Robotics legit? Check filings, prior coverage, and founders.",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Poll the queue until each proposal is decided (does not auto-approve).",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="After approve/execute, GET SIMULATED seller endpoints (starts sellers on 8101-8103).",
    )
    args = parser.parse_args()

    ensure_registry()
    queue = QueueClient()

    print("=== Research desk ===")
    print(f"Q: {args.question}\n")
    if args.fetch or args.wait:
        print(
            "Waiting for human decisions in the approval UI "
            "(http://127.0.0.1:5173/#desk). No auto-approve.\n"
        )

    run = run_research(
        args.question,
        source_label="cli",
        wait_for_decisions=args.wait and not args.fetch,
        fetch_seller_data=args.fetch,
    )
    print(format_run_report(run))

    pending = queue.list(status="pending")
    print(f"=== Approval queue: {len(pending)} pending ===")
    for p in pending:
        print(f"  {p.id}  ${p.amount_usd:.2f}  -> {p.seller}")
        print(f"    purpose: {p.purpose}")
        print(f"    source:  {p.source}")
        print(f"    flags:   {p.flags}")

    enqueued = len(run.enqueued)
    paid = len(run.paid_results)
    print(f"\nDone: {enqueued} proposals enqueued (target: 3).")
    if args.fetch:
        print(f"Paid→data fetches: {paid} SIMULATED seller response(s).")
    return 0 if enqueued >= 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
