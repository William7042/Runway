"""Payment orchestration for the agent layer.

Flow: policy check -> router.propose_payment -> verifier flag -> queue.create.
The agent NEVER calls execute(). Person C (or demo harness) approves; Person A executes.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from agent.models import Proposal
from agent.policy import PolicyConfig, PolicyResult, check_proposal
from agent.queue_client import QueueClient
from agent.verifier import VerifierResult, verify
from stubs import router_stub

logger = logging.getLogger("runway.payments")


class PaymentBlocked(Exception):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def propose_and_enqueue(
    *,
    buyer: str,
    seller: str,
    amount_usd: float,
    purpose: str,
    source: str,
    user_request: str,
    policy: PolicyConfig,
    queue: Optional[QueueClient] = None,
    preferred_asset: str = "USDC",
) -> tuple[Optional[Proposal], PolicyResult, Optional[VerifierResult]]:
    """Run policy + propose + verify + push to approval queue.

    Returns (proposal_or_None, policy_result, verifier_result_or_None).
    On policy block: proposal is None and nothing is enqueued.
    Verifier mismatches add a flag; they do not block.
    """
    # Pre-check with provisional path assets (stub always uses NVDAc + USDC).
    live = os.getenv('RUNWAY_MODE', 'stub') == 'live'
    provisional_assets = [] if live else ["NVDAc", preferred_asset]
    provisional_cost = 0 if live else round(amount_usd * 0.003, 4)

    policy_result = check_proposal(
        config=policy,
        buyer=buyer,
        seller=seller,
        amount_usd=amount_usd,
        assets_in_path=provisional_assets,
        expected_cost=provisional_cost,
        purpose=purpose,
        source=source,
        record_velocity=not live,
    )
    if policy_result.blocked:
        logger.warning("Blocked before propose_payment: %s", policy_result.reasons)
        return None, policy_result, None

    # Money-layer adapter owns all True Markets access.
    if live:
        from runway_money.agent_adapter import draft_payment
        proposal = draft_payment(buyer, seller, amount_usd, purpose, source)
        # The router's real assets and fees must satisfy policy before enqueue.
        policy_result = check_proposal(config=policy, buyer=buyer, seller=seller,
            amount_usd=amount_usd, assets_in_path=[s.asset for s in proposal.path],
            expected_cost=proposal.expected_cost, purpose=purpose, source=source)
        if policy_result.blocked:
            return None, policy_result, None
    else:
        proposal = router_stub.propose_payment(
            buyer=buyer,
            seller=seller,
            amount_usd=amount_usd,
            purpose=purpose,
            source=source,
            preferred_asset=preferred_asset,
        )

    path_summary = " -> ".join(f"{s.type}:{s.asset}:{s.amount}" for s in proposal.path)
    v = verify(
        user_request=user_request,
        purpose=purpose,
        amount_usd=amount_usd,
        seller=seller,
        path_summary=path_summary,
        buyer=buyer,
    )
    if v.is_mismatch:
        proposal.flags.append(v.flag_text())
        # Re-store so stub + queue see flags.
        if not live:
            router_stub._PROPOSALS[proposal.id] = proposal

    q = queue or QueueClient()
    stored = q.create(proposal)
    logger.info(
        "Enqueued proposal %s status=%s flags=%s",
        stored.id,
        stored.status.value,
        stored.flags,
    )
    return stored, policy_result, v
