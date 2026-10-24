"""Shared contract types. Do not change without telling Persons A and C."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class PathStep(BaseModel):
    type: Literal["swap", "transfer"]
    asset: str
    amount: float


class AlternativePath(BaseModel):
    path: list[PathStep]
    rejected_reason: str


class DriftInfo(BaseModel):
    on_chain_price: float
    reference_price: float
    gap_pct: float


class Proposal(BaseModel):
    id: str
    buyer: str
    seller: str
    purpose: str
    amount_usd: float
    path: list[PathStep]
    expected_cost: float
    alternatives: list[AlternativePath] = Field(default_factory=list)
    drift: Optional[DriftInfo] = None
    flags: list[str] = Field(default_factory=list)
    source: str
    status: ProposalStatus = ProposalStatus.PENDING


class Receipt(BaseModel):
    quote: dict[str, Any]
    fill: dict[str, Any]
    tx_hash: str
    status: str


class Decision(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = ""


class SpecialistProfile(BaseModel):
    id: str
    name: str
    capability: str
    private_data: str
    price_usd: float
    accepted_assets: list[str]
    endpoint: str
    wallet: str
    simulated: bool = True


class BountyStatus(str, Enum):
    OPEN = "open"
    FUNDED = "funded"
    CLAIMED = "claimed"
    SUBMITTED = "submitted"
    PAID = "paid"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class Bounty(BaseModel):
    id: str
    poster: str
    title: str
    description: str
    price_usd: float
    accepted_asset: str
    deadline: str
    # Escrow is APP-MANAGED (not a smart contract). Funds sit in a dedicated
    # wallet created via Person A's router; the app alone can transfer out.
    escrow_wallet: Optional[str] = None
    funding_proposal_id: Optional[str] = None
    claimant: Optional[str] = None
    submission: Optional[str] = None
    status: BountyStatus = BountyStatus.OPEN
    checker_test: Optional[str] = None  # optional objective check description
    verify_notes: Optional[str] = None
