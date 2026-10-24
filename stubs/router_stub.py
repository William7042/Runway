"""Person A router STUB — canned proposals/receipts in the shared contract shape.

Agent layer uses this until the real True Markets-backed router lands.
Never call True Markets from the agent layer; always go through propose_payment.
"""

from __future__ import annotations

import os
import uuid
from typing import Optional

from agent.models import (
    AlternativePath,
    DriftInfo,
    PathStep,
    Proposal,
    ProposalStatus,
    Receipt,
)

# In-memory store so execute() can look up approval status.
_PROPOSALS: dict[str, Proposal] = {}


def _dry_run() -> bool:
    return os.getenv("DRY_RUN", "1") == "1"


def propose_payment(
    buyer: str,
    seller: str,
    amount_usd: float,
    purpose: str,
    source: str,
    *,
    flags: Optional[list[str]] = None,
    preferred_asset: str = "USDC",
) -> Proposal:
    """Return a canned Proposal matching the shared contract.

    Real router (Person A) will quote paths from buyer balances. Stub always
    proposes: swap a slice of ETH -> USDC, then transfer USDC to seller.
    """
    from runway_money.assets import COMMERCE_SYMBOLS
    if preferred_asset not in COMMERCE_SYMBOLS:
        raise ValueError('Asset is outside the commerce allowlist')
    swap_amount = round(amount_usd / 3000.0, 6)  # pretend ETH ~ $3000
    path = [
        PathStep(type="swap", asset="ETH", amount=swap_amount),
        PathStep(type="transfer", asset=preferred_asset, amount=amount_usd),
    ]
    alt = AlternativePath(
        path=[PathStep(type="transfer", asset="USDC", amount=amount_usd)],
        rejected_reason="Buyer USDC balance below amount; endowment prefers gains from ETH",
    )
    proposal = Proposal(
        id=f"prop_{uuid.uuid4().hex[:10]}",
        buyer=buyer,
        seller=seller,
        purpose=purpose,
        amount_usd=amount_usd,
        path=path,
        expected_cost=round(amount_usd * 0.003, 4),  # ~30 bps fees
        alternatives=[alt],
        drift=DriftInfo(on_chain_price=3001.5, reference_price=3000.05, gap_pct=0.05),
        flags=[
            "SIMULATED: canned ETH price and balances; no funds move",
            *(flags or []),
        ],
        source=source,
        status=ProposalStatus.PENDING,
    )
    _PROPOSALS[proposal.id] = proposal
    return proposal


def mark_status(proposal_id: str, status: ProposalStatus) -> None:
    """Called by queue sync so the stub knows about human decisions."""
    if proposal_id in _PROPOSALS:
        _PROPOSALS[proposal_id].status = status


def get_proposal(proposal_id: str) -> Optional[Proposal]:
    return _PROPOSALS.get(proposal_id)


def execute(proposal_id: str) -> Receipt:
    """Refuse unless approved. DRY_RUN=1 returns a fake receipt without signing."""
    proposal = _PROPOSALS.get(proposal_id)
    if proposal is None:
        raise ValueError(f"Unknown proposal {proposal_id}")
    if proposal.status != ProposalStatus.APPROVED:
        raise PermissionError(
            f"Refusing execute: proposal {proposal_id} status={proposal.status.value} "
            "(only 'approved' may execute; no auto-approve)"
        )

    if _dry_run():
        receipt = Receipt(
            quote={"pair": "ETH/USDC", "amount_usd": proposal.amount_usd, "dry_run": True},
            fill={"filled": False, "reason": "DRY_RUN=1 — nothing signed or sent"},
            tx_hash="0xdryrun0000000000000000000000000000000000",
            status="dry_run",
        )
        proposal.status = ProposalStatus.EXECUTED
        return receipt

    # Real path would call True Markets; stub never does.
    receipt = Receipt(
        quote={"pair": "ETH/USDC", "amount_usd": proposal.amount_usd},
        fill={"filled": True, "amount_usd": proposal.amount_usd},
        tx_hash=f"0xstub{uuid.uuid4().hex[:40]}",
        status="executed",
    )
    proposal.status = ProposalStatus.EXECUTED
    return receipt


def create_escrow_wallet(bounty_id: str) -> str:
    """App-managed escrow wallet id (not a smart contract)."""
    return f"escrow_{bounty_id}_{uuid.uuid4().hex[:6]}"
