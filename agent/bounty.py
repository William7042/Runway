"""Bounty board with APP-MANAGED escrow (not a smart contract).

Flow: post -> fund escrow via propose_payment (Person A) -> one claimant ->
submit -> verify (human; optional checker agent for objective tasks) ->
payout or refund proposal.

Escrow wallets are created through the router stub / Person A; the app alone
moves funds out after human approval. Say so in UI text.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent.models import Bounty, BountyStatus
from agent.payments import propose_and_enqueue
from agent.policy import PolicyConfig, default_research_policy
from agent.queue_client import QueueClient
from agent.registry import known_seller_wallets
from stubs import router_stub

logger = logging.getLogger("runway.bounty")

BOUNTY_DIR = Path("data/bounties")
BOUNTY_DIR.mkdir(parents=True, exist_ok=True)

# Notice shown in API responses / UI copy.
ESCROW_DISCLAIMER = (
    "Escrow is APP-MANAGED, not a smart contract. Funds sit in a dedicated "
    "wallet created for this bounty; only the Runway app can initiate transfers, "
    "and every transfer still requires human approval."
)


def _save(b: Bounty) -> Bounty:
    (BOUNTY_DIR / f"{b.id}.json").write_text(b.model_dump_json(indent=2))
    return b


def _load(bounty_id: str) -> Bounty:
    fp = BOUNTY_DIR / f"{bounty_id}.json"
    if not fp.exists():
        raise KeyError(bounty_id)
    return Bounty.model_validate_json(fp.read_text())


def list_bounties(status: Optional[str] = None) -> list[Bounty]:
    out = []
    for fp in sorted(BOUNTY_DIR.glob("*.json")):
        b = Bounty.model_validate_json(fp.read_text())
        if status is None or b.status.value == status:
            out.append(b)
    return out


def post_bounty(
    *,
    poster: str,
    title: str,
    description: str,
    price_usd: float,
    accepted_asset: str = "USDC",
    deadline: str,
    checker_test: Optional[str] = None,
) -> Bounty:
    """Create an open bounty. Funding is a separate step that goes through approvals."""
    b = Bounty(
        id=f"bounty_{uuid.uuid4().hex[:10]}",
        poster=poster,
        title=title,
        description=description,
        price_usd=price_usd,
        accepted_asset=accepted_asset,
        deadline=deadline,
        checker_test=checker_test,
        status=BountyStatus.OPEN,
    )
    logger.info("Posted bounty %s (%s)", b.id, ESCROW_DISCLAIMER)
    return _save(b)


def fund_bounty(
    bounty_id: str,
    *,
    user_request: str,
    policy: Optional[PolicyConfig] = None,
    queue: Optional[QueueClient] = None,
) -> tuple[Bounty, Optional[object]]:
    """Propose funding transfer into an app-managed escrow wallet via Person A stub."""
    b = _load(bounty_id)
    if b.status not in (BountyStatus.OPEN,):
        raise ValueError(f"cannot fund status={b.status.value}")

    escrow = router_stub.create_escrow_wallet(b.id)
    b.escrow_wallet = escrow

    pol = policy or default_research_policy(known_seller_wallets() | {escrow, "escrow_board"})
    # Allow this escrow as recipient for this funding payment.
    pol.recipient_allowlist = set(pol.recipient_allowlist) | {escrow, "escrow_board"}

    proposal, policy_result, verifier = propose_and_enqueue(
        buyer=b.poster,
        seller=escrow,
        amount_usd=b.price_usd,
        purpose=(
            f"Fund APP-MANAGED escrow for bounty '{b.title}'. "
            f"{ESCROW_DISCLAIMER}"
        ),
        source=f"bounty_post:{b.id}",
        user_request=user_request,
        policy=pol,
        queue=queue,
        preferred_asset=b.accepted_asset,
    )
    if proposal is None:
        raise RuntimeError(f"funding blocked by policy: {policy_result.reasons}")

    b.funding_proposal_id = proposal.id
    b.status = BountyStatus.FUNDED  # optimistic; real funds move after human approve+execute
    _save(b)
    return b, proposal


def claim_bounty(bounty_id: str, claimant: str) -> Bounty:
    b = _load(bounty_id)
    if b.status != BountyStatus.FUNDED:
        raise ValueError("only funded bounties can be claimed")
    if b.claimant:
        raise ValueError("already claimed — one claimant at a time")
    b.claimant = claimant
    b.status = BountyStatus.CLAIMED
    return _save(b)


def submit_work(bounty_id: str, claimant: str, submission: str) -> Bounty:
    b = _load(bounty_id)
    if b.claimant != claimant:
        raise ValueError("only the claimant may submit")
    if b.status != BountyStatus.CLAIMED:
        raise ValueError(f"bad status {b.status.value}")
    b.submission = submission
    b.status = BountyStatus.SUBMITTED
    return _save(b)


def run_checker(bounty_id: str) -> dict:
    """Optional objective checker for tasks with checker_test defined.

    Returns a report; a HUMAN must still confirm before payout.
    """
    b = _load(bounty_id)
    if not b.checker_test:
        return {"applicable": False, "note": "no checker_test; human-only verify"}
    submission = (b.submission or "").lower()
    # Extremely simple demo checker: require keywords from the test string.
    required = [w for w in b.checker_test.lower().split() if len(w) > 4][:5]
    missing = [w for w in required if w not in submission]
    passed = len(missing) == 0 and len(submission) > 20
    return {
        "applicable": True,
        "passed": passed,
        "missing_keywords": missing,
        "note": "Checker is advisory; human must confirm before payout.",
        "escrow_disclaimer": ESCROW_DISCLAIMER,
    }


def verify_and_payout(
    bounty_id: str,
    *,
    human_approved: bool,
    user_request: str,
    notes: str = "",
    policy: Optional[PolicyConfig] = None,
    queue: Optional[QueueClient] = None,
) -> tuple[Bounty, Optional[object]]:
    """Human confirms; then propose payout from escrow -> claimant (still needs approval)."""
    b = _load(bounty_id)
    if b.status != BountyStatus.SUBMITTED:
        raise ValueError("submit work before verify")
    if not human_approved:
        return refund_bounty(bounty_id, user_request=user_request, reason=notes or "rejected", policy=policy, queue=queue)

    checker = run_checker(bounty_id)
    b.verify_notes = json.dumps({"human": notes, "checker": checker})

    if not b.escrow_wallet or not b.claimant:
        raise ValueError("missing escrow or claimant")

    pol = policy or default_research_policy(known_seller_wallets() | {b.claimant})
    pol.recipient_allowlist = set(pol.recipient_allowlist) | {b.claimant}

    proposal, policy_result, _ = propose_and_enqueue(
        buyer=b.escrow_wallet,
        seller=b.claimant,
        amount_usd=b.price_usd,
        purpose=f"Bounty payout for '{b.title}' to {b.claimant}. {ESCROW_DISCLAIMER}",
        source=f"bounty_payout:{b.id}",
        user_request=user_request,
        policy=pol,
        queue=queue,
        preferred_asset=b.accepted_asset,
    )
    if proposal is None:
        raise RuntimeError(f"payout blocked: {policy_result.reasons}")

    b.status = BountyStatus.PAID
    _save(b)
    return b, proposal


def refund_bounty(
    bounty_id: str,
    *,
    user_request: str,
    reason: str = "refund",
    policy: Optional[PolicyConfig] = None,
    queue: Optional[QueueClient] = None,
) -> tuple[Bounty, Optional[object]]:
    b = _load(bounty_id)
    if not b.escrow_wallet:
        raise ValueError("no escrow to refund")

    pol = policy or default_research_policy(known_seller_wallets() | {b.poster})
    pol.recipient_allowlist = set(pol.recipient_allowlist) | {b.poster}

    proposal, policy_result, _ = propose_and_enqueue(
        buyer=b.escrow_wallet,
        seller=b.poster,
        amount_usd=b.price_usd,
        purpose=f"Refund bounty '{b.title}' ({reason}). {ESCROW_DISCLAIMER}",
        source=f"bounty_refund:{b.id}",
        user_request=user_request,
        policy=pol,
        queue=queue,
        preferred_asset=b.accepted_asset,
    )
    if proposal is None:
        raise RuntimeError(f"refund blocked: {policy_result.reasons}")

    b.status = BountyStatus.REFUNDED
    b.verify_notes = reason
    _save(b)
    return b, proposal


def demo_deadline(hours: int = 24) -> str:
    from datetime import timedelta

    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
