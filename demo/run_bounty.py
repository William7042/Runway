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

    print("Waiting for a human decision in the approval queue. No automatic funding or payout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
