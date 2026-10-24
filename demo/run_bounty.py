#!/usr/bin/env python3
"""Bounty board demo — post, fund (via proposal), claim, submit, verify.

Escrow is APP-MANAGED, not a smart contract.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import bounty as bounty_mod
from agent.queue_client import QueueClient


def main() -> int:
    q = QueueClient()
    user_q = "Fact-check Acme Robotics founders for the research desk."

    b = bounty_mod.post_bounty(
        poster="wallet_research_desk",
        title="Human fact-check: Acme Robotics founders",
        description=(
            "Verify prior exits and litigation. "
            + bounty_mod.ESCROW_DISCLAIMER
        ),
        price_usd=1.0,
        accepted_asset="USDC",
        deadline=bounty_mod.demo_deadline(24),
        checker_test="founders litigation exits verified sources",
    )
    print(f"Posted {b.id}")
    print(f"  NOTE: {bounty_mod.ESCROW_DISCLAIMER}")

    b, funding = bounty_mod.fund_bounty(b.id, user_request=user_q, queue=q)
    print(f"Funding proposal: {getattr(funding, 'id', funding)} escrow={b.escrow_wallet}")

    # Demo harness approves funding so claim can proceed.
    if funding is not None:
        q.decide(funding.id, "approve", reason="demo: fund escrow")

    b = bounty_mod.claim_bounty(b.id, claimant="wallet_bounty_worker")
    print(f"Claimed by {b.claimant}")

    b = bounty_mod.submit_work(
        b.id,
        "wallet_bounty_worker",
        "Founders: prior exit at LogiCo 2019; no litigation found in mock sources. verified.",
    )
    print(f"Submitted. checker={bounty_mod.run_checker(b.id)}")

    b, payout = bounty_mod.verify_and_payout(
        b.id,
        human_approved=True,
        user_request=user_q,
        notes="Human confirms checker + submission look good",
        queue=q,
    )
    print(f"Payout proposal: {getattr(payout, 'id', payout)} status={b.status.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
