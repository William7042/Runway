#!/usr/bin/env python3
"""End-to-end research desk demo against the router stub + approval queue.

DONE WHEN: agent proposes three payments and the queue shows them.

Usage:
  # terminal 1: uvicorn stubs.queue_service:app --port 8000
  # terminal 2:
  DRY_RUN=1 python -m demo.run_research
  DRY_RUN=1 python -m demo.run_research --auto-approve   # demo harness only
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
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Demo harness: approve pending proposals (NOT available to the agent)",
    )
    parser.add_argument(
        "--execute-approved",
        action="store_true",
        help="Call Person A stub execute() on approved proposals (agent never does this)",
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

    if args.auto_approve:
        print("\n=== Demo harness auto-approving (human stand-in) ===")
        for p in pending:
            decided = queue.decide(p.id, "approve", reason="demo harness")
            print(f"  approved {decided.id}")
            if args.execute_approved:
                # Sync stub status then execute — money layer responsibility.
                router_stub.mark_status(decided.id, decided.status)
                # Stub may not have the proposal if queue created it fresh; ensure present.
                if router_stub.get_proposal(decided.id) is None:
                    router_stub._PROPOSALS[decided.id] = decided
                receipt = router_stub.execute(decided.id)
                queue.receipt(decided.id, receipt)
                print(f"  executed {decided.id} tx={receipt.tx_hash} status={receipt.status}")

    enqueued = len(run.enqueued)
    print(f"\nDone: {enqueued} proposals enqueued (target: 3).")
    return 0 if enqueued >= 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
